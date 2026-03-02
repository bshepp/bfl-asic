"""Tests for bfl_asic.protocol.responses."""

import pytest

from bfl_asic.exceptions import BFLProtocolError
from bfl_asic.protocol.responses import (
    DeviceInfo,
    TemperatureReading,
    WorkResult,
    WorkStatus,
    parse_identify,
    parse_temperature,
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
    def test_single_sensor(self):
        raw = b"TEMP0:45C"
        result = parse_temperature(raw)
        assert result.sensors == [45.0]

    def test_two_sensors(self):
        raw = b"TEMP0:45C\nTEMP1:43C"
        result = parse_temperature(raw)
        assert result.sensors == [45.0, 43.0]

    def test_three_sensors(self):
        raw = b"TEMP0:45C\nTEMP1:43C\nTEMP2:50C"
        result = parse_temperature(raw)
        assert result.sensors == [45.0, 43.0, 50.0]

    def test_decimal_temperatures(self):
        raw = b"TEMP0:45.5C"
        result = parse_temperature(raw)
        assert result.sensors == [45.5]

    def test_returns_temperature_reading_type(self):
        raw = b"TEMP0:45C"
        result = parse_temperature(raw)
        assert isinstance(result, TemperatureReading)

    def test_with_spaces(self):
        raw = b"TEMP0: 45 C"
        result = parse_temperature(raw)
        assert result.sensors == [45.0]

    def test_raises_on_garbage(self):
        with pytest.raises(BFLProtocolError, match="No temperature data"):
            parse_temperature(b"garbage data")

    def test_raises_on_empty(self):
        with pytest.raises(BFLProtocolError, match="No temperature data"):
            parse_temperature(b"")

    def test_raises_on_partial_format(self):
        with pytest.raises(BFLProtocolError, match="No temperature data"):
            parse_temperature(b"TEMP0:")

    def test_carriage_return_separator(self):
        raw = b"TEMP0:45C\r\nTEMP1:43C"
        result = parse_temperature(raw)
        assert result.sensors == [45.0, 43.0]

    # -- Raw CSV format (SC firmware) --

    def test_raw_csv_three_values(self):
        raw = b"3448,1008,11420\n"
        result = parse_temperature(raw)
        assert len(result.sensors) == 3
        assert result.sensors[0] == pytest.approx(34.48)
        assert result.sensors[1] == pytest.approx(10.08)
        assert result.sensors[2] == pytest.approx(114.20)

    def test_raw_csv_single_value(self):
        raw = b"3500\n"
        result = parse_temperature(raw)
        assert result.sensors == [35.0]

    def test_raw_csv_with_spaces(self):
        raw = b"3448, 1008, 11420\n"
        result = parse_temperature(raw)
        assert len(result.sensors) == 3
        assert result.sensors[0] == pytest.approx(34.48)


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
