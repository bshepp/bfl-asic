"""Cycle detection algorithms for iterated hash dynamics.

Implements Floyd's tortoise-and-hare and Brent's power-of-two cycle
detection.  Both run in O(1) memory -- they only store a constant
number of hash values at any time.

The ``hash_fn`` parameter on each function allows injecting a custom
hash function for testing.  Default is full SHA-256.  For tests, a
truncated "toy hash" (SHA-256 truncated to 3 bytes) makes cycles
reachable in reasonable time.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib


def _sha256_iterate(value: bytes) -> bytes:
    """Single SHA-256 iteration: x -> SHA-256(x)."""
    return hashlib.sha256(value).digest()


# -------------------------------------------------------------------
# Data class
# -------------------------------------------------------------------

@dataclass
class CycleInfo:
    """Result of cycle detection."""

    tail_length: int  # Steps before entering cycle (lambda)
    cycle_length: int  # Length of the cycle (mu)
    cycle_entry: bytes  # The first repeated value


# -------------------------------------------------------------------
# Floyd's tortoise-and-hare
# -------------------------------------------------------------------

def floyd_detect(
    seed: bytes,
    max_steps: int = 1_000_000,
    hash_fn: callable | None = None,
) -> CycleInfo | None:
    """Floyd's tortoise-and-hare cycle detection.

    Phase 1: Move tortoise 1 step, hare 2 steps until they meet.
    Phase 2: Reset tortoise to start, move both 1 step to find cycle entry.
    Phase 3: Move hare around cycle to find cycle length.

    Parameters
    ----------
    seed:
        Starting value (32 bytes).
    max_steps:
        Maximum number of hare steps before giving up.
    hash_fn:
        Hash function to use.  Default is SHA-256.

    Returns
    -------
    CycleInfo or None
        ``None`` if *max_steps* exceeded without cycle detection.
    """
    if hash_fn is None:
        hash_fn = _sha256_iterate

    # Phase 1: find meeting point
    tortoise = hash_fn(seed)
    hare = hash_fn(hash_fn(seed))
    steps = 2  # hare has taken 2 steps so far

    while tortoise != hare:
        if steps >= max_steps:
            return None
        tortoise = hash_fn(tortoise)
        hare = hash_fn(hash_fn(hare))
        steps += 2

    # Phase 2: find cycle entry (tail length)
    tortoise = seed
    tail_length = 0

    while tortoise != hare:
        tortoise = hash_fn(tortoise)
        hare = hash_fn(hare)
        tail_length += 1

    cycle_entry = tortoise

    # Phase 3: find cycle length
    cycle_length = 1
    hare = hash_fn(tortoise)

    while hare != tortoise:
        hare = hash_fn(hare)
        cycle_length += 1

    return CycleInfo(
        tail_length=tail_length,
        cycle_length=cycle_length,
        cycle_entry=cycle_entry,
    )


# -------------------------------------------------------------------
# Brent's algorithm
# -------------------------------------------------------------------

def brent_detect(
    seed: bytes,
    max_steps: int = 1_000_000,
    hash_fn: callable | None = None,
) -> CycleInfo | None:
    """Brent's cycle detection (generally faster than Floyd's).

    Uses a power-of-two search strategy.

    Phase 1: Find cycle length mu using power-of-two search.
    Phase 2: Find cycle entry point (tail length lambda).

    Parameters
    ----------
    seed:
        Starting value (32 bytes).
    max_steps:
        Maximum number of steps before giving up.
    hash_fn:
        Hash function to use.  Default is SHA-256.

    Returns
    -------
    CycleInfo or None
        ``None`` if *max_steps* exceeded.
    """
    if hash_fn is None:
        hash_fn = _sha256_iterate

    # Phase 1: find cycle length using power-of-two teleportation
    power = 1
    cycle_length = 1
    tortoise = seed
    hare = hash_fn(seed)
    total_steps = 1

    while tortoise != hare:
        if total_steps >= max_steps:
            return None
        if cycle_length == power:
            # Teleport tortoise to hare position
            tortoise = hare
            power *= 2
            cycle_length = 0
        hare = hash_fn(hare)
        cycle_length += 1
        total_steps += 1

    # Phase 2: find cycle entry (tail length)
    # Advance hare cycle_length steps ahead of tortoise, both starting from seed
    tortoise = seed
    hare = seed
    for _ in range(cycle_length):
        hare = hash_fn(hare)

    tail_length = 0
    while tortoise != hare:
        tortoise = hash_fn(tortoise)
        hare = hash_fn(hare)
        tail_length += 1

    cycle_entry = tortoise

    return CycleInfo(
        tail_length=tail_length,
        cycle_length=cycle_length,
        cycle_entry=cycle_entry,
    )
