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


def test_set_fan_auto_is_silent(recwarn):
    from bfl_asic.transport.simulator import SimulatorTransport
    from bfl_asic.device import BFLDevice
    with BFLDevice(SimulatorTransport()) as dev:
        assert dev.set_fan_auto() is True
    assert not recwarn.list  # auto = safe resting state, no warning


def test_set_fan_zero_warns_thermal_safety():
    from bfl_asic.transport.simulator import SimulatorTransport
    from bfl_asic.device import BFLDevice
    from bfl_asic.exceptions import ThermalSafetyWarning
    with BFLDevice(SimulatorTransport()) as dev:
        with pytest.warns(ThermalSafetyWarning):
            dev.set_fan(0)  # fan off = most dangerous


def test_set_fan_bad_level_warns_then_raises():
    from bfl_asic.transport.simulator import SimulatorTransport
    from bfl_asic.device import BFLDevice
    from bfl_asic.exceptions import ThermalSafetyWarning
    with BFLDevice(SimulatorTransport()) as dev:
        with pytest.warns(ThermalSafetyWarning):
            with pytest.raises(ValueError):
                dev.set_fan(99)


def test_set_fan_returns_false_on_err_ack():
    from bfl_asic.device import BFLDevice

    class ErrFanTransport:
        is_open = True
        def open(self): self.is_open = True
        def close(self): self.is_open = False
        def write(self, data: bytes): self._last = data
        def readline(self, timeout=None):
            # ZGX identify must still work so BFLDevice context enter is ok
            if getattr(self, "_last", b"").startswith(b"ZGX"):
                return b"BitForce SHA256 SC 1.0\n"
            return b"ERR:TIMEOUT\n"

    dev = BFLDevice(ErrFanTransport())
    dev.__enter__()
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assert dev.set_fan_auto() is False      # ERR ack -> False
            assert dev.set_fan(4) is False
    finally:
        dev.__exit__(None, None, None)


def test_fan_fixed_restores_auto_normally_and_on_exception():
    from bfl_asic.transport.simulator import SimulatorTransport
    from bfl_asic.device import BFLDevice, fan_fixed

    t = SimulatorTransport()
    with BFLDevice(t) as dev:
        with fan_fixed(dev, 0):
            assert t.device.fan_mode == "fixed" and t.device.fan_level == 0
        assert t.device.fan_mode == "auto"          # restored on normal exit
        # restored even when the body raises
        with pytest.raises(RuntimeError):
            with fan_fixed(dev, 4):
                assert t.device.fan_mode == "fixed"
                raise RuntimeError("boom")
        assert t.device.fan_mode == "auto"
