"""Tests for bfl_asic.protocol.work."""

import hashlib
import struct

import pytest

from bfl_asic.protocol.work import (
    build_block_header,
    build_synthetic_work,
    compute_midstate,
    _sha256_compress,
    _H0,
)


# -------------------------------------------------------------------
# Known test vector: Bitcoin genesis block (block #0)
#
# The 80-byte header in hex:
#   version    = 01000000
#   prev_hash  = 00000000 00000000 00000000 00000000
#                00000000 00000000 00000000 00000000
#   merkle     = 3ba3edfd 7a7b12b2 7ac72c3e 67768f61
#                7fc81bc3 888a5132 3a9fb8aa 4b1e5e4a
#   timestamp  = 29ab5f49
#   bits       = ffff001d
#   nonce      = 1dac2b7c
# -------------------------------------------------------------------

GENESIS_HEADER_HEX = (
    "01000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
    "29ab5f49"
    "ffff001d"
    "1dac2b7c"
)

GENESIS_HEADER = bytes.fromhex(GENESIS_HEADER_HEX)
GENESIS_FIRST_64 = GENESIS_HEADER[:64]


# -------------------------------------------------------------------
# compute_midstate
# -------------------------------------------------------------------

class TestComputeMidstate:
    def test_returns_32_bytes(self):
        result = compute_midstate(GENESIS_FIRST_64)
        assert len(result) == 32

    def test_returns_bytes_type(self):
        result = compute_midstate(GENESIS_FIRST_64)
        assert isinstance(result, bytes)

    def test_validates_input_too_short(self):
        with pytest.raises(ValueError, match="exactly 64 bytes"):
            compute_midstate(b"\x00" * 63)

    def test_validates_input_too_long(self):
        with pytest.raises(ValueError, match="exactly 64 bytes"):
            compute_midstate(b"\x00" * 65)

    def test_validates_empty_input(self):
        with pytest.raises(ValueError, match="exactly 64 bytes"):
            compute_midstate(b"")

    def test_deterministic(self):
        """Same input always produces the same midstate."""
        a = compute_midstate(GENESIS_FIRST_64)
        b = compute_midstate(GENESIS_FIRST_64)
        assert a == b

    def test_different_input_different_output(self):
        a = compute_midstate(b"\x00" * 64)
        b = compute_midstate(b"\x01" + b"\x00" * 63)
        assert a != b

    def test_midstate_matches_sha256_internal_state(self):
        """Verify our midstate against a full SHA-256 hash.

        If we feed the same 64 bytes as the first block, then manually
        construct what SHA-256 would produce for a message that is
        exactly 64 bytes (with proper padding in the second block), the
        intermediate state after block 1 should match our midstate.

        We verify by padding the 64-byte input to produce a second
        block, compressing that second block with our midstate as the
        initial state, and comparing the result to hashlib.sha256.
        """
        data = GENESIS_FIRST_64
        midstate_bytes = compute_midstate(data)

        # Parse midstate into 8 x uint32
        midstate_words = struct.unpack(">8I", midstate_bytes)

        # SHA-256 padding for a 64-byte (512-bit) message:
        # append 0x80, then zeros, then 64-bit big-endian bit length
        # Total padded length must be a multiple of 64.
        # 64 bytes = 512 bits.  Padding: 0x80 + 55 zero bytes + 8-byte length
        # = 64 bytes (one more block).
        bit_length = 64 * 8  # 512 bits
        padding = b"\x80" + b"\x00" * 55 + struct.pack(">Q", bit_length)
        assert len(padding) == 64

        # Compress padding block using our midstate as input state
        final_state = _sha256_compress(padding, midstate_words)
        our_digest = struct.pack(">8I", *final_state)

        # Compare with hashlib
        expected = hashlib.sha256(data).digest()
        assert our_digest == expected

    def test_known_all_zeros(self):
        """Midstate of all-zero 64 bytes, verified via SHA-256 round-trip."""
        data = b"\x00" * 64
        midstate_bytes = compute_midstate(data)
        midstate_words = struct.unpack(">8I", midstate_bytes)

        # Pad and compress second block
        bit_length = 64 * 8
        padding = b"\x80" + b"\x00" * 55 + struct.pack(">Q", bit_length)
        final_state = _sha256_compress(padding, midstate_words)
        our_digest = struct.pack(">8I", *final_state)

        expected = hashlib.sha256(data).digest()
        assert our_digest == expected


# -------------------------------------------------------------------
# build_block_header
# -------------------------------------------------------------------

