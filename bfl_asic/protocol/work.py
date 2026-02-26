"""Work-unit construction and SHA-256 midstate computation.

This module provides pure functions for building Bitcoin block headers,
computing the SHA-256 intermediate state (midstate) after the first
512-bit block, and generating synthetic work units for testing.

No I/O happens here.
"""

from __future__ import annotations

import os
import struct

# -------------------------------------------------------------------
# SHA-256 constants (NIST FIPS 180-4)
# -------------------------------------------------------------------

# Initial hash values H0..H7 -- first 32 bits of the fractional parts
# of the square roots of the first 8 primes.
_H0 = (
    0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A,
    0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19,
)

# Round constants K[0..63] -- first 32 bits of the fractional parts
# of the cube roots of the first 64 primes.
_K = (
    0x428A2F98, 0x71374491, 0xB5C0FBCF, 0xE9B5DBA5,
    0x3956C25B, 0x59F111F1, 0x923F82A4, 0xAB1C5ED5,
    0xD807AA98, 0x12835B01, 0x243185BE, 0x550C7DC3,
    0x72BE5D74, 0x80DEB1FE, 0x9BDC06A7, 0xC19BF174,
    0xE49B69C1, 0xEFBE4786, 0x0FC19DC6, 0x240CA1CC,
    0x2DE92C6F, 0x4A7484AA, 0x5CB0A9DC, 0x76F988DA,
    0x983E5152, 0xA831C66D, 0xB00327C8, 0xBF597FC7,
    0xC6E00BF3, 0xD5A79147, 0x06CA6351, 0x14292967,
    0x27B70A85, 0x2E1B2138, 0x4D2C6DFC, 0x53380D13,
    0x650A7354, 0x766A0ABB, 0x81C2C92E, 0x92722C85,
    0xA2BFE8A1, 0xA81A664B, 0xC24B8B70, 0xC76C51A3,
    0xD192E819, 0xD6990624, 0xF40E3585, 0x106AA070,
    0x19A4C116, 0x1E376C08, 0x2748774C, 0x34B0BCB5,
    0x391C0CB3, 0x4ED8AA4A, 0x5B9CCA4F, 0x682E6FF3,
    0x748F82EE, 0x78A5636F, 0x84C87814, 0x8CC70208,
    0x90BEFFFA, 0xA4506CEB, 0xBEF9A3F7, 0xC67178F2,
)

_MASK32 = 0xFFFFFFFF


# -------------------------------------------------------------------
# SHA-256 helper bit-operations (all 32-bit unsigned)
# -------------------------------------------------------------------

def _rotr(x: int, n: int) -> int:
    """Right-rotate a 32-bit word *x* by *n* bits."""
    return ((x >> n) | (x << (32 - n))) & _MASK32


def _ch(x: int, y: int, z: int) -> int:
    return ((x & y) ^ (~x & z)) & _MASK32


def _maj(x: int, y: int, z: int) -> int:
    return (x & y) ^ (x & z) ^ (y & z)


def _sigma0(x: int) -> int:
    return _rotr(x, 2) ^ _rotr(x, 13) ^ _rotr(x, 22)


def _sigma1(x: int) -> int:
    return _rotr(x, 6) ^ _rotr(x, 11) ^ _rotr(x, 25)


def _gamma0(x: int) -> int:
    return _rotr(x, 7) ^ _rotr(x, 18) ^ (x >> 3)


def _gamma1(x: int) -> int:
    return _rotr(x, 17) ^ _rotr(x, 19) ^ (x >> 10)


# -------------------------------------------------------------------
# SHA-256 compression function
# -------------------------------------------------------------------

def _sha256_compress(
    block: bytes,
    h: tuple[int, ...],
) -> tuple[int, ...]:
    """Run one round of the SHA-256 compression function.

    Parameters
    ----------
    block:
        Exactly 64 bytes (one 512-bit message block).
    h:
        Eight 32-bit words representing the current hash state.

    Returns
    -------
    tuple[int, ...]
        Updated 8-word hash state.
    """
    # Prepare message schedule W[0..63]
    w = list(struct.unpack(">16I", block))
    for i in range(16, 64):
        w.append(
            (_gamma1(w[i - 2]) + w[i - 7] + _gamma0(w[i - 15]) + w[i - 16])
            & _MASK32
        )

    # Initialise working variables
    a, b, c, d, e, f, g, hh = h

    # 64 rounds
    for i in range(64):
        t1 = (hh + _sigma1(e) + _ch(e, f, g) + _K[i] + w[i]) & _MASK32
        t2 = (_sigma0(a) + _maj(a, b, c)) & _MASK32
        hh = g
        g = f
        f = e
        e = (d + t1) & _MASK32
        d = c
        c = b
        b = a
        a = (t1 + t2) & _MASK32

    # Add compressed chunk to current hash value
    return (
        (h[0] + a) & _MASK32,
        (h[1] + b) & _MASK32,
        (h[2] + c) & _MASK32,
        (h[3] + d) & _MASK32,
        (h[4] + e) & _MASK32,
        (h[5] + f) & _MASK32,
        (h[6] + g) & _MASK32,
        (h[7] + hh) & _MASK32,
    )


