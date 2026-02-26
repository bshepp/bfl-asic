"""Multi-seed convergence analysis for iterated hash dynamics.

Runs multiple iterated-hash orbits in parallel and detects when two
orbits visit the same state ("convergence").  This reveals funnel
structure in SHA-256's state graph.
"""

from __future__ import annotations

from dataclasses import dataclass
import os

from bfl_asic.dynamics.orbit import (
    OrbitResult,
    compute_orbit,
    sha256_iterate,
)


# -------------------------------------------------------------------
# Data class
# -------------------------------------------------------------------

@dataclass
class ConvergenceResult:
    """Results from multi-seed convergence analysis."""

    seed_count: int
    max_iterations: int
    orbits: list[OrbitResult]
    convergence_pairs: list[tuple[int, int, int]]  # (seed_idx_a, seed_idx_b, iteration)
    common_states: int  # Count of states visited by multiple seeds


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def generate_random_seeds(count: int) -> list[bytes]:
    """Generate *count* random 32-byte seeds."""
    return [os.urandom(32) for _ in range(count)]


# -------------------------------------------------------------------
# Convergence analysis
# -------------------------------------------------------------------

def analyze_convergence(
    seeds: list[bytes],
    max_iterations: int = 100_000,
    check_interval: int = 100,
    hash_fn: callable | None = None,
) -> ConvergenceResult:
    """Run multiple orbits and detect convergence.

    At each *check_interval* step, records the current state of all
    orbits and checks for matches.  Uses a dict mapping
    ``state -> (seed_idx, step)`` for O(1) convergence detection.

    Memory: O(num_seeds * max_iterations / check_interval) for state
    snapshots.

    Parameters
    ----------
    seeds:
        List of 32-byte starting values.
    max_iterations:
        Number of hash iterations per orbit.
    check_interval:
        Record and compare states every N steps.
    hash_fn:
        Hash function to use.  Default is :func:`sha256_iterate`.

    Returns
    -------
    ConvergenceResult
        Convergence analysis results including detected convergence pairs.
    """
    if hash_fn is None:
        hash_fn = sha256_iterate

    num_seeds = len(seeds)

    # Current state of each orbit
    current_states = list(seeds)

    # Map from state bytes -> (seed_idx, step) for first visitor
    state_registry: dict[bytes, tuple[int, int]] = {}

    # Record convergence events
    convergence_pairs: list[tuple[int, int, int]] = []

    # Track which states were visited by multiple seeds
    multi_visit_states: set[bytes] = set()

    # Register initial states (step 0)
    for idx, s in enumerate(seeds):
        if s in state_registry:
            prev_idx, prev_step = state_registry[s]
            convergence_pairs.append((prev_idx, idx, 0))
            multi_visit_states.add(s)
        else:
            state_registry[s] = (idx, 0)

    # Iterate all orbits in lock-step
    for step in range(1, max_iterations + 1):
        for idx in range(num_seeds):
            current_states[idx] = hash_fn(current_states[idx])

        # At check intervals, record and compare
        if step % check_interval == 0:
            for idx in range(num_seeds):
                state = current_states[idx]
                if state in state_registry:
                    prev_idx, prev_step = state_registry[state]
                    if prev_idx != idx:
                        convergence_pairs.append((prev_idx, idx, step))
                        multi_visit_states.add(state)
                else:
                    state_registry[state] = (idx, step)

    # Compute individual orbit results
    orbits: list[OrbitResult] = []
    for seed in seeds:
        orbit = compute_orbit(
            seed=seed,
            max_iterations=max_iterations,
            sample_interval=max(1, check_interval),
            hash_fn=hash_fn,
        )
        orbits.append(orbit)

    return ConvergenceResult(
        seed_count=num_seeds,
        max_iterations=max_iterations,
        orbits=orbits,
        convergence_pairs=convergence_pairs,
        common_states=len(multi_visit_states),
    )
