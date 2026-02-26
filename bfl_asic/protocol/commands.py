"""Pure functions that build command byte sequences for the BFL ASIC.

Every function returns a ``bytes`` object ready to be written to the
serial port.  No I/O happens here.
"""

from __future__ import annotations

import struct

from bfl_asic.protocol.constants import DELIMITER


def build_identify() -> bytes:
    """Return the 3-byte identify command (ZGX)."""
    return b"ZGX"


def build_temperature() -> bytes:
    """Return the 3-byte temperature query command (ZTX)."""
    return b"ZTX"


def build_poll() -> bytes:
    """Return the 3-byte result-poll command (ZFX)."""
    return b"ZFX"


def build_work(midstate: bytes, tail: bytes) -> bytes:
    """Construct a 60-byte work packet.

    Layout::

        Bytes  0- 7 : DELIMITER  (8 bytes)
        Bytes  8-39 : midstate  (32 bytes)
        Bytes 40-51 : tail      (12 bytes)
        Bytes 52-59 : DELIMITER  (8 bytes)

    Parameters
    ----------
    midstate:
        SHA-256 intermediate hash state (exactly 32 bytes).
    tail:
        Remaining block-header bytes after the midstate input
        (exactly 12 bytes).

    Raises
    ------
    ValueError
        If *midstate* is not 32 bytes or *tail* is not 12 bytes.
    """
    if len(midstate) != 32:
        raise ValueError(
            f"midstate must be exactly 32 bytes, got {len(midstate)}"
        )
    if len(tail) != 12:
        raise ValueError(
            f"tail must be exactly 12 bytes, got {len(tail)}"
        )
    return DELIMITER + midstate + tail + DELIMITER


def build_nonce_range(
    midstate: bytes,
    tail: bytes,
    start: int,
    end: int,
) -> bytes:
    """Construct a 68-byte nonce-range work packet.

    Layout::

        Bytes  0-59 : same as :func:`build_work`
        Bytes 60-63 : start nonce (big-endian uint32)
        Bytes 64-67 : end nonce   (big-endian uint32)

    Parameters
    ----------
    midstate:
        SHA-256 intermediate hash state (exactly 32 bytes).
    tail:
        Remaining block-header bytes (exactly 12 bytes).
    start:
        Start nonce (0 .. 0xFFFFFFFF).
    end:
        End nonce (0 .. 0xFFFFFFFF).

    Raises
    ------
    ValueError
        If nonce values are out of the 32-bit unsigned range, or if
        *midstate* / *tail* lengths are wrong.
    """
    if not (0 <= start <= 0xFFFFFFFF):
        raise ValueError(
            f"start nonce must fit in 32 bits (0..0xFFFFFFFF), got {start}"
        )
    if not (0 <= end <= 0xFFFFFFFF):
        raise ValueError(
            f"end nonce must fit in 32 bits (0..0xFFFFFFFF), got {end}"
        )
    work = build_work(midstate, tail)
    return work + struct.pack(">I", start) + struct.pack(">I", end)
