"""Tests for engine-health / dead-core detection from nonce distributions.

A dead engine that scans a contiguous sub-range of the nonce space leaves
a cold (under-represented) band in the winning-nonce histogram. These
tests inject known gaps and confirm the detector localizes them, and
confirm a uniform distribution reads as healthy.
"""
from __future__ import annotations

import random

from bfl_asic.health import (
    DeadRegion,
    EngineHealthReport,
    detect_dead_cores,
    detect_dead_cores_from_counts,
    nonce_histogram,
)

NS = 1 << 32


def test_nonce_histogram_bins_by_value():
    nonces = [0, NS // 4, NS // 4, NS - 1]
    assert nonce_histogram(nonces, 4) == [1, 2, 0, 1]


def test_uniform_distribution_is_healthy():
    rng = random.Random(0)
    nonces = [rng.randrange(NS) for _ in range(30000)]
    rep = detect_dead_cores(nonces, bins=64, engines=27)
    assert isinstance(rep, EngineHealthReport)
    assert rep.healthy
    assert rep.dead_regions == []
    assert rep.cold_fraction == 0.0
    assert rep.estimated_dead_engines == 0.0


def test_dead_contiguous_band_is_detected():
    rng = random.Random(1)
    lo, hi = int(0.30 * NS), int(0.40 * NS)  # one engine's range is dead
    nonces: list[int] = []
    while len(nonces) < 30000:
        v = rng.randrange(NS)
        if lo <= v < hi:
            continue
        nonces.append(v)
    rep = detect_dead_cores(nonces, bins=64, engines=27)
    assert not rep.healthy
    assert rep.dead_regions
    r = rep.dead_regions[0]
    # region overlaps the injected [0.30, 0.40] band
    assert r.nonce_start <= 0.40 * NS and r.nonce_end >= 0.30 * NS
    assert 0.07 < rep.cold_fraction < 0.13
    assert rep.estimated_dead_engines is not None
    assert 1.5 < rep.estimated_dead_engines < 4.0  # ~10% of 27 engines


def test_detect_from_counts_localizes_zeroed_bins():
    counts = [70] * 64
    for i in range(20, 26):  # a dead band, bins 20..25
        counts[i] = 0
    rep = detect_dead_cores_from_counts(counts, sum(counts), engines=27)
    assert not rep.healthy
    region = rep.dead_regions[0]
    assert isinstance(region, DeadRegion)
    assert region.start_bin == 20 and region.end_bin == 25
    assert region.observed == 0


def test_single_cold_bin_is_noise_not_a_dead_region():
    # One low bin (min_run defaults to 2) must not trigger a dead-core call.
    counts = [70] * 64
    counts[30] = 0
    rep = detect_dead_cores_from_counts(counts, sum(counts))
    assert rep.healthy
    assert rep.dead_regions == []


def test_estimated_dead_engines_none_without_engine_count():
    counts = [70] * 64
    for i in range(20, 26):
        counts[i] = 0
    rep = detect_dead_cores_from_counts(counts, sum(counts))  # engines=None
    assert rep.estimated_dead_engines is None
    assert not rep.healthy  # still detects the region

def test_summary_mentions_verdict():
    rep = detect_dead_cores_from_counts([70] * 64, 70 * 64, engines=27)
    assert "healthy" in rep.summary().lower()
