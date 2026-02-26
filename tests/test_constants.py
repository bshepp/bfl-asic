"""Tests for protocol constants and the exception hierarchy."""

import pytest

from bfl_asic.protocol.constants import (
    BAUD_RATE,
    CMD_IDENTIFY,
    CMD_NONCE_RANGE,
    CMD_RESULT,
    CMD_TEMP,
    CMD_WORK,
    DELIMITER,
    POLL_INTERVAL,
    THROTTLE_DELAY,
    WORK_TIMEOUT,
)
from bfl_asic.exceptions import (
    BFLConnectionError,
    BFLDeviceError,
    BFLError,
    BFLProtocolError,
    BFLTimeoutError,
)


# -------------------------------------------------------------------
# Delimiter
# -------------------------------------------------------------------

class TestDelimiter:
    def test_delimiter_length(self):
        assert len(DELIMITER) == 8

    def test_delimiter_is_all_0x3e(self):
        assert all(b == 0x3E for b in DELIMITER)

    def test_delimiter_bytes_value(self):
        assert DELIMITER == b">" * 8


# -------------------------------------------------------------------
# Command codes
# -------------------------------------------------------------------

ALL_COMMANDS = [CMD_IDENTIFY, CMD_WORK, CMD_RESULT, CMD_TEMP, CMD_NONCE_RANGE]


class TestCommandCodes:
    @pytest.mark.parametrize("cmd", ALL_COMMANDS)
    def test_command_is_three_bytes(self, cmd):
        assert len(cmd) == 3

    @pytest.mark.parametrize("cmd", ALL_COMMANDS)
    def test_command_starts_with_Z(self, cmd):
        assert cmd[0:1] == b"Z"

    def test_command_values_are_distinct(self):
        assert len(set(ALL_COMMANDS)) == len(ALL_COMMANDS)


# -------------------------------------------------------------------
# Timing constants
# -------------------------------------------------------------------

class TestTimingConstants:
    @pytest.mark.parametrize("value", [POLL_INTERVAL, WORK_TIMEOUT, THROTTLE_DELAY])
    def test_timing_is_positive_float(self, value):
        assert isinstance(value, float)
        assert value > 0


# -------------------------------------------------------------------
# Serial configuration sanity
# -------------------------------------------------------------------

class TestSerialConfig:
    def test_baud_rate(self):
        assert BAUD_RATE == 115200


# -------------------------------------------------------------------
# Exception hierarchy
# -------------------------------------------------------------------

CHILD_EXCEPTIONS = [
    BFLConnectionError,
    BFLProtocolError,
    BFLTimeoutError,
    BFLDeviceError,
]


class TestExceptionHierarchy:
    def test_base_inherits_from_exception(self):
        assert issubclass(BFLError, Exception)

    @pytest.mark.parametrize("exc_cls", CHILD_EXCEPTIONS)
    def test_child_inherits_from_bfl_error(self, exc_cls):
        assert issubclass(exc_cls, BFLError)

    @pytest.mark.parametrize("exc_cls", CHILD_EXCEPTIONS)
    def test_child_is_catchable_as_bfl_error(self, exc_cls):
        with pytest.raises(BFLError):
            raise exc_cls("test")

    @pytest.mark.parametrize("exc_cls", CHILD_EXCEPTIONS)
    def test_child_preserves_message(self, exc_cls):
        msg = "something went wrong"
        err = exc_cls(msg)
        assert str(err) == msg
