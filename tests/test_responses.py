"""Tests for bfl_asic.protocol.responses."""

import pytest

from bfl_asic.exceptions import BFLProtocolError
from bfl_asic.protocol.responses import (
    DeviceInfo,
    TemperatureReading,
    VoltageReading,
    WorkResult,
    WorkStatus,
    parse_identify,
    parse_temperature,
    parse_voltage,
    parse_work_result,
)


# -------------------------------------------------------------------
# parse_identify
# -------------------------------------------------------------------

class TestParseIdentify:
    def test_extracts_model_string(self):
        raw = b"BitFORCE SHA256 ASIC Jalapeno 5GH/s"
        info = parse_identify(raw)
        assert info.model == "BitFORCE SHA256 ASIC Jalapeno 5GH/s"

    def test_sha256_flag_true_when_present(self):
        raw = b"BitFORCE SHA256 ASIC Jalapeno 5GH/s"
        info = parse_identify(raw)
        assert info.sha256 is True

    def test_sha256_flag_false_when_absent(self):
        raw = b"Unknown Device v1.0"
        info = parse_identify(raw)
        assert info.sha256 is False

    def test_raw_preserves_original(self):
        raw = b"BitFORCE SHA256 ASIC Jalapeno 5GH/s"
        info = parse_identify(raw)
        assert info.raw == "BitFORCE SHA256 ASIC Jalapeno 5GH/s"

    def test_strips_whitespace(self):
        raw = b"  BitFORCE SHA256 ASIC  \r\n"
        info = parse_identify(raw)
        assert info.model == "BitFORCE SHA256 ASIC"

    def test_returns_device_info_type(self):
        info = parse_identify(b"test")
        assert isinstance(info, DeviceInfo)

    def test_case_insensitive_sha256_check(self):
        raw = b"BitFORCE sha256 ASIC"
        info = parse_identify(raw)
        assert info.sha256 is True


# -------------------------------------------------------------------
# parse_temperature
# -------------------------------------------------------------------

class TestParseTemperature:
    # -- SC firmware format (ZLX response: "Temp1: 30, Temp2: 30") --

    def test_sc_two_sensors(self):
        raw = b"Temp1: 30, Temp2: 30\n"
        result = parse_temperature(raw)
        assert result.sensors == [30.0, 30.0]

    def test_sc_different_values(self):
        raw = b"Temp1: 45, Temp2: 42\n"
        result = parse_temperature(raw)
        assert result.sensors == [45.0, 42.0]

    def test_sc_single_sensor(self):
        raw = b"Temp1: 55\n"
        result = parse_temperature(raw)
        assert result.sensors == [55.0]

    # -- Older labelled format (TEMP0:45C) --

    def test_labelled_single_sensor(self):
        raw = b"TEMP0:45C"
        result = parse_temperature(raw)
        assert result.sensors == [45.0]

    def test_labelled_two_sensors(self):
        raw = b"TEMP0:45C\nTEMP1:43C"
        result = parse_temperature(raw)
        assert result.sensors == [45.0, 43.0]

    def test_labelled_decimal(self):
        raw = b"TEMP0:45.5C"
        result = parse_temperature(raw)
        assert result.sensors == [45.5]

    def test_returns_temperature_reading_type(self):
        raw = b"Temp1: 30, Temp2: 30\n"
        result = parse_temperature(raw)
        assert isinstance(result, TemperatureReading)

    def test_labelled_with_spaces(self):
        raw = b"TEMP0: 45 C"
        result = parse_temperature(raw)
        assert result.sensors == [45.0]

    def test_raises_on_garbage(self):
        with pytest.raises(BFLProtocolError, match="No temperature data"):
            parse_temperature(b"garbage data")

    def test_raises_on_empty(self):
        with pytest.raises(BFLProtocolError, match="No temperature data"):
            parse_temperature(b"")

    def test_carriage_return_separator(self):
        raw = b"TEMP0:45C\r\nTEMP1:43C"
        result = parse_temperature(raw)
        assert result.sensors == [45.0, 43.0]


# -------------------------------------------------------------------
# parse_voltage
# -------------------------------------------------------------------

