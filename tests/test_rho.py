"""Tests for bfl_asic.dynamics.rho -- cycle detection algorithms.

Uses a toy hash function (SHA-256 truncated to 3 bytes, zero-padded
to 32 bytes) so cycles are reachable in ~2^12 steps rather than ~2^128.
"""

from __future__ import annotations

import hashlib
import os

import pytest

from bfl_asic.dynamics.rho import CycleInfo, brent_detect, floyd_detect


# -------------------------------------------------------------------
# Toy hash function for testing
# -------------------------------------------------------------------

def toy_hash(value: bytes) -> bytes:
    """SHA-256 truncated to 3 bytes, zero-padded to 32 bytes.

    Creates a function on a ~2^24 state space where cycles are
    reachable in ~2^12 steps.
    """
    full = hashlib.sha256(value).digest()
    return full[:3].ljust(32, b"\x00")


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _verify_cycle(cycle_entry: bytes, cycle_length: int, hash_fn: callable) -> bool:
    """Verify that iterating cycle_length times from cycle_entry returns cycle_entry."""
    current = cycle_entry
    for _ in range(cycle_length):
        current = hash_fn(current)
    return current == cycle_entry


def _verify_tail(seed: bytes, tail_length: int, cycle_entry: bytes, hash_fn: callable) -> bool:
    """Verify that iterating tail_length times from seed reaches cycle_entry."""
    current = seed
    for _ in range(tail_length):
        current = hash_fn(current)
    return current == cycle_entry


# -------------------------------------------------------------------
# Floyd's algorithm
# -------------------------------------------------------------------

class TestFloydDetect:
    """Tests for Floyd's tortoise-and-hare cycle detection."""

    def test_finds_cycle_with_toy_hash(self):
        """Floyd's algorithm finds a cycle using the toy hash."""
        seed = b"\x42" * 32
        result = floyd_detect(seed, max_steps=500_000, hash_fn=toy_hash)
        assert result is not None
        assert isinstance(result, CycleInfo)

    def test_cycle_length_positive(self):
        """Detected cycle length is > 0."""
        seed = b"\x42" * 32
        result = floyd_detect(seed, max_steps=500_000, hash_fn=toy_hash)
        assert result is not None
        assert result.cycle_length > 0

    def test_tail_length_non_negative(self):
        """Tail length is >= 0."""
        seed = b"\x42" * 32
        result = floyd_detect(seed, max_steps=500_000, hash_fn=toy_hash)
        assert result is not None
        assert result.tail_length >= 0

    def test_cycle_entry_is_32_bytes(self):
        """cycle_entry is 32 bytes."""
        seed = b"\x42" * 32
        result = floyd_detect(seed, max_steps=500_000, hash_fn=toy_hash)
        assert result is not None
        assert isinstance(result.cycle_entry, bytes)
        assert len(result.cycle_entry) == 32

    def test_verify_cycle_correctness(self):
        """Iterating cycle_length times from cycle_entry returns cycle_entry."""
        seed = b"\x42" * 32
        result = floyd_detect(seed, max_steps=500_000, hash_fn=toy_hash)
        assert result is not None
        assert _verify_cycle(result.cycle_entry, result.cycle_length, toy_hash)

    def test_verify_tail_correctness(self):
        """Iterating tail_length times from seed reaches cycle_entry."""
        seed = b"\x42" * 32
        result = floyd_detect(seed, max_steps=500_000, hash_fn=toy_hash)
        assert result is not None
        assert _verify_tail(seed, result.tail_length, result.cycle_entry, toy_hash)

    def test_returns_none_max_steps_too_small(self):
        """Returns None when max_steps is too small to find a cycle."""
        seed = b"\x42" * 32
        result = floyd_detect(seed, max_steps=10, hash_fn=toy_hash)
        assert result is None

    def test_full_sha256_no_cycle_in_1000_steps(self):
        """With full SHA-256 and max_steps=1000, cycle is unreachable."""
        seed = os.urandom(32)
        result = floyd_detect(seed, max_steps=1000)
        assert result is None


# -------------------------------------------------------------------
# Brent's algorithm
# -------------------------------------------------------------------

