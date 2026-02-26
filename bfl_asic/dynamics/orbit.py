"""Core orbit computation for iterated hash dynamics.

Studies the orbit structure of SHA-256 as a discrete dynamical system:
x0 -> SHA-256(x0) = x1 -> SHA-256(x1) = x2 -> ...

Does NOT store the full trajectory (would be huge for millions of
iterations).  Instead, samples trajectory points and Hamming distances
at configurable intervals and computes aggregate statistics.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

import numpy as np


# -------------------------------------------------------------------
# Data classes
# -------------------------------------------------------------------

@dataclass
class OrbitPoint:
    """Single point in an iterated hash orbit."""

    iteration: int
    value: bytes  # 32 bytes


@dataclass
class OrbitResult:
    """Complete result of an orbit computation."""

    seed: bytes
    iterations: int
    tail_length: int | None  # None if no cycle detected
    cycle_length: int | None  # None if no cycle detected
    cycle_entry: bytes | None  # First repeated value
    is_fixed_point: bool  # SHA-256(x) == x found
    trajectory_sample: list[OrbitPoint]  # Sampled points for visualization
    hamming_distances: list[int]  # Hamming distances between consecutive samples
    mean_hamming: float | None  # Mean Hamming distance
    min_hamming: int | None
    max_hamming: int | None


# -------------------------------------------------------------------
# Primitive operations
# -------------------------------------------------------------------

def sha256_iterate(value: bytes) -> bytes:
    """Single SHA-256 iteration: x -> SHA-256(x).

    Input and output are 32 bytes.
    """
    return hashlib.sha256(value).digest()


def hamming_distance(a: bytes, b: bytes) -> int:
    """Compute Hamming distance (number of differing bits) between two byte strings."""
    arr_a = np.frombuffer(a, dtype=np.uint8)
    arr_b = np.frombuffer(b, dtype=np.uint8)
    return int(np.unpackbits(np.bitwise_xor(arr_a, arr_b)).sum())


def detect_fixed_point(value: bytes) -> bool:
    """Check if SHA-256(value) == value."""
    return hashlib.sha256(value).digest() == value


# -------------------------------------------------------------------
# Orbit computation
# -------------------------------------------------------------------

def compute_orbit(
    seed: bytes,
    max_iterations: int = 1_000_000,
    sample_interval: int = 1000,
    hash_fn: callable | None = None,
) -> OrbitResult:
    """Compute an iterated hash orbit from *seed*.

    Does NOT store the full trajectory (would be huge).  Tracks:

    - Sampled trajectory points at *sample_interval* intervals
    - Hamming distances between consecutive sampled points
    - Fixed point detection
    - Statistics (mean / min / max Hamming distance)

    Parameters
    ----------
    seed:
        32-byte starting value.
    max_iterations:
        Stop after this many iterations.
    sample_interval:
        Save orbit points and Hamming distances every N steps.
    hash_fn:
        Hash function to use (default: :func:`sha256_iterate`).
        Accepts ``bytes``, returns ``bytes``.
        This allows using truncated hash functions for testing.

    Returns
    -------
    OrbitResult
        Aggregate statistics and sampled trajectory.

    Raises
    ------
    ValueError
        If *seed* is not exactly 32 bytes.
    """
    if len(seed) != 32:
        raise ValueError(f"seed must be exactly 32 bytes, got {len(seed)}")

    if hash_fn is None:
        hash_fn = sha256_iterate

    trajectory_sample: list[OrbitPoint] = []
    hamming_distances: list[int] = []
    is_fixed_point = False

    current = seed
    prev_sample = seed

    # Always record the seed as the first sample point
    trajectory_sample.append(OrbitPoint(iteration=0, value=seed))

    for i in range(1, max_iterations + 1):
        next_val = hash_fn(current)

        # Fixed point detection: SHA-256(x) == x
        # Check if the *previous* value was a fixed point (i.e. hashing
        # it gave back the same value).
        if next_val == current:
            is_fixed_point = True

        current = next_val

        # Sample at intervals
        if i % sample_interval == 0:
            hd = hamming_distance(prev_sample, current)
            hamming_distances.append(hd)
            trajectory_sample.append(OrbitPoint(iteration=i, value=current))
            prev_sample = current

    # Compute aggregate statistics
    mean_hamming: float | None = None
    min_hamming: int | None = None
    max_hamming: int | None = None

    if hamming_distances:
        arr = np.array(hamming_distances, dtype=np.float64)
        mean_hamming = float(arr.mean())
        min_hamming = int(arr.min())
        max_hamming = int(arr.max())

    return OrbitResult(
        seed=seed,
        iterations=max_iterations,
        tail_length=None,
        cycle_length=None,
        cycle_entry=None,
        is_fixed_point=is_fixed_point,
        trajectory_sample=trajectory_sample,
        hamming_distances=hamming_distances,
        mean_hamming=mean_hamming,
        min_hamming=min_hamming,
        max_hamming=max_hamming,
    )
