"""Tests for the Icarus / Block-Erupter protocol (work-in / nonce-out).

Anchored to cgminer's driver-icarus.c golden self-test: the 64-byte
``golden_ob`` yields nonce 0x000187a2 (big-endian on the wire). Byte order
was confirmed on real hardware (ASICMiner Block Erupter, 2026-08-19).

Pure functions, no I/O.
"""
from __future__ import annotations

import pytest

from bfl_asic.protocol.icarus import (
    GOLDEN_WORK, GOLDEN_NONCE, build_work, parse_nonce,
)


def test_golden_constants_match_cgminer():
    assert len(GOLDEN_WORK) == 64
    assert GOLDEN_WORK.hex() == (
        "4679ba4ec99876bf4bfe086082b40025"
        "4df6c356451471139a3afa71e48f544a"
        "00000000000000000000000000000000"
        "0000000087320b1a1426674f2fa722ce")
    assert GOLDEN_NONCE == 0x000187A2


def test_parse_nonce_is_big_endian():
    assert parse_nonce(bytes.fromhex("000187a2")) == 0x000187A2
    assert parse_nonce(b"\x00\x00\x00\x01") == 1


def test_parse_nonce_rejects_wrong_length():
    with pytest.raises(ValueError):
        parse_nonce(b"\x00\x00\x00")  # 3 bytes, not 4


def test_build_work_layout():
    # cgminer sends rev(midstate,32) + 20-byte fill + rev(data,12).
    midstate = bytes(range(32))
    data = bytes(range(100, 112))  # 12 bytes
    w = build_work(midstate, data)
    assert len(w) == 64
    assert w[:32] == midstate[::-1]
    assert w[32:52] == b"\x00" * 20
    assert w[52:] == data[::-1]


def test_build_work_validates_lengths():
    with pytest.raises(ValueError):
        build_work(bytes(31), bytes(12))
    with pytest.raises(ValueError):
        build_work(bytes(32), bytes(11))


# --- simulated Icarus transport (headless testing, no hardware) ---------

def test_simulated_icarus_transport_golden_roundtrip():
    from bfl_asic.transport.icarus_simulator import SimulatedIcarusTransport
    t = SimulatedIcarusTransport()
    t.open()
    t.write(GOLDEN_WORK)
    assert parse_nonce(t.read(4)) == GOLDEN_NONCE
    t.close()


def test_simulated_icarus_transport_nonce_is_deterministic():
    from bfl_asic.transport.icarus_simulator import SimulatedIcarusTransport
    t = SimulatedIcarusTransport()
    t.open()
    work = build_work(bytes(range(32)), bytes(range(100, 112)))
    t.write(work)
    n1 = parse_nonce(t.read(4))
    t.write(work)
    n2 = parse_nonce(t.read(4))
    assert n1 == n2
    assert 0 <= n1 < (1 << 32)


def test_simulated_icarus_transport_accumulates_partial_writes():
    from bfl_asic.transport.icarus_simulator import SimulatedIcarusTransport
    t = SimulatedIcarusTransport()
    t.open()
    # split the 64-byte work across two writes; nonce only after all 64 arrive
    t.write(GOLDEN_WORK[:40])
    assert t.read(4) == b""
    t.write(GOLDEN_WORK[40:])
    assert parse_nonce(t.read(4)) == GOLDEN_NONCE


# --- linear-scan hashrate (the Erupter's natural metric) ----------------

def test_linear_scan_hashrate_from_position_over_time():
    from bfl_asic.protocol.icarus import linear_scan_hashrate
    # The Erupter scans nonces linearly from 0, so position / arrival-time
    # is the hashrate directly. These three all imply 335 MH/s.
    pairs = [(335_000_000, 1.0), (670_000_000, 2.0), (1_005_000_000, 3.0)]
    hr = linear_scan_hashrate(pairs)
    assert abs(hr - 335_000_000) < 1_000


def test_linear_scan_hashrate_ignores_nonpositive_time():
    from bfl_asic.protocol.icarus import linear_scan_hashrate
    pairs = [(100, 0.0), (335_000_000, 1.0)]  # first is unusable
    assert abs(linear_scan_hashrate(pairs) - 335_000_000) < 1_000


def test_linear_scan_hashrate_empty_is_none():
    from bfl_asic.protocol.icarus import linear_scan_hashrate
    assert linear_scan_hashrate([]) is None


# --- IcarusNonceSource + the extra_metrics() hook -----------------------

def _work(n):
    for i in range(n):
        yield (bytes([i % 256]) * 32, bytes([i % 256]) * 12)


def test_icarus_nonce_source_yields_a_result_per_work():
    from bfl_asic.transport.icarus_simulator import SimulatedIcarusTransport
    from bfl_asic.nonce_source import IcarusNonceSource
    src = IcarusNonceSource(SimulatedIcarusTransport(), _work(10))
    out = list(src.results(count=10))
    assert len(out) == 10
    assert all(r.nonces for r in out)  # sim returns one nonce per work
    assert src.name() == "icarus-nonce-source"


def test_icarus_nonce_source_reports_hashrate_extra_metric():
    from bfl_asic.transport.icarus_simulator import SimulatedIcarusTransport
    from bfl_asic.nonce_source import IcarusNonceSource
    src = IcarusNonceSource(SimulatedIcarusTransport(), _work(5))
    list(src.results(count=5))
    m = src.extra_metrics()
    assert "hashrate_mhps" in m and "samples" in m
    assert m["samples"] == 5


def test_base_nonce_source_extra_metrics_defaults_empty():
    from bfl_asic.nonce_source import SimulatedNonceSource
    assert SimulatedNonceSource().extra_metrics() == {}


# --- characterize_source: the common core over any NonceSource ----------

def test_characterize_source_common_core_on_icarus():
    from bfl_asic.transport.icarus_simulator import SimulatedIcarusTransport
    from bfl_asic.nonce_source import IcarusNonceSource
    from bfl_asic.characterization import characterize_source
    src = IcarusNonceSource(SimulatedIcarusTransport(), _work(30))
    rep = characterize_source(src, count=30, bins=16)
    assert rep["source"] == "icarus-nonce-source"
    assert rep["throughput"]["jobs_completed"] == 30
    assert rep["nonce_distribution"]["n"] == 30
    assert sum(rep["nonce_distribution"]["counts"]) == 30
    assert "hashrate_mhps" in rep["extras"]   # device-specific extra (Option B)
    assert "healthy" in rep["health"]


def test_characterize_source_generalises_to_a_bfl_source():
    from bfl_asic.nonce_source import SimulatedNonceSource
    from bfl_asic.characterization import characterize_source
    rep = characterize_source(SimulatedNonceSource(), count=20, bins=16)
    assert rep["source"] == "simulated-nonce-source"
    assert rep["throughput"]["jobs_completed"] == 20
    assert rep["extras"] == {}   # a BFL source exposes no device-specific extras
