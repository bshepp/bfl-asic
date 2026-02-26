"""Tests for the transport layer: base ABC, serial transport, and discovery."""

from __future__ import annotations

import asyncio
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from bfl_asic.exceptions import BFLConnectionError
from bfl_asic.transport.base import BaseTransport
from bfl_asic.transport.discovery import FTDI_VID, DevicePort, discover_devices
from bfl_asic.transport.serial import SerialTransport


# ======================================================================
# Helpers: a minimal concrete transport for testing the ABC
# ======================================================================


class MemoryTransport(BaseTransport):
    """In-memory transport backed by byte buffers, for testing."""

    def __init__(self) -> None:
        self._open = False
        self._in_buf = BytesIO()
        self._out_buf = BytesIO()

    def open(self) -> None:
        self._open = True

    def close(self) -> None:
        self._open = False

    def write(self, data: bytes) -> None:
        self._out_buf.write(data)

    def read(self, size: int, timeout: float | None = None) -> bytes:
        return self._in_buf.read(size)

    def readline(self, timeout: float | None = None) -> bytes:
        return self._in_buf.readline()

    @property
    def is_open(self) -> bool:
        return self._open

    # Helper to feed data into the read side
    def feed(self, data: bytes) -> None:
        pos = self._in_buf.tell()
        self._in_buf.seek(0, 2)  # seek to end
        self._in_buf.write(data)
        self._in_buf.seek(pos)


# ======================================================================
# BaseTransport ABC
# ======================================================================


class TestBaseTransportABC:
    """Verify that BaseTransport is abstract and enforces its contract."""

    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseTransport()  # type: ignore[abstract]

    def test_partial_implementation_raises(self):
        """A subclass that only implements *some* abstract methods cannot
        be instantiated."""

        class Partial(BaseTransport):
            def open(self) -> None: ...
            def close(self) -> None: ...
            # missing write, read, readline, is_open

        with pytest.raises(TypeError):
            Partial()  # type: ignore[abstract]

    def test_concrete_subclass_instantiates(self):
        transport = MemoryTransport()
        assert isinstance(transport, BaseTransport)


# ======================================================================
# MemoryTransport (concrete subclass) — exercises the ABC API
# ======================================================================


class TestMemoryTransport:
    """Use the MemoryTransport helper to exercise the base class interface."""

    def test_is_open_initially_false(self):
        t = MemoryTransport()
        assert t.is_open is False

    def test_open_sets_is_open(self):
        t = MemoryTransport()
        t.open()
        assert t.is_open is True

    def test_close_clears_is_open(self):
        t = MemoryTransport()
        t.open()
        t.close()
        assert t.is_open is False

    def test_write_and_read_buffer(self):
        t = MemoryTransport()
        t.open()
        t.write(b"hello")
        assert t._out_buf.getvalue() == b"hello"

    def test_feed_and_read(self):
        t = MemoryTransport()
        t.open()
        t.feed(b"world")
        assert t.read(5) == b"world"

    def test_feed_and_readline(self):
        t = MemoryTransport()
        t.open()
        t.feed(b"line1\nline2\n")
        assert t.readline() == b"line1\n"
        assert t.readline() == b"line2\n"


# ======================================================================
# Context managers
# ======================================================================


class TestSyncContextManager:
    def test_enter_calls_open(self):
        t = MemoryTransport()
        assert t.is_open is False
        with t:
            assert t.is_open is True
        assert t.is_open is False

    def test_exit_returns_false(self):
        """__exit__ must not suppress exceptions."""
        t = MemoryTransport()
        result = t.__exit__(None, None, None)
        assert result is False

    def test_exception_propagates(self):
        t = MemoryTransport()
        with pytest.raises(ValueError, match="boom"):
            with t:
                raise ValueError("boom")
        # transport is still closed after exception
        assert t.is_open is False


class TestAsyncContextManager:
    async def test_aenter_calls_aopen(self):
        t = MemoryTransport()
        assert t.is_open is False
        async with t:
            assert t.is_open is True
        assert t.is_open is False

    async def test_aexit_returns_false(self):
        t = MemoryTransport()
        result = await t.__aexit__(None, None, None)
        assert result is False


# ======================================================================
# Async default implementations
# ======================================================================


class TestAsyncDefaults:
    """Verify that the default async methods delegate to sync ones."""

    async def test_aopen_delegates(self):
        t = MemoryTransport()
        await t.aopen()
        assert t.is_open is True

    async def test_aclose_delegates(self):
        t = MemoryTransport()
        t.open()
        await t.aclose()
        assert t.is_open is False

    async def test_awrite_delegates(self):
        t = MemoryTransport()
        t.open()
        await t.awrite(b"async hello")
        assert t._out_buf.getvalue() == b"async hello"

    async def test_aread_delegates(self):
        t = MemoryTransport()
        t.open()
        t.feed(b"async world")
        data = await t.aread(11)
        assert data == b"async world"

    async def test_areadline_delegates(self):
        t = MemoryTransport()
        t.open()
        t.feed(b"async line\n")
        line = await t.areadline()
        assert line == b"async line\n"


