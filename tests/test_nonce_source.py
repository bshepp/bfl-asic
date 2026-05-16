"""NonceSource: honest device-as-nonce-stream surface (NOT a HashSource)."""
from __future__ import annotations

from bfl_asic.nonce_source import (
    NonceSource, SimulatedNonceSource, DeviceNonceSource)


def test_simulated_nonce_source_yields_results():
    src = SimulatedNonceSource()
    out = list(src.results(count=50))
    assert len(out) == 50
    assert src.name() == "simulated-nonce-source"


def test_nonce_source_is_not_a_hashsource():
    from bfl_asic.stats.engine import HashSource
    assert not issubclass(NonceSource, HashSource)
    assert not issubclass(SimulatedNonceSource, HashSource)
    assert not issubclass(DeviceNonceSource, HashSource)


def test_simulated_nonce_source_duration_bounded_terminates():
    # exercises the deadline branch of run(): must terminate, not hang.
    src = SimulatedNonceSource()
    out = list(src.results(duration=0.05))
    assert isinstance(out, list)


def test_device_nonce_source_over_transport():
    from bfl_asic.transport.simulator import SimulatorTransport, SimulatedDevice

    t = SimulatorTransport(SimulatedDevice(simulated_hashrate=32))

    def work():
        for i in range(20):
            yield (bytes([i]) * 32, bytes([i]) * 12)

    src = DeviceNonceSource(t, work())
    out = list(src.results(count=20))
    assert len(out) == 20
    assert src.name() == "device-nonce-source"
