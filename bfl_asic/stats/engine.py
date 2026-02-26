"""Pluggable hash source abstraction with software SHA-256d implementations.

This module defines a :class:`HashSource` ABC that any hash-producing backend
must implement, plus two concrete software engines:

* :class:`SoftwareHashEngine` -- sequential 32-byte counter inputs.
* :class:`SequentialInputEngine` -- 24-byte base prefix + 8-byte counter,
  designed for avalanche analysis where consecutive inputs differ by exactly 1.

No I/O happens here -- all hashing uses :mod:`hashlib`.
"""

from __future__ import annotations

import hashlib
import struct
from abc import ABC, abstractmethod
from typing import Iterator


# -------------------------------------------------------------------
# Abstract base
# -------------------------------------------------------------------

class HashSource(ABC):
    """Abstract base for anything that produces SHA-256d digests."""

    @abstractmethod
    def hashes(self, count: int | None = None) -> Iterator[tuple[bytes, bytes]]:
        """Yield ``(input_bytes, sha256d_output)`` pairs.

        Parameters
        ----------
        count:
            Number of hashes to produce.  ``None`` means infinite.
        """
        ...

    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this hash source."""
        ...


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _sha256d(data: bytes) -> bytes:
    """Compute SHA-256d (double SHA-256) of *data*."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


# -------------------------------------------------------------------
# SoftwareHashEngine
# -------------------------------------------------------------------

class SoftwareHashEngine(HashSource):
    """Hash engine that generates sequential 32-byte inputs and computes SHA-256d.

    Each input is a 4-byte big-endian counter zero-padded to 32 bytes::

        struct.pack(">I", counter).ljust(32, b'\\x00')

    Parameters
    ----------
    start:
        Starting counter value (default 0).
    """

    def __init__(self, start: int = 0) -> None:
        self._start = start

    def hashes(self, count: int | None = None) -> Iterator[tuple[bytes, bytes]]:
        """Yield ``(input_bytes, sha256d_output)`` pairs.

        Parameters
        ----------
        count:
            Number of pairs to yield.  ``None`` produces an unbounded stream.
        """
        counter = self._start
        produced = 0
        while count is None or produced < count:
            input_bytes = struct.pack(">I", counter).ljust(32, b"\x00")
            output = _sha256d(input_bytes)
            yield (input_bytes, output)
            counter += 1
            produced += 1

    def name(self) -> str:
        """Return human-readable engine name."""
        return "software-sha256d"


# -------------------------------------------------------------------
# SequentialInputEngine
# -------------------------------------------------------------------

class SequentialInputEngine(HashSource):
    """Hash engine for avalanche analysis with tightly sequential inputs.

    Inputs are 32 bytes: a fixed 24-byte *base* prefix followed by an 8-byte
    big-endian counter.  Consecutive inputs therefore differ by exactly +1 in
    the last 8 bytes.

    Parameters
    ----------
    base:
        24-byte prefix.  ``None`` defaults to 24 zero bytes.
    start:
        Starting counter value (default 0).

    Raises
    ------
    ValueError
        If *base* is not ``None`` and not exactly 24 bytes.
    """

    def __init__(self, base: bytes | None = None, start: int = 0) -> None:
        if base is None:
            base = b"\x00" * 24
        if len(base) != 24:
            raise ValueError(
                f"base must be exactly 24 bytes, got {len(base)}"
            )
        self._base = base
        self._start = start

    def hashes(self, count: int | None = None) -> Iterator[tuple[bytes, bytes]]:
        """Yield ``(input_bytes, sha256d_output)`` pairs.

        Parameters
        ----------
        count:
            Number of pairs to yield.  ``None`` produces an unbounded stream.
        """
        counter = self._start
        produced = 0
        while count is None or produced < count:
            input_bytes = self._base + struct.pack(">Q", counter)
            output = _sha256d(input_bytes)
            yield (input_bytes, output)
            counter += 1
            produced += 1

    def name(self) -> str:
        """Return human-readable engine name."""
        return "sequential-input-sha256d"
