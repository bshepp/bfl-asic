"""Pure builders/parsers for the Icarus serial mining protocol.

The Icarus protocol (ASICMiner Block Erupter, Antminer U-series, and the
BM1384 GekkoScience Compac all speak it) is deliberately minimal: write a
64-byte work unit, read back a 4-byte nonce. There is no command space --
the device only hashes (confirmed by falsification on real hardware,
2026-08-19).

Byte layout (from cgminer's driver-icarus.c): a 64-byte work unit is
``rev(midstate, 32) + 20-byte fill + rev(data, 12)``; the nonce reply is
4 bytes, big-endian on the wire. The ``GOLDEN_WORK`` / ``GOLDEN_NONCE``
pair is cgminer's detection self-test (Block 171874).

No I/O happens here.
"""
from __future__ import annotations

WORK_SIZE = 64
NONCE_SIZE = 4
IO_SPEED = 115200  # baud (Block Erupter / Antminer U)

# cgminer driver-icarus.c golden self-test.
GOLDEN_WORK = bytes.fromhex(
    "4679ba4ec99876bf4bfe086082b40025"
    "4df6c356451471139a3afa71e48f544a"
    "00000000000000000000000000000000"
    "0000000087320b1a1426674f2fa722ce"
)
GOLDEN_NONCE = 0x000187A2


def build_work(midstate: bytes, data: bytes) -> bytes:
    """Build a 64-byte Icarus work unit from *midstate* (32B) and *data* (12B).

    Mirrors cgminer: both fields are byte-reversed, separated by a 20-byte
    zero fill. Returns exactly ``WORK_SIZE`` bytes.
    """
    if len(midstate) != 32:
        raise ValueError(f"midstate must be 32 bytes, got {len(midstate)}")
    if len(data) != 12:
        raise ValueError(f"data must be 12 bytes, got {len(data)}")
    return midstate[::-1] + b"\x00" * 20 + data[::-1]


def parse_nonce(raw: bytes) -> int:
    """Parse a 4-byte Icarus nonce reply (big-endian) into an int."""
    if len(raw) != NONCE_SIZE:
        raise ValueError(f"nonce must be {NONCE_SIZE} bytes, got {len(raw)}")
    return int.from_bytes(raw, "big")


def linear_scan_hashrate(nonce_time_pairs) -> float | None:
    """Estimate hashrate in H/s from ``(nonce_position, arrival_time)`` pairs.

    A device that scans nonces linearly from 0 reaches position ``N`` after
    ``N / rate`` seconds, so ``nonce / time == rate``. Averages that estimate
    over every pair with a positive arrival time; returns ``None`` if no
    usable sample exists.
    """
    rates = [n / t for n, t in nonce_time_pairs if t > 0]
    if not rates:
        return None
    return sum(rates) / len(rates)