class TestBuildBlockHeader:
    def test_length_is_80(self):
        header = build_block_header(
            version=1,
            prev_hash=b"\x00" * 32,
            merkle_root=b"\x00" * 32,
            timestamp=0,
            bits=0,
            nonce=0,
        )
        assert len(header) == 80

    def test_version_little_endian(self):
        header = build_block_header(
            version=2,
            prev_hash=b"\x00" * 32,
            merkle_root=b"\x00" * 32,
            timestamp=0,
            bits=0,
        )
        assert header[:4] == b"\x02\x00\x00\x00"

    def test_prev_hash_position(self):
        prev = bytes(range(32))
        header = build_block_header(
            version=1,
            prev_hash=prev,
            merkle_root=b"\x00" * 32,
            timestamp=0,
            bits=0,
        )
        assert header[4:36] == prev

    def test_merkle_root_position(self):
        merkle = bytes(range(32))
        header = build_block_header(
            version=1,
            prev_hash=b"\x00" * 32,
            merkle_root=merkle,
            timestamp=0,
            bits=0,
        )
        assert header[36:68] == merkle

    def test_timestamp_little_endian(self):
        header = build_block_header(
            version=1,
            prev_hash=b"\x00" * 32,
            merkle_root=b"\x00" * 32,
            timestamp=0x495FAB29,
            bits=0,
        )
        assert header[68:72] == struct.pack("<I", 0x495FAB29)

    def test_bits_little_endian(self):
        header = build_block_header(
            version=1,
            prev_hash=b"\x00" * 32,
            merkle_root=b"\x00" * 32,
            timestamp=0,
            bits=0x1D00FFFF,
        )
        assert header[72:76] == struct.pack("<I", 0x1D00FFFF)

    def test_nonce_little_endian(self):
        header = build_block_header(
            version=1,
            prev_hash=b"\x00" * 32,
            merkle_root=b"\x00" * 32,
            timestamp=0,
            bits=0,
            nonce=0x7C2BAC1D,
        )
        assert header[76:80] == struct.pack("<I", 0x7C2BAC1D)

    def test_nonce_defaults_to_zero(self):
        header = build_block_header(
            version=1,
            prev_hash=b"\x00" * 32,
            merkle_root=b"\x00" * 32,
            timestamp=0,
            bits=0,
        )
        assert header[76:80] == b"\x00\x00\x00\x00"

    def test_genesis_block_reconstruction(self):
        """Reconstruct the Bitcoin genesis block header and compare."""
        prev_hash = b"\x00" * 32
        merkle_root = bytes.fromhex(
            "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
        )
        header = build_block_header(
            version=1,
            prev_hash=prev_hash,
            merkle_root=merkle_root,
            timestamp=0x495FAB29,
            bits=0x1D00FFFF,
            nonce=0x7C2BAC1D,
        )
        assert header == GENESIS_HEADER

    def test_rejects_short_prev_hash(self):
        with pytest.raises(ValueError, match="prev_hash"):
            build_block_header(
                version=1,
                prev_hash=b"\x00" * 31,
                merkle_root=b"\x00" * 32,
                timestamp=0,
                bits=0,
            )

    def test_rejects_long_prev_hash(self):
        with pytest.raises(ValueError, match="prev_hash"):
            build_block_header(
                version=1,
                prev_hash=b"\x00" * 33,
                merkle_root=b"\x00" * 32,
                timestamp=0,
                bits=0,
            )

    def test_rejects_short_merkle_root(self):
        with pytest.raises(ValueError, match="merkle_root"):
            build_block_header(
                version=1,
                prev_hash=b"\x00" * 32,
                merkle_root=b"\x00" * 31,
                timestamp=0,
                bits=0,
            )

    def test_rejects_long_merkle_root(self):
        with pytest.raises(ValueError, match="merkle_root"):
            build_block_header(
                version=1,
                prev_hash=b"\x00" * 32,
                merkle_root=b"\x00" * 33,
                timestamp=0,
                bits=0,
            )


# -------------------------------------------------------------------
# build_synthetic_work
# -------------------------------------------------------------------

class TestBuildSyntheticWork:
    def test_returns_tuple(self):
        result = build_synthetic_work()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_midstate_is_32_bytes(self):
        midstate, _ = build_synthetic_work()
        assert len(midstate) == 32

    def test_tail_is_12_bytes(self):
        _, tail = build_synthetic_work()
        assert len(tail) == 12

    def test_midstate_is_bytes(self):
        midstate, _ = build_synthetic_work()
        assert isinstance(midstate, bytes)

    def test_tail_is_bytes(self):
        _, tail = build_synthetic_work()
        assert isinstance(tail, bytes)

    def test_with_seed(self):
        seed = bytes(range(64))
        midstate, tail = build_synthetic_work(seed=seed)
        assert len(midstate) == 32
        assert len(tail) == 12

    def test_deterministic_with_seed(self):
        seed = bytes(range(64))
        a = build_synthetic_work(seed=seed)
        b = build_synthetic_work(seed=seed)
        assert a == b

    def test_different_seeds_different_results(self):
        seed_a = b"\x00" * 64
        seed_b = b"\x01" + b"\x00" * 63
        a = build_synthetic_work(seed=seed_a)
        b = build_synthetic_work(seed=seed_b)
        assert a[0] != b[0]  # midstates differ

    def test_without_seed_is_random(self):
        """Two calls without seed should almost certainly differ."""
        a = build_synthetic_work()
        b = build_synthetic_work()
        # Extremely unlikely to be equal with random 64-byte seeds
        assert a != b

    def test_seed_longer_than_64_uses_extra_for_tail(self):
        seed = bytes(range(76))
        midstate, tail = build_synthetic_work(seed=seed)
        # Midstate is computed from first 64 bytes
        expected_midstate = compute_midstate(seed[:64])
        assert midstate == expected_midstate
        # Tail is bytes 64-75
        assert tail == seed[64:76]

    def test_seed_exactly_64_pads_tail_with_zeros(self):
        seed = bytes(range(64))
        midstate, tail = build_synthetic_work(seed=seed)
        expected_midstate = compute_midstate(seed[:64])
        assert midstate == expected_midstate
        # Tail should be 12 zero bytes since seed has no data past 64
        assert tail == b"\x00" * 12

    def test_seed_too_short_raises(self):
        with pytest.raises(ValueError, match="at least 64 bytes"):
            build_synthetic_work(seed=b"\x00" * 63)

    def test_midstate_consistent_with_compute_midstate(self):
        """The midstate from build_synthetic_work should match
        compute_midstate on the first 64 bytes of the seed."""
        seed = bytes(range(76))
        midstate, _ = build_synthetic_work(seed=seed)
        expected = compute_midstate(seed[:64])
        assert midstate == expected
