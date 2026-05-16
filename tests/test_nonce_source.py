"""NonceSource: honest device-as-nonce-stream surface (NOT a HashSource)."""
from __future__ import annotations

from bfl_asic.nonce_source import (
    NonceSource, SimulatedNonceSource, DeviceNonceSource)


def test_simulated_nonce_source_yields_results():
    src = SimulatedNonceSource()
    out = list(src.results(count=50))
    assert len(out) == 50
    assert src.name()


def test_nonce_source_is_not_a_hashsource():
    from bfl_asic.stats.engine import HashSource
    assert not issubclass(NonceSource, HashSource)
    assert not issubclass(SimulatedNonceSource, HashSource)
    assert not issubclass(DeviceNonceSource, HashSource)
