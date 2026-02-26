"""Tests for the simulator transport: SimulatedDevice and SimulatorTransport."""

from __future__ import annotations

import re

import pytest

from bfl_asic.exceptions import BFLConnectionError
from bfl_asic.protocol.constants import DELIMITER
from bfl_asic.transport.simulator import (
    DeviceState,
    SimulatedDevice,
    SimulatorTransport,
)


# ======================================================================
# Helpers
# ======================================================================


def _make_work_packet(midstate: bytes | None = None, tail: bytes | None = None) -> bytes:
    """Build a 60-byte work packet: DELIMITER + midstate(32) + tail(12) + DELIMITER."""
    if midstate is None:
        midstate = b"\x01" * 32
    if tail is None:
        tail = b"\x02" * 12
    return DELIMITER + midstate + tail + DELIMITER


# ======================================================================
# DeviceState enum
# ======================================================================


class TestDeviceState:
    def test_has_idle(self):
        assert DeviceState.IDLE is not None

    def test_has_hashing(self):
        assert DeviceState.HASHING is not None

    def test_has_overheated(self):
        assert DeviceState.OVERHEATED is not None


# ======================================================================
# SimulatedDevice tests
# ======================================================================


class TestSimulatedDeviceInitialState:
    def test_initial_state_is_idle(self):
        dev = SimulatedDevice()
        assert dev.state is DeviceState.IDLE

    def test_initial_temperature(self):
        dev = SimulatedDevice(base_temperature=40.0)
        assert dev.temperature == 40.0

    def test_default_temperature(self):
        dev = SimulatedDevice()
        assert dev.temperature == 35.0

    def test_no_current_work(self):
        dev = SimulatedDevice()
        assert dev.current_work is None

    def test_no_found_nonces(self):
        dev = SimulatedDevice()
        assert dev.found_nonces == []

    def test_work_not_complete(self):
        dev = SimulatedDevice()
        assert dev.work_complete is False


class TestSimulatedDeviceIdentify:
    def test_identify_command(self):
        dev = SimulatedDevice()
        resp = dev.process_command(b"ZGX")
        assert b"SHA256" in resp
        assert b"Jalapeno" in resp

    def test_identify_ends_with_newline(self):
        dev = SimulatedDevice()
        resp = dev.process_command(b"ZGX")
        assert resp.endswith(b"\n")

    def test_identify_contains_device_info(self):
        dev = SimulatedDevice()
        resp = dev.process_command(b"ZGX")
        assert resp == b"BitFORCE SHA256 ASIC Jalapeno 5GH/s\n"


class TestSimulatedDeviceTemperature:
    def test_temperature_command(self):
        dev = SimulatedDevice()
        resp = dev.process_command(b"ZTX")
        assert resp.startswith(b"TEMP0:")
        assert resp.endswith(b"C\n")

    def test_temperature_format(self):
        dev = SimulatedDevice(base_temperature=42.5)
        resp = dev.process_command(b"ZTX")
        assert resp == b"TEMP0:42.5C\n"

    def test_temperature_one_decimal(self):
        dev = SimulatedDevice(base_temperature=35.0)
        resp = dev.process_command(b"ZTX")
        # Should be formatted to 1 decimal place
        assert b"35.0" in resp


class TestSimulatedDeviceWork:
    def test_submit_work(self):
        dev = SimulatedDevice()
        packet = _make_work_packet()
        resp = dev.process_command(packet)
        assert resp == b"OK\n"

    def test_state_after_work_submission(self):
        """After work submission, state should be HASHING (or OVERHEATED if
        temp exceeded, but under normal conditions it's HASHING)."""
        dev = SimulatedDevice()
        packet = _make_work_packet()
        dev.process_command(packet)
        assert dev.state in (DeviceState.HASHING, DeviceState.OVERHEATED)

    def test_work_is_complete_after_submission(self):
        """Since mining is synchronous, work_complete should be True after
        process_command returns."""
        dev = SimulatedDevice()
        packet = _make_work_packet()
        dev.process_command(packet)
        assert dev.work_complete is True

    def test_current_work_is_set(self):
        dev = SimulatedDevice()
        midstate = b"\xaa" * 32
        tail = b"\xbb" * 12
        packet = _make_work_packet(midstate, tail)
        dev.process_command(packet)
        assert dev.current_work is not None
        assert dev.current_work[0] == midstate
        assert dev.current_work[1] == tail

    def test_zdx_prefix_work(self):
        """Work submitted with a ZDX prefix should also be accepted."""
        dev = SimulatedDevice()
        packet = b"ZDX" + _make_work_packet()
        resp = dev.process_command(packet)
        assert resp == b"OK\n"


