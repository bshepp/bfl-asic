"""Tests for bfl_asic.dynamics.convergence -- multi-seed convergence analysis."""

from __future__ import annotations

import hashlib
import os

import pytest

from bfl_asic.dynamics.convergence import (
    ConvergenceResult,
    analyze_convergence,
    generate_random_seeds,
)
from bfl_asic.dynamics.orbit import OrbitResult


# -------------------------------------------------------------------
# Toy hash function for testing
# -------------------------------------------------------------------

def toy_hash(value: bytes) -> bytes:
    """SHA-256 truncated to 3 bytes, zero-padded to 32 bytes.

    Creates a function on a ~2^24 state space where convergence is
    more likely to occur within reasonable iteration counts.
    """
    full = hashlib.sha256(value).digest()
    return full[:3].ljust(32, b"\x00")


# -------------------------------------------------------------------
# generate_random_seeds
# -------------------------------------------------------------------

class TestGenerateRandomSeeds:
    """Tests for random seed generation."""

    def test_returns_correct_count(self):
        """generate_random_seeds(5) returns exactly 5 seeds."""
        seeds = generate_random_seeds(5)
        assert len(seeds) == 5

    def test_each_seed_is_32_bytes(self):
        """Each seed is exactly 32 bytes."""
        seeds = generate_random_seeds(5)
        for seed in seeds:
            assert isinstance(seed, bytes)
            assert len(seed) == 32

    def test_seeds_are_unique(self):
        """All 5 seeds should be unique (with overwhelming probability)."""
        seeds = generate_random_seeds(5)
        assert len(set(seeds)) == 5

    def test_zero_count(self):
        """generate_random_seeds(0) returns an empty list."""
        seeds = generate_random_seeds(0)
        assert seeds == []


# -------------------------------------------------------------------
# analyze_convergence
# -------------------------------------------------------------------

class TestAnalyzeConvergence:
    """Tests for the convergence analysis function."""

    def test_returns_convergence_result(self):
        """analyze_convergence returns a ConvergenceResult."""
        seeds = [os.urandom(32) for _ in range(3)]
        result = analyze_convergence(
            seeds, max_iterations=100, check_interval=10, hash_fn=toy_hash
        )
        assert isinstance(result, ConvergenceResult)

    def test_seed_count_matches_input(self):
        """seed_count field matches the number of input seeds."""
        seeds = [os.urandom(32) for _ in range(3)]
        result = analyze_convergence(
            seeds, max_iterations=100, check_interval=10, hash_fn=toy_hash
        )
        assert result.seed_count == 3

    def test_orbits_list_correct_length(self):
        """orbits list has one entry per seed."""
        seeds = [os.urandom(32) for _ in range(4)]
        result = analyze_convergence(
            seeds, max_iterations=100, check_interval=10, hash_fn=toy_hash
        )
        assert len(result.orbits) == 4

    def test_orbits_are_orbit_results(self):
        """Each orbit entry is an OrbitResult."""
        seeds = [os.urandom(32) for _ in range(2)]
        result = analyze_convergence(
            seeds, max_iterations=100, check_interval=10, hash_fn=toy_hash
        )
        for orbit in result.orbits:
            assert isinstance(orbit, OrbitResult)

    def test_max_iterations_stored(self):
        """max_iterations field is correctly stored."""
        seeds = [os.urandom(32) for _ in range(2)]
        result = analyze_convergence(
            seeds, max_iterations=500, check_interval=10, hash_fn=toy_hash
        )
        assert result.max_iterations == 500

    def test_convergence_pairs_is_list_of_tuples(self):
        """convergence_pairs is a list of (seed_idx_a, seed_idx_b, iteration) tuples."""
        seeds = [os.urandom(32) for _ in range(3)]
        result = analyze_convergence(
            seeds, max_iterations=100, check_interval=10, hash_fn=toy_hash
        )
        assert isinstance(result.convergence_pairs, list)
        for pair in result.convergence_pairs:
            assert isinstance(pair, tuple)
            assert len(pair) == 3

    def test_common_states_non_negative(self):
        """common_states is non-negative."""
        seeds = [os.urandom(32) for _ in range(3)]
        result = analyze_convergence(
            seeds, max_iterations=100, check_interval=10, hash_fn=toy_hash
        )
        assert result.common_states >= 0

    def test_toy_hash_convergence_possible(self):
        """With toy_hash and enough iterations, convergence may be detected.

        We use many seeds and enough iterations to increase the chance.
        This is a probabilistic test -- with 10 seeds in a 2^24 space
        and 50000 iterations, convergence is likely.
        """
        seeds = [os.urandom(32) for _ in range(10)]
        result = analyze_convergence(
            seeds, max_iterations=50_000, check_interval=50, hash_fn=toy_hash
        )
        # We just verify the structure is valid; convergence is probabilistic
        assert isinstance(result, ConvergenceResult)
        assert result.seed_count == 10

    def test_full_sha256_no_convergence_low_iterations(self):
        """With full SHA-256 and low iterations, no convergence is expected."""
        seeds = [os.urandom(32) for _ in range(3)]
        result = analyze_convergence(
            seeds, max_iterations=100, check_interval=10
        )
        assert result.convergence_pairs == []
        assert result.common_states == 0

    def test_identical_seeds_converge_immediately(self):
        """If two seeds are identical, convergence is detected at step 0."""
        seed = os.urandom(32)
        seeds = [seed, seed]
        result = analyze_convergence(
            seeds, max_iterations=100, check_interval=10, hash_fn=toy_hash
        )
        # At least one convergence pair at step 0
        assert any(step == 0 for _, _, step in result.convergence_pairs)
        assert result.common_states >= 1
