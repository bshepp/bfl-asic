"""Tests for bfl_asic.stats.accumulators -- statistical accumulators."""

from __future__ import annotations

import math

import numpy as np
import pytest

from bfl_asic.stats.accumulators import (
    AvalancheAccumulator,
    BitCorrelationAccumulator,
    BitFrequencyAccumulator,
    ByteDistributionAccumulator,
    CompositeAccumulator,
    EntropyAccumulator,
    NearCollisionAccumulator,
)
from bfl_asic.stats.engine import SoftwareHashEngine


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _generate_hashes(count: int, start: int = 0) -> list[tuple[bytes, bytes]]:
    """Generate *count* (input, output) pairs from SoftwareHashEngine."""
    engine = SoftwareHashEngine(start=start)
    return list(engine.hashes(count=count))


# Precompute a shared set of 10 000 hashes for statistical tests.
_HASH_PAIRS_10K: list[tuple[bytes, bytes]] = _generate_hashes(10_000)


def _ingest_many(acc: object, pairs: list[tuple[bytes, bytes]]) -> None:
    """Ingest a list of (input, output) pairs into an accumulator."""
    for inp, out in pairs:
        acc.ingest(inp, out)  # type: ignore[union-attr]


# -------------------------------------------------------------------
# BitFrequencyAccumulator
# -------------------------------------------------------------------

class TestBitFrequencyAccumulator:
    """Tests for BitFrequencyAccumulator."""

    def test_construction(self):
        acc = BitFrequencyAccumulator()
        assert acc is not None

    def test_sample_count_starts_at_zero(self):
        acc = BitFrequencyAccumulator()
        assert acc.sample_count == 0

    def test_ingest_one_increments_sample_count(self):
        acc = BitFrequencyAccumulator()
        inp, out = _HASH_PAIRS_10K[0]
        acc.ingest(inp, out)
        assert acc.sample_count == 1

    def test_report_returns_valid_dict_after_one_ingest(self):
        acc = BitFrequencyAccumulator()
        inp, out = _HASH_PAIRS_10K[0]
        acc.ingest(inp, out)
        report = acc.report()
        assert "bit_frequencies" in report
        assert "max_bias" in report
        assert "mean_bias" in report
        assert "chi_squared" in report

    def test_report_bit_frequencies_length(self):
        acc = BitFrequencyAccumulator()
        inp, out = _HASH_PAIRS_10K[0]
        acc.ingest(inp, out)
        assert len(report := acc.report()["bit_frequencies"]) == 256

    def test_reset_clears_state(self):
        acc = BitFrequencyAccumulator()
        _ingest_many(acc, _HASH_PAIRS_10K[:100])
        acc.reset()
        assert acc.sample_count == 0
        report = acc.report()
        assert report["max_bias"] == 0.0

    def test_report_at_zero_samples(self):
        acc = BitFrequencyAccumulator()
        report = acc.report()
        assert report["bit_frequencies"] == [0.0] * 256
        assert report["chi_squared"] == 0.0

    def test_bit_frequencies_in_range_after_10k_hashes(self):
        """Each bit frequency should be between 0.45 and 0.55."""
        acc = BitFrequencyAccumulator()
        _ingest_many(acc, _HASH_PAIRS_10K)
        report = acc.report()
        for freq in report["bit_frequencies"]:
            assert 0.45 <= freq <= 0.55, f"Frequency {freq} out of range"

    def test_max_bias_small_after_10k_hashes(self):
        acc = BitFrequencyAccumulator()
        _ingest_many(acc, _HASH_PAIRS_10K)
        report = acc.report()
        assert report["max_bias"] < 0.05

    def test_chi_squared_positive(self):
        acc = BitFrequencyAccumulator()
        _ingest_many(acc, _HASH_PAIRS_10K[:100])
        report = acc.report()
        assert report["chi_squared"] >= 0.0


# -------------------------------------------------------------------
# AvalancheAccumulator
# -------------------------------------------------------------------

