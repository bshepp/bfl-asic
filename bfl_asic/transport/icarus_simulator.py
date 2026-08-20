"""In-process simulator for the Icarus protocol (Block Erupter class).

Mirrors :class:`~bfl_asic.transport.simulator.SimulatorTransport` but for
the far simpler Icarus wire protocol: accumulate written bytes until a full
64-byte work unit has arrived, then make a deterministic 4-byte nonce
available to read. Lets the Icarus source/characterisation layers be tested
headless, with no Block Erupter attached.

The golden work returns the golden nonce (matching real hardware); any other
work returns a deterministic nonce derived from its bytes, so tests over the
nonce stream are reproducible.
"""
from __future__ import annotations

import hashlib

from bfl_asic.exceptions import BFLConnectionError
from bfl_asic.protocol.icarus import (
    GOLDEN_NONCE, GOLDEN_WORK, NONCE_SIZE, WORK_SIZE,
)


class SimulatedIcarusDevice:
    """Deterministic Icarus 'chip': one 64-byte work -> one 4-byte nonce."""

    def process_work(self, work: bytes) -> bytes:
        """Return a 4-byte big-endian nonce for *work* (or b"" for none)."""
        if work == GOLDEN_WORK:
            return GOLDEN_NONCE.to_bytes(NONCE_SIZE, "big")
        nonce = int.from_bytes(hashlib.sha256(work).digest()[:NONCE_SIZE],
                               "big")
        return nonce.to_bytes(NONCE_SIZE, "big")


class SimulatedIcarusTransport:
    """Bridge the transport interface to a :class:`SimulatedIcarusDevice`.

    Implements the sync :class:`~bfl_asic.transport.base.BaseTransport` API
    directly (rather than subclassing) to keep this module independent of the
    BFL-flavoured base; the async wrappers aren't needed for the sync source.
    """

    def __init__(self, device: SimulatedIcarusDevice | None = None) -> None:
        self._device = device or SimulatedIcarusDevice()
        self._work_buffer = b""
        self._response_buffer = b""
        self._opened = False

    def open(self) -> None:
        self._opened = True

    def close(self) -> None:
        self._opened = False
        self._work_buffer = b""
        self._response_buffer = b""

    def flush_input(self) -> None:
        self._response_buffer = b""

    def write(self, data: bytes) -> None:
        if not self._opened:
            raise BFLConnectionError("Transport is not open")
        self._work_buffer += data
        while len(self._work_buffer) >= WORK_SIZE:
            work = self._work_buffer[:WORK_SIZE]
            self._work_buffer = self._work_buffer[WORK_SIZE:]
            self._response_buffer += self._device.process_work(work)

    def read(self, size: int, timeout: float | None = None) -> bytes:
        if not self._opened:
            raise BFLConnectionError("Transport is not open")
        data = self._response_buffer[:size]
        self._response_buffer = self._response_buffer[size:]
        return data

    def readline(self, timeout: float | None = None) -> bytes:
        # Icarus has no line framing; nonces are fixed-width. Provided only
        # to satisfy transport-shaped callers.
        return self.read(len(self._response_buffer), timeout)

    @property
    def is_open(self) -> bool:
        return self._opened

    @property
    def device(self) -> SimulatedIcarusDevice:
        return self._device