class TestSimulatedDevicePoll:
    def test_poll_when_idle(self):
        dev = SimulatedDevice()
        resp = dev.process_command(b"ZFX")
        assert resp == b"IDLE\n"

    def test_poll_after_work(self):
        """After submitting work, polling should return NONCE-FOUND or NO-NONCE."""
        dev = SimulatedDevice()
        packet = _make_work_packet()
        dev.process_command(packet)
        resp = dev.process_command(b"ZFX")
        text = resp.decode().strip()
        assert text.startswith("NONCE-FOUND:") or text == "NO-NONCE"

    def test_poll_resets_to_idle(self):
        """After reading the result, the device should return to IDLE."""
        dev = SimulatedDevice()
        packet = _make_work_packet()
        dev.process_command(packet)
        dev.process_command(b"ZFX")  # read result
        assert dev.state is DeviceState.IDLE

    def test_poll_clears_work(self):
        dev = SimulatedDevice()
        packet = _make_work_packet()
        dev.process_command(packet)
        dev.process_command(b"ZFX")
        assert dev.current_work is None


class TestSimulatedDeviceNonceFormat:
    def test_nonce_format(self):
        """If nonces are found, they should be 8-char zero-padded hex strings."""
        dev = SimulatedDevice(simulated_hashrate=5000)
        packet = _make_work_packet()
        dev.process_command(packet)
        resp = dev.process_command(b"ZFX")
        text = resp.decode().strip()
        if text.startswith("NONCE-FOUND:"):
            nonce_str = text[len("NONCE-FOUND:"):]
            parts = nonce_str.split(",")
            for part in parts:
                assert len(part) == 8, f"Nonce {part!r} is not 8 chars"
                assert re.fullmatch(r"[0-9a-f]{8}", part), (
                    f"Nonce {part!r} is not valid hex"
                )

    def test_found_nonces_are_valid(self):
        """Each found nonce should produce a SHA-256d hash with first byte 0x00."""
        import hashlib

        dev = SimulatedDevice(simulated_hashrate=5000)
        midstate = b"\x01" * 32
        tail = b"\x02" * 12
        packet = _make_work_packet(midstate, tail)
        dev.process_command(packet)

        for nonce in dev.found_nonces:
            nonce_bytes = nonce.to_bytes(4, "big")
            h1 = hashlib.sha256(midstate + tail + nonce_bytes).digest()
            h2 = hashlib.sha256(h1).digest()
            assert h2[0] == 0x00, f"Nonce {nonce} does not produce leading zero byte"