class TestAvalancheAccumulator:
    """Tests for AvalancheAccumulator."""

    def test_construction(self):
        acc = AvalancheAccumulator()
        assert acc is not None

    def test_sample_count_starts_at_zero(self):
        acc = AvalancheAccumulator()
        assert acc.sample_count == 0

    def test_ingest_one_increments_sample_count(self):
        acc = AvalancheAccumulator()
        inp, out = _HASH_PAIRS_10K[0]
        acc.ingest(inp, out)
        assert acc.sample_count == 1

    def test_first_hash_no_histogram_update(self):
        acc = AvalancheAccumulator()
        inp, out = _HASH_PAIRS_10K[0]
        acc.ingest(inp, out)
        report = acc.report()
        assert report["pairs_counted"] == 0
        assert sum(report["histogram"]) == 0

    def test_report_keys(self):
        acc = AvalancheAccumulator()
        _ingest_many(acc, _HASH_PAIRS_10K[:5])
        report = acc.report()
        assert "histogram" in report
        assert "mean" in report
        assert "std" in report
        assert "min" in report
        assert "max" in report
        assert "pairs_counted" in report

    def test_histogram_shape(self):
        acc = AvalancheAccumulator()
        _ingest_many(acc, _HASH_PAIRS_10K[:10])
        assert len(acc.report()["histogram"]) == 257

    def test_pairs_counted_equals_sample_minus_one(self):
        acc = AvalancheAccumulator()
        _ingest_many(acc, _HASH_PAIRS_10K[:50])
        assert acc.report()["pairs_counted"] == 49

    def test_reset_clears_state(self):
        acc = AvalancheAccumulator()
        _ingest_many(acc, _HASH_PAIRS_10K[:100])
        acc.reset()
        assert acc.sample_count == 0
        assert acc.report()["pairs_counted"] == 0

    def test_mean_hamming_distance_after_10k(self):
        """Mean should be near 128 for random hashes."""
        acc = AvalancheAccumulator()
        _ingest_many(acc, _HASH_PAIRS_10K)
        report = acc.report()
        assert 120 <= report["mean"] <= 136

    def test_std_reasonable(self):
        """Std dev should be close to theoretical sqrt(256*0.25) ~ 8."""
        acc = AvalancheAccumulator()
        _ingest_many(acc, _HASH_PAIRS_10K)
        report = acc.report()
        assert 5.0 <= report["std"] <= 12.0

    def test_min_max_within_range(self):
        acc = AvalancheAccumulator()
        _ingest_many(acc, _HASH_PAIRS_10K)
        report = acc.report()
        assert 0 <= report["min"] <= report["max"] <= 256

    def test_report_at_zero_samples(self):
        acc = AvalancheAccumulator()
        report = acc.report()
        assert report["mean"] == 0.0
        assert report["pairs_counted"] == 0


# -------------------------------------------------------------------
# BitCorrelationAccumulator
# -------------------------------------------------------------------

