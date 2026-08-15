"""Tests for the synchronous BFLDevice API against SimulatorTransport."""

from __future__ import annotations

import pytest

from bfl_asic.device import BFLDevice
from bfl_asic.protocol.responses import (
    DeviceInfo,
    TemperatureReading,
    WorkResult,
    WorkStatus,
)
from bfl_asic.protocol.work import build_synthetic_work
from bfl_asic.transport.simulator import SimulatorTransport


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def device():
    """Provide a BFLDevice backed by an opened SimulatorTransport."""
    transport = SimulatorTransport()
    transport.open()
    yield BFLDevice(transport)
    transport.close()


# ======================================================================
# Identify
# ======================================================================


class TestIdentify:
    def test_identify_returns_device_info(self, device: BFLDevice):
        info = device.identify()
        assert isinstance(info, DeviceInfo)

    def test_identify_sha256_flag(self, device: BFLDevice):
        info = device.identify()
        assert info.sha256 is True

    def test_identify_model_string(self, device: BFLDevice):
        info = device.identify()
        assert "Jalapeno" in info.model

    def test_identify_raw_field(self, device: BFLDevice):
        info = device.identify()
        assert "SHA256" in info.raw


# ======================================================================
# Temperature
# ======================================================================


class TestGetTemperature:
    def test_returns_temperature_reading(self, device: BFLDevice):
        reading = device.get_temperature()
        assert isinstance(reading, TemperatureReading)

    def test_has_sensor_values(self, device: BFLDevice):
        reading = device.get_temperature()
        assert len(reading.sensors) >= 1

    def test_sensor_value_is_float(self, device: BFLDevice):
        reading = device.get_temperature()
        assert isinstance(reading.sensors[0], float)

    def test_sensor_value_reasonable(self, device: BFLDevice):
        reading = device.get_temperature()
        # Default base temp is 35.0
        assert 0.0 < reading.sensors[0] < 150.0


# ======================================================================
# Submit work
# ======================================================================


class TestSubmitWork:
    def test_submit_work_does_not_raise(self, device: BFLDevice):
        midstate, tail = build_synthetic_work(b"\x00" * 64)
        device.submit_work(midstate, tail)

    def test_submit_work_multiple_times(self, device: BFLDevice):
        """Submitting multiple work units should not raise."""
        for i in range(3):
            seed = (i).to_bytes(1, "big").ljust(64, b"\x00")
            midstate, tail = build_synthetic_work(seed)
            device.submit_work(midstate, tail)


# ======================================================================
# Poll result
# ======================================================================


class TestPollResult:
    def test_poll_when_idle(self, device: BFLDevice):
        result = device.poll_result()
        assert result.status == WorkStatus.IDLE

    def test_poll_after_work(self, device: BFLDevice):
        midstate, tail = build_synthetic_work(b"\x00" * 64)
        device.submit_work(midstate, tail)
        result = device.poll_result()
        assert result.status in (WorkStatus.NONCE_FOUND, WorkStatus.NO_NONCE)


# ======================================================================
# Submit and wait
# ======================================================================


class TestSubmitAndWait:
    def test_returns_work_result(self, device: BFLDevice):
        midstate, tail = build_synthetic_work(b"\x00" * 64)
        result = device.submit_and_wait(midstate, tail)
        assert isinstance(result, WorkResult)

    def test_result_not_busy(self, device: BFLDevice):
        midstate, tail = build_synthetic_work(b"\x00" * 64)
        result = device.submit_and_wait(midstate, tail)
        assert result.status != WorkStatus.BUSY

    def test_result_is_nonce_found_or_no_nonce(self, device: BFLDevice):
        midstate, tail = build_synthetic_work(b"\x00" * 64)
        result = device.submit_and_wait(midstate, tail)
        assert result.status in (WorkStatus.NONCE_FOUND, WorkStatus.NO_NONCE)

    def test_returns_nonces_list(self, device: BFLDevice):
        """The result should have a nonces list (possibly empty)."""
        midstate, tail = build_synthetic_work(b"\x00" * 64)
        result = device.submit_and_wait(midstate, tail)
        assert isinstance(result.nonces, list)

    def test_nonces_are_ints(self, device: BFLDevice):
        """Each nonce should be an integer."""
        midstate, tail = build_synthetic_work(b"\x01" * 64)
        result = device.submit_and_wait(midstate, tail)
        for nonce in result.nonces:
            assert isinstance(nonce, int)


# ======================================================================
# hash_data
# ======================================================================


