"""Tests for the randomness battery orchestrator and snapshot."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from bfl_asic.randomness.battery import (
    RandomnessBattery,
    bytes_to_bits,
    collect_bits,
)
from bfl_asic.randomness.snapshot import RandomnessSnapshot
from bfl_asic.randomness.tests import frequency_test
from bfl_asic.stats.engine import SoftwareHashEngine


# -------------------------------------------------------------------
# bytes_to_bits + collect_bits helpers
# -------------------------------------------------------------------


class TestBytesToBits:
    def test_single_byte_msb_first(self):
        # 0x80 = 1000 0000 (MSB first)
        bits = bytes_to_bits(b"\x80")
        assert bits.tolist() == [1, 0, 0, 0, 0, 0, 0, 0]

    def test_zero_byte(self):
        bits = bytes_to_bits(b"\x00")
        assert bits.tolist() == [0] * 8

    def test_multibyte(self):
        # 0xFF 0x00 -> all 1s then all 0s
        bits = bytes_to_bits(b"\xff\x00")
        assert bits.tolist() == [1] * 8 + [0] * 8

    def test_accepts_ndarray(self):
        arr = np.frombuffer(b"\xff", dtype=np.uint8)
        bits = bytes_to_bits(arr)
        assert bits.tolist() == [1] * 8


class TestCollectBits:
    def test_returns_correct_length(self):
        bits = collect_bits(SoftwareHashEngine(), hash_count=10)
        assert bits.size == 10 * 32 * 8  # 10 hashes * 32 bytes * 8 bits

    def test_zero_count_rejected(self):
        with pytest.raises(ValueError):
            collect_bits(SoftwareHashEngine(), hash_count=0)

    def test_negative_count_rejected(self):
        with pytest.raises(ValueError):
            collect_bits(SoftwareHashEngine(), hash_count=-1)


# -------------------------------------------------------------------
# RandomnessBattery
# -------------------------------------------------------------------


class TestRandomnessBattery:
    def test_run_returns_snapshot(self):
        battery = RandomnessBattery()
        snap = battery.run(hash_count=20)
        assert isinstance(snap, RandomnessSnapshot)

    def test_run_records_metadata(self):
        battery = RandomnessBattery()
        snap = battery.run(hash_count=20)
        assert snap.sample_count == 20
        assert snap.bit_count == 20 * 256
        assert snap.engine_name == "software-sha256d"
        assert snap.duration_seconds >= 0.0
        assert snap.alpha == 0.01

    def test_run_includes_cusum_both_directions(self):
        battery = RandomnessBattery()
        snap = battery.run(hash_count=20)
        names = {r["name"] for r in snap.results}
        assert "cumulative_sums_forward" in names
        assert "cumulative_sums_reverse" in names

    def test_run_includes_all_default_tests(self):
        battery = RandomnessBattery()
        snap = battery.run(hash_count=20)
        names = {r["name"] for r in snap.results}
        expected = {
            "frequency_monobit",
            "block_frequency",
            "runs",
            "longest_run",
            "dft_spectral",
            "cumulative_sums_forward",
            "cumulative_sums_reverse",
        }
        assert expected.issubset(names)

    def test_pass_count(self):
        battery = RandomnessBattery()
        snap = battery.run(hash_count=20)
        assert snap.pass_count + snap.fail_count == len(snap.results)
        # SHA-256d should pass all enabled tests at this size
        assert snap.fail_count == 0

    def test_custom_test_subset(self):
        battery = RandomnessBattery(tests=[frequency_test])
        snap = battery.run(hash_count=10)
        assert len(snap.results) == 1
        assert snap.results[0]["name"] == "frequency_monobit"

    def test_custom_alpha(self):
        battery = RandomnessBattery(alpha=0.05)
        snap = battery.run(hash_count=10)
        assert snap.alpha == 0.05


# -------------------------------------------------------------------
# Snapshot JSON round-trip
# -------------------------------------------------------------------


class TestSnapshotJson:
    def test_roundtrip(self, tmp_path):
        battery = RandomnessBattery()
        snap = battery.run(hash_count=20)
        path = tmp_path / "snap.json"
        snap.save(path)
        reloaded = RandomnessSnapshot.load(path)
        assert reloaded.sample_count == snap.sample_count
        assert reloaded.engine_name == snap.engine_name
        assert len(reloaded.results) == len(snap.results)

    def test_json_is_valid(self, tmp_path):
        battery = RandomnessBattery()
        snap = battery.run(hash_count=20)
        text = snap.to_json()
        parsed = json.loads(text)
        assert "results" in parsed
        assert isinstance(parsed["results"], list)