class TestBitCorrelationAccumulator:
    """Tests for BitCorrelationAccumulator."""

    def test_construction_default(self):
        acc = BitCorrelationAccumulator()
        assert acc is not None

    def test_default_tracks_256_positions(self):
        acc = BitCorrelationAccumulator()
        assert len(acc._positions) == 256

    def test_custom_positions(self):
        positions = [0, 1, 2, 10, 255]
        acc = BitCorrelationAccumulator(positions=positions)
        assert acc._positions == positions

    def test_sample_count_starts_at_zero(self):
        acc = BitCorrelationAccumulator()
        assert acc.sample_count == 0

    def test_ingest_one_increments_sample_count(self):
        acc = BitCorrelationAccumulator(positions=[0, 1, 2, 3])
        inp, out = _HASH_PAIRS_10K[0]
        acc.ingest(inp, out)
        assert acc.sample_count == 1

    def test_report_keys(self):
        acc = BitCorrelationAccumulator(positions=[0, 1])
        inp, out = _HASH_PAIRS_10K[0]
        acc.ingest(inp, out)
        report = acc.report()
        assert "cooccurrence" in report
        assert "positions" in report
        assert "expected_cooccurrence" in report
        assert "max_deviation" in report
        assert "correlation_matrix" in report

    def test_cooccurrence_shape_matches_positions(self):
        positions = [0, 10, 20]
        acc = BitCorrelationAccumulator(positions=positions)
        _ingest_many(acc, _HASH_PAIRS_10K[:10])
        cooc = acc.report()["cooccurrence"]
        assert len(cooc) == 3
        assert len(cooc[0]) == 3

    def test_reset_clears_state(self):
        acc = BitCorrelationAccumulator(positions=[0, 1])
        _ingest_many(acc, _HASH_PAIRS_10K[:50])
        acc.reset()
        assert acc.sample_count == 0

    def test_max_deviation_small_after_many_hashes(self):
        """After many hashes, off-diagonal deviation from 0.25 should be small.

        The diagonal has expected value ~0.5 (bit AND itself = bit), so
        max_deviation includes the diagonal at ~0.25.  We verify that
        off-diagonal entries in the correlation matrix are close to 0.25.
        """
        positions = [0, 32, 64, 96, 128, 160, 192, 224]
        acc = BitCorrelationAccumulator(positions=positions)
        _ingest_many(acc, _HASH_PAIRS_10K)
        report = acc.report()
        corr = np.array(report["correlation_matrix"])
        k = len(positions)
        # Check off-diagonal entries only
        for i in range(k):
            for j in range(k):
                if i != j:
                    assert abs(corr[i, j] - 0.25) < 0.05, (
                        f"Off-diagonal correlation[{i},{j}] = {corr[i, j]}"
                    )

    def test_report_at_zero_samples(self):
        acc = BitCorrelationAccumulator(positions=[0, 1])
        report = acc.report()
        assert report["expected_cooccurrence"] == 0.0
        assert report["max_deviation"] == 0.0


# -------------------------------------------------------------------
# NearCollisionAccumulator
# -------------------------------------------------------------------

class TestNearCollisionAccumulator:
    """Tests for NearCollisionAccumulator."""

    def test_construction(self):
        acc = NearCollisionAccumulator()
        assert acc is not None

    def test_sample_count_starts_at_zero(self):
        acc = NearCollisionAccumulator()
        assert acc.sample_count == 0

    def test_ingest_one_increments_sample_count(self):
        acc = NearCollisionAccumulator()
        inp, out = _HASH_PAIRS_10K[0]
        acc.ingest(inp, out)
        assert acc.sample_count == 1

    def test_report_keys(self):
        acc = NearCollisionAccumulator()
        inp, out = _HASH_PAIRS_10K[0]
        acc.ingest(inp, out)
        report = acc.report()
        assert "collision_counts" in report
        assert "window_size" in report
        assert "max_distance" in report
        assert "comparisons_made" in report

    def test_collision_counts_are_dict(self):
        acc = NearCollisionAccumulator(window_size=10)
        _ingest_many(acc, _HASH_PAIRS_10K[:20])
        report = acc.report()
        assert isinstance(report["collision_counts"], dict)
        for key in report["collision_counts"]:
            assert isinstance(key, int)

    def test_window_does_not_exceed_max_size(self):
        acc = NearCollisionAccumulator(window_size=10)
        _ingest_many(acc, _HASH_PAIRS_10K[:50])
        assert acc.report()["window_size"] <= 10

    def test_comparisons_made_positive_after_multiple_ingests(self):
        acc = NearCollisionAccumulator(window_size=10)
        _ingest_many(acc, _HASH_PAIRS_10K[:20])
        assert acc.report()["comparisons_made"] > 0

    def test_reset_clears_state(self):
        acc = NearCollisionAccumulator(window_size=10)
        _ingest_many(acc, _HASH_PAIRS_10K[:20])
        acc.reset()
        assert acc.sample_count == 0
        assert acc.report()["comparisons_made"] == 0
        assert acc.report()["window_size"] == 0

    def test_near_collisions_extremely_rare_for_random(self):
        """With random SHA-256d hashes and small window, near-collisions
        at very low distance should be extremely rare or zero."""
        acc = NearCollisionAccumulator(max_distance=5, window_size=100)
        _ingest_many(acc, _HASH_PAIRS_10K[:500])
        report = acc.report()
        # Distance 1-5 collisions should be 0 for random hashes
        total_near = sum(report["collision_counts"].get(d, 0) for d in range(1, 6))
        assert total_near == 0

    def test_max_distance_respected(self):
        acc = NearCollisionAccumulator(max_distance=8)
        assert acc.report()["max_distance"] == 8