class TestSimulatedDeviceThermal:
    def test_temperature_rises_after_work(self):
        dev = SimulatedDevice(base_temperature=35.0, heat_per_work=5.0)
        initial = dev.temperature
        packet = _make_work_packet()
        dev.process_command(packet)
        assert dev.temperature > initial
        assert dev.temperature == initial + 5.0

    def test_overheated_rejects_work(self):
        dev = SimulatedDevice(overheat_threshold=85.0)
        dev.temperature = 90.0
        dev.state = DeviceState.OVERHEATED
        packet = _make_work_packet()
        resp = dev.process_command(packet)
        assert resp == b"ERR:OVERHEATED\n"

    def test_cooling_on_idle_poll(self):
        """Polling for results when work is done should cool the device."""
        dev = SimulatedDevice(base_temperature=35.0, cooling_rate=2.0)
        packet = _make_work_packet()
        dev.process_command(packet)
        temp_after_work = dev.temperature
        dev.process_command(b"ZFX")  # read result, triggers cooling
        assert dev.temperature < temp_after_work

    def test_temperature_does_not_drop_below_base(self):
        dev = SimulatedDevice(base_temperature=35.0, cooling_rate=100.0)
        dev.temperature = 36.0
        dev.state = DeviceState.HASHING
        dev.work_complete = True
        dev.current_work = (b"\x00" * 32, b"\x00" * 12)
        dev.process_command(b"ZFX")
        assert dev.temperature >= dev.base_temperature

    def test_overheated_recovery(self):
        """Device should recover from OVERHEATED once temp drops enough."""
        dev = SimulatedDevice(
            overheat_threshold=85.0, cooling_rate=50.0, base_temperature=35.0
        )
        dev.temperature = 80.0
        dev.state = DeviceState.OVERHEATED
        # Poll to trigger cooling: 80 - 50 = 35 (< 85 - 10 = 75)
        dev.process_command(b"ZFX")
        assert dev.state is DeviceState.IDLE

    def test_overheated_stays_hot(self):
        """Device should stay OVERHEATED if temp doesn't drop far enough."""
        dev = SimulatedDevice(
            overheat_threshold=85.0, cooling_rate=0.5, base_temperature=35.0
        )
        dev.temperature = 84.0
        dev.state = DeviceState.OVERHEATED
        # 84 - 0.5 = 83.5, threshold - 10 = 75.  83.5 > 75, so stays overheated.
        dev.process_command(b"ZFX")
        assert dev.state is DeviceState.OVERHEATED

    def test_work_triggers_overheat(self):
        dev = SimulatedDevice(
            base_temperature=84.0, heat_per_work=2.0, overheat_threshold=85.0
        )
        packet = _make_work_packet()
        dev.process_command(packet)
        assert dev.state is DeviceState.OVERHEATED


class TestSimulatedDeviceUnknownCommand:
    def test_unknown_command(self):
        dev = SimulatedDevice()
        resp = dev.process_command(b"XYZABC")
        assert resp == b"ERR:UNKNOWN\n"

    def test_empty_command(self):
        dev = SimulatedDevice()
        resp = dev.process_command(b"")
        assert resp == b"ERR:UNKNOWN\n"


class TestSimulatedDeviceErrorInjection:
    def test_error_rate_zero_no_garble(self):
        dev = SimulatedDevice(error_rate=0.0)
        # Should always return the same response.
        resp = dev.process_command(b"ZGX")
        assert resp == b"BitFORCE SHA256 ASIC Jalapeno 5GH/s\n"

    def test_error_rate_one_always_garbles(self):
        """With error_rate=1.0, every response should be garbled."""
        dev = SimulatedDevice(error_rate=1.0)
        # Run multiple times -- at least one should differ from the clean version.
        clean = b"BitFORCE SHA256 ASIC Jalapeno 5GH/s\n"
        garbled_count = 0
        for _ in range(20):
            resp = dev.process_command(b"ZGX")
            if resp != clean:
                garbled_count += 1
        # With error_rate=1.0, all should be garbled (single bit flip always changes).
        assert garbled_count == 20


# ======================================================================
# SimulatorTransport tests
# ======================================================================


class TestSimulatorTransportLifecycle:
    def test_is_closed_initially(self):
        t = SimulatorTransport()
        assert t.is_open is False

    def test_open_and_close(self):
        t = SimulatorTransport()
        t.open()
        assert t.is_open is True
        t.close()
        assert t.is_open is False

    def test_close_clears_buffer(self):
        t = SimulatorTransport()
        t.open()
        t.write(b"ZGX")
        t.close()
        # Re-open; buffer should be empty.
        t.open()
        data = t.read(100)
        assert data == b""


class TestSimulatorTransportErrors:
    def test_write_raises_when_closed(self):
        t = SimulatorTransport()
        with pytest.raises(BFLConnectionError, match="not open"):
            t.write(b"ZGX")

    def test_read_raises_when_closed(self):
        t = SimulatorTransport()
        with pytest.raises(BFLConnectionError, match="not open"):
            t.read(10)

    def test_readline_raises_when_closed(self):
        t = SimulatorTransport()
        with pytest.raises(BFLConnectionError, match="not open"):
            t.readline()


