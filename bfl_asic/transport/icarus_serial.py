"""Real-hardware serial transport for the Icarus protocol.

The Icarus wire protocol (ASICMiner Block Erupter, Antminer U-series,
GekkoScience BM1384) is write-64-byte-work / read-4-byte-nonce with no line
framing. This transport is the live-port counterpart to
:class:`~bfl_asic.transport.icarus_simulator.SimulatedIcarusTransport`; it
drives a CP210x/FTDI USB-UART bridge via pyserial and plugs straight into
:class:`~bfl_asic.nonce_source.IcarusNonceSource` and the shared
characterisation layer.

It mirrors :class:`~bfl_asic.transport.serial.SerialTransport`'s conventions
(8N1, reset buffers on open, timeout-override-and-restore reads) with two
Icarus-specific differences:

* the default read *timeout* is long (seconds), because an Icarus device may
  scan much of the 32-bit nonce space before returning a nonce -- or return
  none at all for a given work unit;
* a ``serial_factory`` seam lets the byte plumbing be tested against a fake
  serial port without hardware.
"""
from __future__ import annotations

from typing import Callable

import serial as pyserial

from bfl_asic.exceptions import BFLConnectionError
from bfl_asic.transport.base import BaseTransport


class IcarusSerialTransport(BaseTransport):
    """Transport for a real Icarus-class miner over a serial port."""

    def __init__(self, port: str, baudrate: int = 115200,
                 timeout: float = 11.0, *,
                 serial_factory: Callable[..., object] | None = None) -> None:
        """Create the transport (does **not** open the port yet).

        Args:
            port: Serial port path (``'COM4'`` on Windows, ``'/dev/ttyUSB0'``
                on Linux).
            baudrate: Baud rate. Default ``115200`` (Block Erupter / Antminer U).
            timeout: Default read timeout in seconds. Long by design -- a nonce
                may take a full nonce-space scan to arrive, and many work units
                yield none. Overridable per :meth:`read` call.
            serial_factory: Callable constructing the underlying serial object
                (test seam). Defaults to :class:`serial.Serial`.
        """
        self._port = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._serial_factory = serial_factory or pyserial.Serial
        self._serial = None

    def open(self) -> None:
        """Open the serial port (8N1) and flush its buffers."""
        self._serial = self._serial_factory(
            port=self._port,
            baudrate=self._baudrate,
            bytesize=pyserial.EIGHTBITS,
            parity=pyserial.PARITY_NONE,
            stopbits=pyserial.STOPBITS_ONE,
            timeout=self._timeout,
        )
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()

    def close(self) -> None:
        """Close the serial port if it is open."""
        if self._serial is not None and self._serial.is_open:
            self._serial.close()
        self._serial = None

    def write(self, data: bytes) -> None:
        """Write *data* (a 64-byte work unit) to the device.

        Raises:
            BFLConnectionError: If the transport is not open.
        """
        if not self.is_open:
            raise BFLConnectionError("Transport is not open")
        self._serial.write(data)

    def read(self, size: int, timeout: float | None = None) -> bytes:
        """Read up to *size* bytes (a 4-byte nonce), optionally overriding
        the default timeout for this one call.

        Raises:
            BFLConnectionError: If the transport is not open.
        """
        if not self.is_open:
            raise BFLConnectionError("Transport is not open")
        old_timeout = self._serial.timeout
        if timeout is not None:
            self._serial.timeout = timeout
        try:
            return self._serial.read(size)
        finally:
            self._serial.timeout = old_timeout

    def readline(self, timeout: float | None = None) -> bytes:
        """Read whatever is currently available.

        Icarus has no line framing (nonces are fixed-width); this exists only
        to satisfy the transport interface. Delegates to the serial object's
        ``readline`` so callers that expect the method do not break.
        """
        if not self.is_open:
            raise BFLConnectionError("Transport is not open")
        old_timeout = self._serial.timeout
        if timeout is not None:
            self._serial.timeout = timeout
        try:
            return self._serial.readline()
        finally:
            self._serial.timeout = old_timeout

    def flush_input(self) -> None:
        """Discard buffered inbound bytes (stale nonces from a prior work)."""
        if self._serial is not None and self._serial.is_open:
            self._serial.reset_input_buffer()

    @property
    def is_open(self) -> bool:
        """``True`` if the underlying serial port is open."""
        return self._serial is not None and self._serial.is_open

    @property
    def port(self) -> str:
        """The serial port path passed to the constructor."""
        return self._port