# ======================================================================
# SerialTransport — constructor and pre-open state
# ======================================================================


class TestSerialTransportConstructor:
    def test_stores_port(self):
        t = SerialTransport(port="/dev/ttyUSB0")
        assert t.port == "/dev/ttyUSB0"

    def test_stores_custom_port(self):
        t = SerialTransport(port="COM3")
        assert t.port == "COM3"

    def test_default_baudrate(self):
        t = SerialTransport(port="/dev/ttyUSB0")
        assert t._baudrate == 115200

    def test_custom_baudrate(self):
        t = SerialTransport(port="/dev/ttyUSB0", baudrate=9600)
        assert t._baudrate == 9600

    def test_is_open_before_open(self):
        t = SerialTransport(port="/dev/ttyUSB0")
        assert t.is_open is False

    def test_serial_is_none_before_open(self):
        t = SerialTransport(port="/dev/ttyUSB0")
        assert t._serial is None


class TestSerialTransportNotOpen:
    """Operations on a closed SerialTransport should raise BFLConnectionError."""

    def test_write_raises_when_not_open(self):
        t = SerialTransport(port="/dev/ttyUSB0")
        with pytest.raises(BFLConnectionError, match="not open"):
            t.write(b"hello")

    def test_read_raises_when_not_open(self):
        t = SerialTransport(port="/dev/ttyUSB0")
        with pytest.raises(BFLConnectionError, match="not open"):
            t.read(10)

    def test_readline_raises_when_not_open(self):
        t = SerialTransport(port="/dev/ttyUSB0")
        with pytest.raises(BFLConnectionError, match="not open"):
            t.readline()


class TestSerialTransportMocked:
    """Test SerialTransport with a mocked pyserial.Serial instance."""

    def _make_transport(self) -> SerialTransport:
        """Create a SerialTransport with a mocked serial connection."""
        t = SerialTransport(port="/dev/ttyUSB0", baudrate=115200)
        mock_serial = MagicMock()
        mock_serial.is_open = True
        mock_serial.timeout = 1.0
        t._serial = mock_serial
        return t

    def test_is_open_with_mock(self):
        t = self._make_transport()
        assert t.is_open is True

    def test_write_calls_serial_write(self):
        t = self._make_transport()
        t.write(b"data")
        t._serial.write.assert_called_once_with(b"data")

    def test_read_calls_serial_read(self):
        t = self._make_transport()
        t._serial.read.return_value = b"resp"
        result = t.read(4)
        t._serial.read.assert_called_once_with(4)
        assert result == b"resp"

    def test_read_with_timeout_override(self):
        t = self._make_transport()
        t._serial.read.return_value = b"x"
        t._serial.timeout = 1.0
        result = t.read(1, timeout=5.0)
        # timeout was set to 5.0 during the call
        assert t._serial.timeout == 1.0  # restored after call

    def test_readline_calls_serial_readline(self):
        t = self._make_transport()
        t._serial.readline.return_value = b"line\n"
        result = t.readline()
        t._serial.readline.assert_called_once()
        assert result == b"line\n"

    def test_readline_with_timeout_override(self):
        t = self._make_transport()
        t._serial.readline.return_value = b"line\n"
        t._serial.timeout = 1.0
        t.readline(timeout=3.0)
        assert t._serial.timeout == 1.0  # restored after call

    def test_close_calls_serial_close(self):
        t = self._make_transport()
        mock_serial = t._serial
        t.close()
        mock_serial.close.assert_called_once()

    def test_close_sets_serial_to_none(self):
        t = self._make_transport()
        t.close()
        assert t._serial is None

    def test_close_when_already_closed(self):
        t = SerialTransport(port="/dev/ttyUSB0")
        # Should not raise
        t.close()
        assert t._serial is None


class TestSerialTransportOpen:
    """Test the open() method with a mocked pyserial module."""

    @patch("bfl_asic.transport.serial.pyserial.Serial")
    def test_open_creates_serial_instance(self, mock_serial_cls):
        mock_instance = MagicMock()
        mock_instance.is_open = True
        mock_serial_cls.return_value = mock_instance

        t = SerialTransport(port="COM3", baudrate=9600)
        t.open()

        mock_serial_cls.assert_called_once()
        call_kwargs = mock_serial_cls.call_args
        assert call_kwargs.kwargs["port"] == "COM3"
        assert call_kwargs.kwargs["baudrate"] == 9600
        mock_instance.reset_input_buffer.assert_called_once()
        mock_instance.reset_output_buffer.assert_called_once()
        assert t.is_open is True