class TestHashData:
    def test_returns_list_of_ints(self, device: BFLDevice):
        nonces = device.hash_data(b"hello world")
        assert isinstance(nonces, list)
        for n in nonces:
            assert isinstance(n, int)

    def test_with_short_data(self, device: BFLDevice):
        """Short data should be padded and not raise."""
        nonces = device.hash_data(b"\x42")
        assert isinstance(nonces, list)

    def test_with_64_byte_data(self, device: BFLDevice):
        """Exact 64-byte input should work directly."""
        nonces = device.hash_data(b"\xaa" * 64)
        assert isinstance(nonces, list)

    def test_with_long_data(self, device: BFLDevice):
        """Data longer than 64 bytes should be truncated."""
        nonces = device.hash_data(b"\xbb" * 128)
        assert isinstance(nonces, list)


# ======================================================================
# generate_entropy
# ======================================================================


class TestGenerateEntropy:
    def test_returns_bytes(self, device: BFLDevice):
        result = device.generate_entropy(16)
        assert isinstance(result, bytes)

    def test_exact_length(self, device: BFLDevice):
        for length in (1, 4, 16, 32, 64):
            result = device.generate_entropy(length)
            assert len(result) == length, (
                f"Expected {length} bytes, got {len(result)}"
            )

    def test_nonzero_entropy(self, device: BFLDevice):
        """Entropy should not be all zeros (extremely unlikely)."""
        result = device.generate_entropy(32)
        assert result != b"\x00" * 32

    def test_small_entropy(self, device: BFLDevice):
        result = device.generate_entropy(1)
        assert len(result) == 1


# ======================================================================
# Context manager
# ======================================================================


class TestContextManager:
    def test_opens_and_closes_transport(self):
        transport = SimulatorTransport()
        assert transport.is_open is False
        with BFLDevice(transport) as dev:
            assert transport.is_open is True
            info = dev.identify()
            assert isinstance(info, DeviceInfo)
        assert transport.is_open is False

    def test_closes_on_exception(self):
        transport = SimulatorTransport()
        with pytest.raises(RuntimeError):
            with BFLDevice(transport):
                assert transport.is_open is True
                raise RuntimeError("test")
        assert transport.is_open is False


# ======================================================================
# Transport property
# ======================================================================


class TestTransportProperty:
    def test_access_transport(self, device: BFLDevice):
        assert isinstance(device.transport, SimulatorTransport)

    def test_transport_is_open(self, device: BFLDevice):
        assert device.transport.is_open is True

    def test_transport_is_same_instance(self):
        transport = SimulatorTransport()
        dev = BFLDevice(transport)
        assert dev.transport is transport


# ======================================================================
# Details census
# ======================================================================


class TestDetails:
    def test_get_details_returns_census(self, device: BFLDevice):
        from bfl_asic.protocol.queued import DeviceDetails
        det = device.get_details()
        assert isinstance(det, DeviceDetails)
        assert det.device == "BitFORCE SC"
        assert det.firmware == "1.0.0"
        assert det.engines == 30
        assert det.frequency == "[UNKNOWN]"

    def test_get_details_reads_full_multiline_reply(self, device: BFLDevice):
        # A single readline() would only capture DEVICE:; the census must
        # consume the whole reply through to OK.
        det = device.get_details()
        assert det.xlink_mode == "MASTER"
        assert det.chain_presence_mask == "00000000"
        assert det.jobs_in_queue == 0


# ======================================================================
# Probe commands (ZJX/ZUX/ZSX)
# ======================================================================


class TestProbeCommands:
    def test_get_firmware(self, device: BFLDevice):
        from bfl_asic.protocol.probe import FirmwareInfo
        fw = device.get_firmware()
        assert isinstance(fw, FirmwareInfo)
        assert fw.version == "1.0.0"

    def test_nvram_note_roundtrip(self, device: BFLDevice):
        assert device.read_note() == ""
        assert device.write_note("hello silicon") is True
        assert device.read_note() == "hello silicon"

    def test_write_note_warns_nvram(self, device: BFLDevice):
        import warnings
        from bfl_asic.exceptions import NVRAMWriteWarning
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            device.write_note("x")
        assert any(issubclass(c.category, NVRAMWriteWarning) for c in caught)


# ======================================================================
# Package-level import
# ======================================================================


class TestPackageExport:
    def test_importable_from_package(self):
        from bfl_asic import BFLDevice as Imported
        assert Imported is BFLDevice
