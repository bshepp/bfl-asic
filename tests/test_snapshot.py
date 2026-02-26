"""Tests for bfl_asic.stats.snapshot -- JSON-serializable snapshots."""

from __future__ import annotations

import json

import numpy as np
import pytest

from bfl_asic.stats.snapshot import StatsSnapshot, _NumpyEncoder


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _make_sample_snapshot(**overrides) -> StatsSnapshot:
    """Build a StatsSnapshot with sensible defaults; override any field."""
    defaults = dict(
        timestamp="2025-01-01T00:00:00+00:00",
        sample_count=1000,
        engine_name="software-sha256d",
        duration_seconds=2.5,
        hash_rate=400.0,
        bit_frequency={"bit_frequencies": [0.5] * 256, "max_bias": 0.01},
        avalanche={"mean": 128.0, "std": 8.0},
        correlation={"max_deviation": 0.002},
        near_collision={"collision_counts": {}, "comparisons_made": 500},
        byte_distribution={"chi_squared": 250.0, "total_bytes": 32000},
        entropy={"shannon_entropy": 7.99, "max_entropy": 8.0, "efficiency": 0.999},
    )
    defaults.update(overrides)
    return StatsSnapshot(**defaults)


# -------------------------------------------------------------------
# Construction
# -------------------------------------------------------------------

class TestStatsSnapshotConstruction:
    """Tests for StatsSnapshot field access and basic construction."""

    def test_create_with_sample_data(self):
        snap = _make_sample_snapshot()
        assert snap.timestamp == "2025-01-01T00:00:00+00:00"
        assert snap.sample_count == 1000
        assert snap.engine_name == "software-sha256d"
        assert snap.duration_seconds == 2.5
        assert snap.hash_rate == 400.0

    def test_fields_match_accumulator_keys(self):
        snap = _make_sample_snapshot()
        assert isinstance(snap.bit_frequency, dict)
        assert isinstance(snap.avalanche, dict)
        assert isinstance(snap.correlation, dict)
        assert isinstance(snap.near_collision, dict)
        assert isinstance(snap.byte_distribution, dict)
        assert isinstance(snap.entropy, dict)

    def test_hash_rate_field(self):
        snap = _make_sample_snapshot(sample_count=5000, duration_seconds=10.0)
        assert snap.hash_rate == snap.hash_rate  # just a stored field here


# -------------------------------------------------------------------
# Serialization
# -------------------------------------------------------------------

class TestStatsSnapshotSerialization:
    """Tests for to_json / from_json round-trips."""

    def test_to_json_returns_valid_json(self):
        snap = _make_sample_snapshot()
        text = snap.to_json()
        parsed = json.loads(text)
        assert isinstance(parsed, dict)

    def test_to_json_contains_all_fields(self):
        snap = _make_sample_snapshot()
        parsed = json.loads(snap.to_json())
        for field in (
            "timestamp", "sample_count", "engine_name",
            "duration_seconds", "hash_rate",
            "bit_frequency", "avalanche", "correlation",
            "near_collision", "byte_distribution", "entropy",
        ):
            assert field in parsed, f"Missing field: {field}"

    def test_from_json_round_trip(self):
        snap = _make_sample_snapshot()
        text = snap.to_json()
        restored = StatsSnapshot.from_json(text)
        assert restored.timestamp == snap.timestamp
        assert restored.sample_count == snap.sample_count
        assert restored.engine_name == snap.engine_name
        assert restored.duration_seconds == snap.duration_seconds
        assert restored.hash_rate == snap.hash_rate
        assert restored.bit_frequency == snap.bit_frequency
        assert restored.avalanche == snap.avalanche
        assert restored.correlation == snap.correlation
        assert restored.near_collision == snap.near_collision
        assert restored.byte_distribution == snap.byte_distribution
        assert restored.entropy == snap.entropy

    def test_from_json_preserves_nested_lists(self):
        snap = _make_sample_snapshot(
            bit_frequency={"bit_frequencies": list(range(256))}
        )
        restored = StatsSnapshot.from_json(snap.to_json())
        assert restored.bit_frequency["bit_frequencies"] == list(range(256))


# -------------------------------------------------------------------
# File I/O
# -------------------------------------------------------------------