# ======================================================================
# DevicePort dataclass
# ======================================================================


class TestDevicePort:
    def test_fields(self):
        dp = DevicePort(
            port="/dev/ttyUSB0",
            description="FTDI FT232R",
            vid=0x0403,
            pid=0x6001,
        )
        assert dp.port == "/dev/ttyUSB0"
        assert dp.description == "FTDI FT232R"
        assert dp.vid == 0x0403
        assert dp.pid == 0x6001

    def test_vid_pid_can_be_none(self):
        dp = DevicePort(port="COM1", description="Unknown", vid=None, pid=None)
        assert dp.vid is None
        assert dp.pid is None

    def test_equality(self):
        a = DevicePort(port="COM3", description="BFL", vid=0x0403, pid=0x6001)
        b = DevicePort(port="COM3", description="BFL", vid=0x0403, pid=0x6001)
        assert a == b

    def test_ftdi_vid_constant(self):
        assert FTDI_VID == 0x0403


# ======================================================================
# discover_devices()
# ======================================================================


class TestDiscoverDevices:
    def test_returns_list(self):
        """On a CI / dev machine without FTDI hardware, the result is
        still a list (possibly empty)."""
        result = discover_devices()
        assert isinstance(result, list)

    @patch("serial.tools.list_ports.comports")
    def test_discovers_ftdi_device(self, mock_comports):
        fake = MagicMock()
        fake.vid = 0x0403
        fake.pid = 0x6001
        fake.device = "COM3"
        fake.description = "FTDI FT232R"
        mock_comports.return_value = [fake]

        result = discover_devices()
        assert len(result) == 1
        assert result[0].port == "COM3"
        assert result[0].vid == 0x0403

    @patch("serial.tools.list_ports.comports")
    def test_discovers_bfl_by_description(self, mock_comports):
        fake = MagicMock()
        fake.vid = 0x1234  # not FTDI
        fake.pid = 0x5678
        fake.device = "/dev/ttyUSB1"
        fake.description = "Butterfly Labs BitFORCE"
        mock_comports.return_value = [fake]

        result = discover_devices()
        assert len(result) == 1
        assert result[0].description == "Butterfly Labs BitFORCE"

    @patch("serial.tools.list_ports.comports")
    def test_ignores_non_matching_device(self, mock_comports):
        fake = MagicMock()
        fake.vid = 0x1234
        fake.pid = 0x5678
        fake.device = "/dev/ttyS0"
        fake.description = "Generic Serial Port"
        mock_comports.return_value = [fake]

        result = discover_devices()
        assert len(result) == 0

    @patch("serial.tools.list_ports.comports")
    def test_handles_none_description(self, mock_comports):
        fake = MagicMock()
        fake.vid = 0x0403
        fake.pid = 0x6001
        fake.device = "COM5"
        fake.description = None
        mock_comports.return_value = [fake]

        result = discover_devices()
        assert len(result) == 1
        assert result[0].description == ""

    @patch("serial.tools.list_ports.comports")
    def test_multiple_devices(self, mock_comports):
        ftdi = MagicMock()
        ftdi.vid = 0x0403
        ftdi.pid = 0x6001
        ftdi.device = "COM3"
        ftdi.description = "FTDI"

        bfl = MagicMock()
        bfl.vid = 0x9999
        bfl.pid = 0x0001
        bfl.device = "COM4"
        bfl.description = "BFL Miner"

        generic = MagicMock()
        generic.vid = 0x1111
        generic.pid = 0x2222
        generic.device = "COM5"
        generic.description = "Unrelated Device"

        mock_comports.return_value = [ftdi, bfl, generic]

        result = discover_devices()
        assert len(result) == 2
        ports = {d.port for d in result}
        assert ports == {"COM3", "COM4"}

    @patch("serial.tools.list_ports.comports")
    def test_case_insensitive_keyword_match(self, mock_comports):
        fake = MagicMock()
        fake.vid = 0x0000
        fake.pid = 0x0000
        fake.device = "/dev/ttyUSB0"
        fake.description = "BUTTERFLY Labs"
        mock_comports.return_value = [fake]

        result = discover_devices()
        assert len(result) == 1


# ======================================================================
# Package re-exports
# ======================================================================


class TestTransportPackageExports:
    def test_base_transport_importable(self):
        from bfl_asic.transport import BaseTransport
        assert BaseTransport is not None

    def test_serial_transport_importable(self):
        from bfl_asic.transport import SerialTransport
        assert SerialTransport is not None

    def test_device_port_importable(self):
        from bfl_asic.transport import DevicePort
        assert DevicePort is not None

    def test_discover_devices_importable(self):
        from bfl_asic.transport import discover_devices
        assert callable(discover_devices)
