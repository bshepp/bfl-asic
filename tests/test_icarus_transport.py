"""Behavioral tests for the real-hardware Icarus serial transport.

The transport wraps pyserial, so it is driven here against a *fake* serial
port (``FakeIcarusSerial``) that stands in for the chip at the byte level:
it accumulates 64-byte work units and answers each with the deterministic
nonce a real Icarus device would return (reusing ``SimulatedIcarusDevice``).
That lets every behaviour be asserted headless; the live-hardware run is the
integration proof. Dependency injection is via the ``serial_factory`` seam.
"""
import pytest

from bfl_asic.exceptions import BFLConnectionError
from bfl_asic.protocol.icarus import (
    GOLDEN_NONCE, GOLDEN_WORK, NONCE_SIZE, WORK_SIZE, build_work, parse_nonce,
)
from bfl_asic.transport.icarus_serial import IcarusSerialTransport
from bfl_asic.transport.icarus_simulator import SimulatedIcarusDevice


class FakeIcarusSerial:
    """A pyserial-shaped double that behaves like an Icarus chip on the wire."""

    def __init__(self, **kwargs):
        self.init_kwargs = kwargs
        self.timeout = kwargs.get("timeout")
        self.timeout_at_read = "unset"
        self.is_open = True
        self.reset_input_calls = 0
        self.reset_output_calls = 0
        self._device = SimulatedIcarusDevice()
        self._in = b""      # bytes available to read (nonces)
        self._work = b""    # accumulated inbound work

    def read(self, size):
        self.timeout_at_read = self.timeout
        data, self._in = self._in[:size], self._in[size:]
        return data

    def write(self, data):
        self._work += data
        while len(self._work) >= WORK_SIZE:
            unit, self._work = self._work[:WORK_SIZE], self._work[WORK_SIZE:]
            self._in += self._device.process_work(unit)

    def reset_input_buffer(self):
        self.reset_input_calls += 1
        self._in = b""

    def reset_output_buffer(self):
        self.reset_output_calls += 1

    def close(self):
        self.is_open = False


def _open_transport(timeout=11.0):
    t = IcarusSerialTransport("COM-TEST", timeout=timeout,
                              serial_factory=FakeIcarusSerial)
    t.open()
    return t


def test_is_open_false_until_open_then_true_until_close():
    t = IcarusSerialTransport("COM-TEST", serial_factory=FakeIcarusSerial)
    assert t.is_open is False
    t.open()
    assert t.is_open is True
    t.close()
    assert t.is_open is False


def test_write_before_open_raises_connection_error():
    t = IcarusSerialTransport("COM-TEST", serial_factory=FakeIcarusSerial)
    with pytest.raises(BFLConnectionError):
        t.write(GOLDEN_WORK)


def test_read_before_open_raises_connection_error():
    t = IcarusSerialTransport("COM-TEST", serial_factory=FakeIcarusSerial)
    with pytest.raises(BFLConnectionError):
        t.read(NONCE_SIZE)


def test_open_uses_8n1_and_resets_buffers():
    t = _open_transport(timeout=7.5)
    kw = t._serial.init_kwargs
    assert kw["baudrate"] == 115200
    assert kw["bytesize"] == 8
    assert kw["parity"] == "N"
    assert kw["stopbits"] == 1
    assert kw["timeout"] == 7.5
    assert t._serial.reset_input_calls == 1
    assert t._serial.reset_output_calls == 1


def test_write_then_read_returns_device_nonce():
    t = _open_transport()
    t.write(GOLDEN_WORK)
    raw = t.read(NONCE_SIZE)
    assert raw == GOLDEN_NONCE.to_bytes(NONCE_SIZE, "big")
    assert parse_nonce(raw) == GOLDEN_NONCE


def test_read_timeout_override_applied_then_restored():
    t = _open_transport(timeout=11.0)
    t.write(GOLDEN_WORK)
    t.read(NONCE_SIZE, timeout=5.0)
    assert t._serial.timeout_at_read == 5.0   # override in effect during read
    assert t._serial.timeout == 11.0          # restored afterwards


def test_flush_input_resets_input_buffer():
    t = _open_transport()
    t.write(GOLDEN_WORK)          # queues a nonce in the fake's input buffer
    t.flush_input()
    assert t._serial.reset_input_calls == 2   # once at open, once here
    assert t.read(NONCE_SIZE) == b""          # buffer was cleared


def test_close_marks_not_open_and_closes_port():
    t = _open_transport()
    port = t._serial
    t.close()
    assert t.is_open is False
    assert port.is_open is False


def test_icarus_nonce_source_over_serial_transport_yields_golden_nonce():
    from bfl_asic.nonce_source import IcarusNonceSource

    midstate = GOLDEN_WORK[:32][::-1]
    data = GOLDEN_WORK[52:64][::-1]
    assert build_work(midstate, data) == GOLDEN_WORK  # guard the reconstruction

    t = IcarusSerialTransport("COM-TEST", serial_factory=FakeIcarusSerial)
    src = IcarusNonceSource(t, work_iter=[(midstate, data)])
    results = list(src.results(count=1))

    assert len(results) == 1
    assert results[0].nonces == [GOLDEN_NONCE]
