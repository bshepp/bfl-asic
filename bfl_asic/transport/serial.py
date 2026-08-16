"""Serial transport using pyserial for real BFL hardware communication.

Works on both Linux (``/dev/ttyUSB0``) and Windows (``COM3``).
"""

from __future__ import annotations

import serial as pyserial

from bfl_asic.exceptions import BFLConnectionError
from bfl_asic.transport.base import BaseTransport


class SerialTransport(BaseTransport):
    """Transport using a real serial port via pyserial."""

    def __init__(self, port: str, baudrate: int = 115200) -> None:
        """Create a serial transport (does **not** open the port yet).

        Args:
            port: Serial port path (``'/dev/ttyUSB0'`` on Linux,
                  ``'COM3'`` on Windows).
            baudrate: Baud rate.  Default ``115200``.
        """
        self._port = port
        self._baudrate = baudrate
        self._serial: pyserial.Serial | None = None

    # ------------------------------------------------------------------
    # Sync API
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Open the serial port and flush its buffers."""
        self._serial = pyserial.Serial(
            port=self._port,
            baudrate=self._baudrate,
            bytesize=pyserial.EIGHTBITS,
            parity=pyserial.PARITY_NONE,
            stopbits=pyserial.STOPBITS_ONE,
            timeout=1.0,
        )
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()

    def close(self) -> None:
        """Close the serial port if it is open."""
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None

    def write(self, data: bytes) -> None:
        """Write *data* to the serial port.

        Raises:
            BFLConnectionError: If the transport is not open.
        """
        if not self.is_open:
            raise BFLConnectionError("Transport is not open")
        self._serial.write(data)  # type: ignore[union-attr]

    def read(self, size: int, timeout: float | None = None) -> bytes:
        """Read up to *size* bytes, optionally overriding the timeout.

        Raises:
            BFLConnectionError: If the transport is not open.
        """
        if not self.is_open:
            raise BFLConnectionError("Transport is not open")
        assert self._serial is not None  # for type-checker
        old_timeout = self._serial.timeout
        if timeout is not None:
            self._serial.timeout = timeout
        try:
            return self._serial.read(size)
        finally:
            self._serial.timeout = old_timeout

    def readline(self, timeout: float | None = None) -> bytes:
        """Read a newline-terminated line, optionally overriding the timeout.

        Raises:
            BFLConnectionError: If the transport is not open.
        """
        if not self.is_open:
            raise BFLConnectionError("Transport is not open")
        assert self._serial is not None  # for type-checker
        old_timeout = self._serial.timeout
        if timeout is not None:
            self._serial.timeout = timeout
        try:
            return self._serial.readline()
        finally:
            self._serial.timeout = old_timeout

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    def flush_input(self) -> None:
        """Discard buffered inbound bytes (real serial port)."""
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
