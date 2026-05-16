"""Fan-control protocol: pure builders/ack. No hardware."""
from __future__ import annotations

import pytest

from bfl_asic.protocol.fan import build_fan_auto, build_fan_level, parse_fan_ack


def test_build_fan_auto():
    assert build_fan_auto() == b"Z9X"


@pytest.mark.parametrize("level,expected",
                         [(0, b"Z0X"), (1, b"Z1X"), (2, b"Z2X"),
                          (3, b"Z3X"), (4, b"Z4X")])
def test_build_fan_level(level, expected):
    assert build_fan_level(level) == expected


@pytest.mark.parametrize("bad", [-1, 5, 99])
def test_build_fan_level_rejects_out_of_range(bad):
    with pytest.raises(ValueError):
        build_fan_level(bad)


def test_parse_fan_ack_tolerant():
    # cgminer just READ_NLs the reply; exact token is unconfirmed.
    assert parse_fan_ack(b"OK\n") is True
    assert parse_fan_ack(b"SUCCESS\n") is True
    assert parse_fan_ack(b"anything\n") is True
    assert parse_fan_ack(b"ERR:INVALID DATA\n") is False
    assert parse_fan_ack(b"") is False


@pytest.mark.parametrize("bad", [True, False])
def test_build_fan_level_rejects_bool(bad):
    # bool is an int subclass; a thermal-safety path must not silently
    # accept True/False as a fan level.
    with pytest.raises(ValueError):
        build_fan_level(bad)


@pytest.mark.parametrize("bad", ["2", 2.0, None])
def test_build_fan_level_rejects_non_int(bad):
    with pytest.raises(ValueError):
        build_fan_level(bad)


def test_parse_fan_ack_whitespace_and_crlf_are_false():
    assert parse_fan_ack(b"   \n") is False
    assert parse_fan_ack(b"\r\n") is False
    assert parse_fan_ack(b"\t") is False


def test_device_fan_methods_and_warning(recwarn):
    from bfl_asic.transport.simulator import SimulatorTransport
    from bfl_asic.device import BFLDevice

    with BFLDevice(SimulatorTransport()) as dev:
        assert dev.set_fan_auto() is True
        assert dev.set_fan(4) is True            # fixed level
    msgs = [str(w.message) for w in recwarn.list]
    assert any("thermal" in m.lower() for m in msgs)  # safety warning fired