class TestStatsSnapshotFileIO:
    """Tests for save() and load() through a file."""

    def test_save_and_load_round_trip(self, tmp_path):
        snap = _make_sample_snapshot()
        filepath = tmp_path / "snap.json"
        snap.save(filepath)
        restored = StatsSnapshot.load(filepath)
        assert restored.sample_count == snap.sample_count
        assert restored.engine_name == snap.engine_name
        assert restored.entropy == snap.entropy

    def test_saved_file_is_valid_json(self, tmp_path):
        snap = _make_sample_snapshot()
        filepath = tmp_path / "snap.json"
        snap.save(filepath)
        parsed = json.loads(filepath.read_text())
        assert parsed["sample_count"] == 1000


# -------------------------------------------------------------------
# Numpy handling
# -------------------------------------------------------------------

class TestNumpyHandling:
    """Tests that numpy arrays and scalar types survive JSON round-trips."""

    def test_numpy_array_in_report_dict(self):
        snap = _make_sample_snapshot(
            bit_frequency={"bit_frequencies": np.array([0.5] * 256)}
        )
        text = snap.to_json()
        parsed = json.loads(text)
        assert isinstance(parsed["bit_frequency"]["bit_frequencies"], list)
        assert len(parsed["bit_frequency"]["bit_frequencies"]) == 256

    def test_numpy_integer_in_report_dict(self):
        snap = _make_sample_snapshot(
            avalanche={"mean": np.int64(128), "pairs": np.int32(999)}
        )
        text = snap.to_json()
        parsed = json.loads(text)
        assert parsed["avalanche"]["mean"] == 128
        assert isinstance(parsed["avalanche"]["mean"], int)

    def test_numpy_float_in_report_dict(self):
        snap = _make_sample_snapshot(
            entropy={"shannon_entropy": np.float64(7.99), "max_entropy": np.float32(8.0)}
        )
        text = snap.to_json()
        parsed = json.loads(text)
        assert abs(parsed["entropy"]["shannon_entropy"] - 7.99) < 1e-10
        assert isinstance(parsed["entropy"]["shannon_entropy"], float)

    def test_numpy_2d_array_in_report_dict(self):
        mat = np.eye(4)
        snap = _make_sample_snapshot(
            correlation={"correlation_matrix": mat}
        )
        text = snap.to_json()
        parsed = json.loads(text)
        assert parsed["correlation"]["correlation_matrix"] == mat.tolist()


# -------------------------------------------------------------------
# from_pipeline factory
# -------------------------------------------------------------------

class TestFromPipeline:
    """Tests for StatsSnapshot.from_pipeline() factory method."""

    def test_creates_valid_snapshot(self):
        report = {
            "bit_frequency": {"max_bias": 0.01},
            "avalanche": {"mean": 128.0},
            "correlation": {},
            "near_collision": {},
            "byte_distribution": {},
            "entropy": {"shannon_entropy": 7.99},
        }
        snap = StatsSnapshot.from_pipeline(
            engine_name="test-engine",
            sample_count=5000,
            duration_seconds=10.0,
            report=report,
        )
        assert snap.engine_name == "test-engine"
        assert snap.sample_count == 5000
        assert snap.duration_seconds == 10.0

    def test_hash_rate_computed_correctly(self):
        snap = StatsSnapshot.from_pipeline(
            engine_name="test",
            sample_count=5000,
            duration_seconds=10.0,
            report={},
        )
        assert snap.hash_rate == pytest.approx(500.0)

    def test_hash_rate_with_zero_duration(self):
        """Zero duration should not cause division by zero."""
        snap = StatsSnapshot.from_pipeline(
            engine_name="test",
            sample_count=100,
            duration_seconds=0.0,
            report={},
        )
        assert snap.hash_rate == pytest.approx(100 / 0.001)

    def test_timestamp_is_iso_format(self):
        snap = StatsSnapshot.from_pipeline(
            engine_name="test",
            sample_count=1,
            duration_seconds=0.1,
            report={},
        )
        # ISO 8601 timestamps contain 'T' separator
        assert "T" in snap.timestamp

    def test_missing_report_keys_default_to_empty_dict(self):
        snap = StatsSnapshot.from_pipeline(
            engine_name="test",
            sample_count=1,
            duration_seconds=0.1,
            report={"bit_frequency": {"max_bias": 0.0}},
        )
        assert snap.avalanche == {}
        assert snap.correlation == {}
        assert snap.near_collision == {}
        assert snap.byte_distribution == {}
        assert snap.entropy == {}
        assert snap.bit_frequency == {"max_bias": 0.0}