# -------------------------------------------------------------------
# ByteDistributionAccumulator
# -------------------------------------------------------------------

class TestByteDistributionAccumulator:
    """Tests for ByteDistributionAccumulator."""

    def test_construction(self):
        acc = ByteDistributionAccumulator()
        assert acc is not None

    def test_sample_count_starts_at_zero(self):
        acc = ByteDistributionAccumulator()
        assert acc.sample_count == 0

    def test_ingest_one_increments_sample_count(self):
        acc = ByteDistributionAccumulator()
        inp, out = _HASH_PAIRS_10K[0]
        acc.ingest(inp, out)
        assert acc.sample_count == 1

    def test_report_keys(self):
        acc = ByteDistributionAccumulator()
        inp, out = _HASH_PAIRS_10K[0]
        acc.ingest(inp, out)
        report = acc.report()
        assert "histogram" in report
        assert "chi_squared" in report
        assert "min_count" in report
        assert "max_count" in report
        assert "total_bytes" in report

    def test_histogram_length(self):
        acc = ByteDistributionAccumulator()
        inp, out = _HASH_PAIRS_10K[0]
        acc.ingest(inp, out)
        assert len(acc.report()["histogram"]) == 256

    def test_total_bytes_equals_sample_count_times_32(self):
        acc = ByteDistributionAccumulator()
        _ingest_many(acc, _HASH_PAIRS_10K[:100])
        report = acc.report()
        assert report["total_bytes"] == 100 * 32

    def test_reset_clears_state(self):
        acc = ByteDistributionAccumulator()
        _ingest_many(acc, _HASH_PAIRS_10K[:100])
        acc.reset()
        assert acc.sample_count == 0
        assert acc.report()["total_bytes"] == 0

    def test_chi_squared_reasonable_after_10k(self):
        """Chi-squared should not reject uniformity at generous significance."""
        acc = ByteDistributionAccumulator()
        _ingest_many(acc, _HASH_PAIRS_10K)
        report = acc.report()
        # For 255 degrees of freedom, chi-squared critical value at p=0.001
        # is about 310.  We use a very generous bound.
        assert report["chi_squared"] < 400

    def test_report_at_zero_samples(self):
        acc = ByteDistributionAccumulator()
        report = acc.report()
        assert report["total_bytes"] == 0
        assert report["chi_squared"] == 0.0

    def test_histogram_sum_equals_total_bytes(self):
        acc = ByteDistributionAccumulator()
        _ingest_many(acc, _HASH_PAIRS_10K[:100])
        report = acc.report()
        assert sum(report["histogram"]) == report["total_bytes"]


# -------------------------------------------------------------------
# EntropyAccumulator
# -------------------------------------------------------------------