# -------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------

def compute_midstate(block_header_first_64: bytes) -> bytes:
    """Compute the SHA-256 midstate after processing one 512-bit block.

    This returns the **intermediate** hash state -- i.e. the eight
    32-bit words that result from compressing the first 64 bytes of a
    block header through SHA-256, **before** any padding or
    finalisation is applied.

    Parameters
    ----------
    block_header_first_64:
        The first 64 bytes of a Bitcoin block header.

    Returns
    -------
    bytes
        32 bytes (8 x 4-byte big-endian words).

    Raises
    ------
    ValueError
        If *block_header_first_64* is not exactly 64 bytes.
    """
    if len(block_header_first_64) != 64:
        raise ValueError(
            f"Input must be exactly 64 bytes, got {len(block_header_first_64)}"
        )
    state = _sha256_compress(block_header_first_64, _H0)
    return struct.pack(">8I", *state)


def build_block_header(
    version: int,
    prev_hash: bytes,
    merkle_root: bytes,
    timestamp: int,
    bits: int,
    nonce: int = 0,
) -> bytes:
    """Construct an 80-byte Bitcoin block header.

    Layout (all multi-byte integers are little-endian)::

        Bytes  0- 3 : version      (int32)
        Bytes  4-35 : prev_hash    (32 bytes, as-is)
        Bytes 36-67 : merkle_root  (32 bytes, as-is)
        Bytes 68-71 : timestamp    (uint32)
        Bytes 72-75 : bits         (uint32)
        Bytes 76-79 : nonce        (uint32)

    Parameters
    ----------
    version:
        Block version number.
    prev_hash:
        Hash of the previous block (exactly 32 bytes).
    merkle_root:
        Merkle root hash (exactly 32 bytes).
    timestamp:
        Block timestamp as a Unix epoch value.
    bits:
        Encoded difficulty target.
    nonce:
        Starting nonce value (defaults to 0).

    Raises
    ------
    ValueError
        If *prev_hash* or *merkle_root* are not 32 bytes.
    """
    if len(prev_hash) != 32:
        raise ValueError(
            f"prev_hash must be exactly 32 bytes, got {len(prev_hash)}"
        )
    if len(merkle_root) != 32:
        raise ValueError(
            f"merkle_root must be exactly 32 bytes, got {len(merkle_root)}"
        )
    return (
        struct.pack("<i", version)
        + prev_hash
        + merkle_root
        + struct.pack("<I", timestamp)
        + struct.pack("<I", bits)
        + struct.pack("<I", nonce)
    )


def build_synthetic_work(
    seed: bytes | None = None,
) -> tuple[bytes, bytes]:
    """Generate a synthetic work unit for non-mining testing.

    Constructs a fake 80-byte block header (from *seed* or random
    bytes), computes its midstate, and returns the ``(midstate, tail)``
    pair ready for :func:`bfl_asic.protocol.commands.build_work`.

    Parameters
    ----------
    seed:
        Optional 64-byte seed.  When ``None``, 64 random bytes are
        used via :func:`os.urandom`.

    Returns
    -------
    tuple[bytes, bytes]
        ``(midstate, tail)`` where *midstate* is 32 bytes and *tail*
        is 12 bytes (block header bytes 64-75, with the nonce field
        set to zero).
    """
    if seed is None:
        seed = os.urandom(64)

    # We need 76 bytes for the header-without-nonce.  Use the seed for
    # the first 64, then take bytes 0..11 of the seed again for the
    # tail portion (bytes 64-75).  The nonce (bytes 76-79) is always 0.
    if len(seed) < 64:
        raise ValueError(
            f"seed must be at least 64 bytes, got {len(seed)}"
        )

    first_64 = seed[:64]
    # Tail: bytes 64-75 of the "block header".  If the seed is long
    # enough, use bytes 64-75; otherwise fill with zeros.
    if len(seed) >= 76:
        tail = seed[64:76]
    else:
        # Pad with zeros so the tail covers bytes 64..75
        extra = seed[64:]
        tail = extra + b"\x00" * (12 - len(extra))

    midstate = compute_midstate(first_64)
    return midstate, tail