class TestBrentDetect:
    """Tests for Brent's cycle detection."""

    def test_finds_cycle_with_toy_hash(self):
        """Brent's algorithm finds a cycle using the toy hash."""
        seed = b"\x42" * 32
        result = brent_detect(seed, max_steps=500_000, hash_fn=toy_hash)
        assert result is not None
        assert isinstance(result, CycleInfo)

    def test_cycle_length_positive(self):
        """Detected cycle length is > 0."""
        seed = b"\x42" * 32
        result = brent_detect(seed, max_steps=500_000, hash_fn=toy_hash)
        assert result is not None
        assert result.cycle_length > 0

    def test_tail_length_non_negative(self):
        """Tail length is >= 0."""
        seed = b"\x42" * 32
        result = brent_detect(seed, max_steps=500_000, hash_fn=toy_hash)
        assert result is not None
        assert result.tail_length >= 0

    def test_cycle_entry_is_32_bytes(self):
        """cycle_entry is 32 bytes."""
        seed = b"\x42" * 32
        result = brent_detect(seed, max_steps=500_000, hash_fn=toy_hash)
        assert result is not None
        assert isinstance(result.cycle_entry, bytes)
        assert len(result.cycle_entry) == 32

    def test_verify_cycle_correctness(self):
        """Iterating cycle_length times from cycle_entry returns cycle_entry."""
        seed = b"\x42" * 32
        result = brent_detect(seed, max_steps=500_000, hash_fn=toy_hash)
        assert result is not None
        assert _verify_cycle(result.cycle_entry, result.cycle_length, toy_hash)

    def test_verify_tail_correctness(self):
        """Iterating tail_length times from seed reaches cycle_entry."""
        seed = b"\x42" * 32
        result = brent_detect(seed, max_steps=500_000, hash_fn=toy_hash)
        assert result is not None
        assert _verify_tail(seed, result.tail_length, result.cycle_entry, toy_hash)

    def test_returns_none_max_steps_too_small(self):
        """Returns None when max_steps is too small to find a cycle."""
        seed = b"\x42" * 32
        result = brent_detect(seed, max_steps=10, hash_fn=toy_hash)
        assert result is None

    def test_full_sha256_no_cycle_in_1000_steps(self):
        """With full SHA-256 and max_steps=1000, cycle is unreachable."""
        seed = os.urandom(32)
        result = brent_detect(seed, max_steps=1000)
        assert result is None


# -------------------------------------------------------------------
# Cross-algorithm consistency
# -------------------------------------------------------------------

class TestCrossAlgorithm:
    """Both algorithms should agree on the same seed."""

    def test_same_cycle_length(self):
        """Floyd and Brent find the same cycle_length for the same seed."""
        seed = b"\x42" * 32
        floyd = floyd_detect(seed, max_steps=500_000, hash_fn=toy_hash)
        brent = brent_detect(seed, max_steps=500_000, hash_fn=toy_hash)
        assert floyd is not None
        assert brent is not None
        assert floyd.cycle_length == brent.cycle_length

    def test_same_tail_length(self):
        """Floyd and Brent find the same tail_length for the same seed."""
        seed = b"\x42" * 32
        floyd = floyd_detect(seed, max_steps=500_000, hash_fn=toy_hash)
        brent = brent_detect(seed, max_steps=500_000, hash_fn=toy_hash)
        assert floyd is not None
        assert brent is not None
        assert floyd.tail_length == brent.tail_length

    def test_same_cycle_entry(self):
        """Floyd and Brent find the same cycle_entry for the same seed."""
        seed = b"\x42" * 32
        floyd = floyd_detect(seed, max_steps=500_000, hash_fn=toy_hash)
        brent = brent_detect(seed, max_steps=500_000, hash_fn=toy_hash)
        assert floyd is not None
        assert brent is not None
        assert floyd.cycle_entry == brent.cycle_entry

    def test_consistency_with_different_seed(self):
        """Cross-check with a different seed value."""
        seed = b"\xff" * 32
        floyd = floyd_detect(seed, max_steps=500_000, hash_fn=toy_hash)
        brent = brent_detect(seed, max_steps=500_000, hash_fn=toy_hash)
        assert floyd is not None
        assert brent is not None
        assert floyd.cycle_length == brent.cycle_length
        assert floyd.tail_length == brent.tail_length
        assert floyd.cycle_entry == brent.cycle_entry