class TestEntropyAccumulator:
    """Tests for EntropyAccumulator."""

    def test_construction(self):
        acc = EntropyAccumulator()
        assert acc is not None

    def test_sample_count_starts_at_zero(self):
        acc = EntropyAccumulator()
        assert acc.sample_count == 0

    def test_ingest_one_increments_sample_count(self):
        acc = EntropyAccumulator()
        inp, out = _HASH_PAIRS_10K[0]
        acc.ingest(inp, out)
        assert acc.sample_count == 1

    def test_report_keys(self):
        acc = EntropyAccumulator()
        inp, out = _HASH_PAIRS_10K[0]
        acc.ingest(inp, out)
        report = acc.report()
        assert "shannon_entropy" in report
        assert "max_entropy" in report
        assert "efficiency" in report

    def test_max_entropy_is_8(self):
        acc = EntropyAccumulator()
        assert acc.report()["max_entropy"] == 8.0

    def test_reset_clears_state(self):
        acc = EntropyAccumulator()
        _ingest_many(acc, _HASH_PAIRS_10K[:100])
        acc.reset()
        assert acc.sample_count == 0
        assert acc.report()["shannon_entropy"] == 0.0

    def test_high_entropy_after_10k_hashes(self):
        """Shannon entropy should be > 7.9 bits for uniform-like data."""
        acc = EntropyAccumulator()
        _ingest_many(acc, _HASH_PAIRS_10K)
        report = acc.report()
        assert report["shannon_entropy"] > 7.9

    def test_efficiency_near_one_after_10k(self):
        acc = EntropyAccumulator()
        _ingest_many(acc, _HASH_PAIRS_10K)
        report = acc.report()
        assert report["efficiency"] > 0.99

    def test_report_at_zero_samples(self):
        acc = EntropyAccumulator()
        report = acc.report()
        assert report["shannon_entropy"] == 0.0
        assert report["efficiency"] == 0.0


# -------------------------------------------------------------------
# CompositeAccumulator
# -------------------------------------------------------------------

class TestCompositeAccumulator:
    """Tests for CompositeAccumulator."""

    def test_construction_default(self):
        acc = CompositeAccumulator()
        assert acc is not None

    def test_default_creates_six_children(self):
        acc = CompositeAccumulator()
        assert len(acc._children) == 6

    def test_sample_count_starts_at_zero(self):
        acc = CompositeAccumulator()
        assert acc.sample_count == 0

    def test_single_ingest_updates_all_children(self):
        acc = CompositeAccumulator()
        inp, out = _HASH_PAIRS_10K[0]
        acc.ingest(inp, out)
        assert acc.sample_count == 1
        # Verify each child was updated
        for _name, child in acc._children:
            assert child.sample_count == 1  # type: ignore[union-attr]

    def test_report_contains_all_expected_keys(self):
        acc = CompositeAccumulator()
        inp, out = _HASH_PAIRS_10K[0]
        acc.ingest(inp, out)
        report = acc.report()
        expected_keys = {
            "bit_frequency",
            "avalanche",
            "correlation",
            "near_collision",
            "byte_distribution",
            "entropy",
        }
        assert set(report.keys()) == expected_keys

    def test_custom_accumulator_list(self):
        children = [
            ("bf", BitFrequencyAccumulator()),
            ("ent", EntropyAccumulator()),
        ]
        acc = CompositeAccumulator(accumulators=children)
        assert len(acc._children) == 2
        inp, out = _HASH_PAIRS_10K[0]
        acc.ingest(inp, out)
        report = acc.report()
        assert "bf" in report
        assert "ent" in report

    def test_reset_resets_all_children(self):
        acc = CompositeAccumulator()
        _ingest_many(acc, _HASH_PAIRS_10K[:50])
        acc.reset()
        assert acc.sample_count == 0
        for _name, child in acc._children:
            assert child.sample_count == 0  # type: ignore[union-attr]

    def test_report_values_are_dicts(self):
        acc = CompositeAccumulator()
        inp, out = _HASH_PAIRS_10K[0]
        acc.ingest(inp, out)
        report = acc.report()
        for key, value in report.items():
            assert isinstance(value, dict), f"report[{key!r}] should be a dict"

    def test_empty_children_list(self):
        acc = CompositeAccumulator(accumulators=[])
        assert acc.sample_count == 0
        assert acc.report() == {}