class TestParseVoltage:
    def test_three_values(self):
        raw = b"3564,1011,11420\n"
        result = parse_voltage(raw)
        assert result.vcc1 == pytest.approx(3.564)
        assert result.vcc2 == pytest.approx(1.011)
        assert result.vmain == pytest.approx(11.420)

    def test_raw_preserved(self):
        raw = b"3300,1000,12000\n"
        result = parse_voltage(raw)
        assert result.raw == [3300, 1000, 12000]

    def test_returns_voltage_reading_type(self):
        raw = b"3300,1000,12000\n"
        result = parse_voltage(raw)
        assert isinstance(result, VoltageReading)

    def test_with_spaces(self):
        raw = b"3300, 1000, 12000\n"
        result = parse_voltage(raw)
        assert result.vcc1 == pytest.approx(3.3)

    def test_raises_on_non_numeric(self):
        with pytest.raises(BFLProtocolError, match="Unrecognised voltage"):
            parse_voltage(b"TEMP0:45C")

    def test_raises_on_too_few_values(self):
        with pytest.raises(BFLProtocolError, match="Expected 3"):
            parse_voltage(b"3300,1000\n")


# -------------------------------------------------------------------
# parse_work_result
# -------------------------------------------------------------------

class TestParseWorkResult:
    # -- BUSY --
    def test_busy_single_b(self):
        result = parse_work_result(b"B")
        assert result.status == WorkStatus.BUSY
        assert result.nonces == []

    def test_busy_with_extra_data(self):
        result = parse_work_result(b"BUSY")
        assert result.status == WorkStatus.BUSY

    def test_busy_with_trailing_whitespace(self):
        result = parse_work_result(b"B  \n")
        assert result.status == WorkStatus.BUSY

    # -- NO-NONCE --
    def test_no_nonce(self):
        result = parse_work_result(b"NO-NONCE")
        assert result.status == WorkStatus.NO_NONCE
        assert result.nonces == []

    # -- IDLE --
    def test_idle(self):
        result = parse_work_result(b"IDLE")
        assert result.status == WorkStatus.IDLE
        assert result.nonces == []

    # -- NONCE-FOUND --
    def test_nonce_found_single(self):
        result = parse_work_result(b"NONCE-FOUND:a1b2c3d4")
        assert result.status == WorkStatus.NONCE_FOUND
        assert result.nonces == [0xA1B2C3D4]

    def test_nonce_found_multiple(self):
        result = parse_work_result(b"NONCE-FOUND:a1b2c3d4,e5f67890")
        assert result.status == WorkStatus.NONCE_FOUND
        assert result.nonces == [0xA1B2C3D4, 0xE5F67890]

    def test_nonce_found_three(self):
        result = parse_work_result(b"NONCE-FOUND:00000001,00000002,00000003")
        assert result.status == WorkStatus.NONCE_FOUND
        assert result.nonces == [1, 2, 3]

    def test_nonce_found_returns_work_result(self):
        result = parse_work_result(b"NONCE-FOUND:deadbeef")
        assert isinstance(result, WorkResult)
        assert result.nonces == [0xDEADBEEF]

    def test_nonce_found_uppercase_hex(self):
        result = parse_work_result(b"NONCE-FOUND:DEADBEEF")
        assert result.nonces == [0xDEADBEEF]

    # -- Unknown --
    def test_raises_on_unknown(self):
        with pytest.raises(BFLProtocolError, match="Unrecognised"):
            parse_work_result(b"SOMETHING-WEIRD")

    def test_raises_on_empty(self):
        with pytest.raises(BFLProtocolError):
            parse_work_result(b"")


# -------------------------------------------------------------------
# Enum values
# -------------------------------------------------------------------

class TestWorkStatusEnum:
    def test_busy_value(self):
        assert WorkStatus.BUSY.value == "busy"

    def test_no_nonce_value(self):
        assert WorkStatus.NO_NONCE.value == "no_nonce"

    def test_nonce_found_value(self):
        assert WorkStatus.NONCE_FOUND.value == "nonce_found"

    def test_idle_value(self):
        assert WorkStatus.IDLE.value == "idle"
