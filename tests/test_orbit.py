"""Tests for bfl_asic.dynamics.orbit -- core orbit computation."""

from __future__ import annotations

import hashlib
import os

import numpy as np
import pytest

from bfl_asic.dynamics.orbit import (
    OrbitPoint,
    OrbitResult,
    compute_orbit,
    detect_fixed_point,
    hamming_distance,
    sha256_iterate,
)


# -------------------------------------------------------------------
# sha256_iterate
# -------------------------------------------------------------------

class TestSha256Iterate:
    """Tests for the single SHA-256 iteration primitive."""

    def test_produces_32_bytes(self):
        """Output is exactly 32 bytes."""
        inp = b"\x00" * 32
        out = sha256_iterate(inp)
        assert isinstance(out, bytes)
        assert len(out) == 32

    def test_matches_hashlib(self):
        """Output matches hashlib.sha256(x).digest()."""
        inp = os.urandom(32)
        assert sha256_iterate(inp) == hashlib.sha256(inp).digest()

    def test_deterministic(self):
        """Same input always gives same output."""
        inp = b"\xab" * 32
        assert sha256_iterate(inp) == sha256_iterate(inp)

    def test_different_inputs_different_outputs(self):
        """Different inputs produce different outputs (with overwhelming probability)."""
        a = b"\x00" * 32
        b = b"\x01" * 32
        assert sha256_iterate(a) != sha256_iterate(b)


# -------------------------------------------------------------------
# hamming_distance
# -------------------------------------------------------------------

class TestHammingDistance:
    """Tests for the Hamming distance function."""

    def test_identical_inputs_zero(self):
        """Hamming distance of identical inputs is 0."""
        val = os.urandom(32)
        assert hamming_distance(val, val) == 0

    def test_all_zeros_vs_all_ones_is_256(self):
        """Hamming distance of all-zeros vs all-ones is 256 bits."""
        a = b"\x00" * 32
        b = b"\xff" * 32
        assert hamming_distance(a, b) == 256

    def test_single_bit_flip(self):
        """Flipping one bit gives Hamming distance 1."""
        a = b"\x00" * 32
        b = b"\x01" + b"\x00" * 31
        assert hamming_distance(a, b) == 1

    def test_symmetric(self):
        """hamming_distance(a, b) == hamming_distance(b, a)."""
        a = os.urandom(32)
        b = os.urandom(32)
        assert hamming_distance(a, b) == hamming_distance(b, a)

    def test_range_0_to_256(self):
        """Result is always in [0, 256] for 32-byte inputs."""
        for _ in range(10):
            a = os.urandom(32)
            b = os.urandom(32)
            d = hamming_distance(a, b)
            assert 0 <= d <= 256


# -------------------------------------------------------------------
# detect_fixed_point
# -------------------------------------------------------------------

class TestDetectFixedPoint:
    """Tests for fixed point detection."""

    def test_random_values_not_fixed(self):
        """Random 32-byte values are almost certainly not fixed points."""
        for _ in range(10):
            val = os.urandom(32)
            assert detect_fixed_point(val) is False

    def test_specific_non_fixed_point(self):
        """A known non-fixed point returns False."""
        val = b"\x00" * 32
        assert detect_fixed_point(val) is False


# -------------------------------------------------------------------
# compute_orbit
# -------------------------------------------------------------------

class TestComputeOrbit:
    """Tests for the main orbit computation function."""

    def test_returns_orbit_result(self):
        """compute_orbit returns an OrbitResult instance."""
        seed = os.urandom(32)
        result = compute_orbit(seed, max_iterations=100, sample_interval=10)
        assert isinstance(result, OrbitResult)

    def test_iterations_field(self):
        """iterations field matches max_iterations."""
        seed = os.urandom(32)
        result = compute_orbit(seed, max_iterations=100, sample_interval=10)
        assert result.iterations == 100

    def test_seed_is_preserved(self):
        """The seed is stored in the result."""
        seed = os.urandom(32)
        result = compute_orbit(seed, max_iterations=100, sample_interval=10)
        assert result.seed == seed

    def test_trajectory_sample_contains_orbit_points(self):
        """trajectory_sample contains OrbitPoint objects."""
        seed = os.urandom(32)
        result = compute_orbit(seed, max_iterations=100, sample_interval=10)
        for pt in result.trajectory_sample:
            assert isinstance(pt, OrbitPoint)
            assert isinstance(pt.value, bytes)
            assert len(pt.value) == 32

    def test_trajectory_sample_at_correct_intervals(self):
        """Sample points are taken at the correct iteration intervals."""
        seed = os.urandom(32)
        result = compute_orbit(seed, max_iterations=100, sample_interval=10)
        # First point is the seed at iteration 0
        assert result.trajectory_sample[0].iteration == 0
        # Remaining points at multiples of sample_interval
        for pt in result.trajectory_sample[1:]:
            assert pt.iteration % 10 == 0

    def test_trajectory_sample_count(self):
        """Number of sample points is correct."""
        seed = os.urandom(32)
        result = compute_orbit(seed, max_iterations=100, sample_interval=10)
        # 1 (seed) + 100/10 = 11 sample points
        assert len(result.trajectory_sample) == 11

    def test_hamming_distances_populated(self):
        """hamming_distances list has the right number of entries."""
        seed = os.urandom(32)
        result = compute_orbit(seed, max_iterations=100, sample_interval=10)
        # 100/10 = 10 Hamming distances (between consecutive samples)
        assert len(result.hamming_distances) == 10

    def test_mean_hamming_in_expected_range(self):
        """Mean Hamming distance is between 100 and 150 for SHA-256 orbits.

        For a good hash function, consecutive hashes should be ~128 bits apart.
        """
        seed = os.urandom(32)
        result = compute_orbit(seed, max_iterations=10000, sample_interval=100)
        assert result.mean_hamming is not None
        assert 100 < result.mean_hamming < 150

    def test_min_max_hamming_consistent(self):
        """min_hamming <= mean_hamming <= max_hamming."""
        seed = os.urandom(32)
        result = compute_orbit(seed, max_iterations=1000, sample_interval=100)
        assert result.min_hamming is not None
        assert result.max_hamming is not None
        assert result.mean_hamming is not None
        assert result.min_hamming <= result.mean_hamming <= result.max_hamming

    def test_custom_hash_fn(self):
        """compute_orbit works with a custom hash function."""

        def identity_ish(value: bytes) -> bytes:
            """Rotate bytes by 1 position."""
            return value[1:] + value[:1]

        seed = b"\x00" * 31 + b"\x01"
        result = compute_orbit(seed, max_iterations=100, sample_interval=10, hash_fn=identity_ish)
        assert isinstance(result, OrbitResult)
        assert result.iterations == 100

    def test_seed_validation_wrong_length(self):
        """Seed that is not 32 bytes raises ValueError."""
        with pytest.raises(ValueError, match="32 bytes"):
            compute_orbit(b"\x00" * 16, max_iterations=10)

    def test_seed_validation_empty(self):
        """Empty seed raises ValueError."""
        with pytest.raises(ValueError, match="32 bytes"):
            compute_orbit(b"", max_iterations=10)

    def test_no_cycle_fields_set(self):
        """By default (without rho integration) cycle fields are None."""
        seed = os.urandom(32)
        result = compute_orbit(seed, max_iterations=100, sample_interval=10)
        assert result.tail_length is None
        assert result.cycle_length is None
        assert result.cycle_entry is None