class TestSimulatorTransportRoundTrips:
    def test_identify_round_trip(self):
        t = SimulatorTransport()
        t.open()
        t.write(b"ZGX")
        resp = t.readline()
        assert b"SHA256" in resp
        assert b"Jalapeno" in resp

    def test_temperature_round_trip(self):
        t = SimulatorTransport()
        t.open()
        t.write(b"ZTX")
        resp = t.readline()
        assert resp.startswith(b"TEMP0:")
        assert resp.endswith(b"C\n")

    def test_work_round_trip(self):
        t = SimulatorTransport()
        t.open()
        packet = _make_work_packet()
        t.write(packet)
        ok_resp = t.readline()
        assert ok_resp == b"OK\n"

        t.write(b"ZFX")
        result_resp = t.readline()
        text = result_resp.decode().strip()
        assert text.startswith("NONCE-FOUND:") or text == "NO-NONCE"

    def test_read_partial(self):
        t = SimulatorTransport()
        t.open()
        t.write(b"ZGX")
        # Read only 5 bytes at a time.
        chunk1 = t.read(5)
        chunk2 = t.read(100)
        full = chunk1 + chunk2
        assert b"SHA256" in full

    def test_readline_no_newline(self):
        """If the buffer has no newline, readline returns everything."""
        t = SimulatorTransport()
        t.open()
        # Manually inject partial data (no newline).
        t._response_buffer = b"partial"
        data = t.readline()
        assert data == b"partial"
        assert t._response_buffer == b""


class TestSimulatorTransportContextManager:
    def test_context_manager(self):
        t = SimulatorTransport()
        with t:
            assert t.is_open is True
            t.write(b"ZGX")
            resp = t.readline()
            assert b"Jalapeno" in resp
        assert t.is_open is False

    def test_context_manager_exception_cleanup(self):
        t = SimulatorTransport()
        with pytest.raises(RuntimeError):
            with t:
                assert t.is_open is True
                raise RuntimeError("test error")
        assert t.is_open is False


class TestSimulatorTransportDevice:
    def test_device_property(self):
        dev = SimulatedDevice(base_temperature=50.0)
        t = SimulatorTransport(device=dev)
        assert t.device is dev
        assert t.device.temperature == 50.0

    def test_default_device(self):
        t = SimulatorTransport()
        assert isinstance(t.device, SimulatedDevice)

    def test_device_state_accessible(self):
        t = SimulatorTransport()
        t.open()
        assert t.device.state is DeviceState.IDLE
        packet = _make_work_packet()
        t.write(packet)
        # State should have changed (HASHING or OVERHEATED after work).
        assert t.device.state in (DeviceState.HASHING, DeviceState.OVERHEATED)


class TestSimulatorTransportAsync:
    """Verify that the async methods work (inherited from BaseTransport)."""

    async def test_async_open_close(self):
        t = SimulatorTransport()
        await t.aopen()
        assert t.is_open is True
        await t.aclose()
        assert t.is_open is False

    async def test_async_write_read(self):
        t = SimulatorTransport()
        await t.aopen()
        await t.awrite(b"ZGX")
        resp = await t.areadline()
        assert b"Jalapeno" in resp
        await t.aclose()

    async def test_async_context_manager(self):
        t = SimulatorTransport()
        async with t:
            assert t.is_open is True
            await t.awrite(b"ZTX")
            resp = await t.areadline()
            assert resp.startswith(b"TEMP0:")
        assert t.is_open is False


# ======================================================================
# Package re-export tests
# ======================================================================


class TestSimulatorPackageExports:
    def test_simulated_device_importable(self):
        from bfl_asic.transport import SimulatedDevice
        assert SimulatedDevice is not None

    def test_simulator_transport_importable(self):
        from bfl_asic.transport import SimulatorTransport
        assert SimulatorTransport is not None
