"""Orchestrator that runs the NIST SP 800-22 test battery against a HashSource."""

from __future__ import annotations

import time
from typing import Callable, Iterable

import numpy as np

from bfl_asic.randomness.snapshot import RandomnessSnapshot
from bfl_asic.randomness.tests import (
    ALL_TESTS,
    DEFAULT_ALPHA,
    TestResult,
    cumulative_sums_test,
)
from bfl_asic.stats.engine import HashSource, SoftwareHashEngine


def bytes_to_bits(buf: bytes | np.ndarray) -> np.ndarray:
    """Convert a bytes-like object to a 1-D uint8 bit array (MSB-first per byte)."""
    if isinstance(buf, np.ndarray):
        buf = buf.tobytes()
    return np.unpackbits(np.frombuffer(buf, dtype=np.uint8))


def collect_bits(source: HashSource, hash_count: int) -> np.ndarray:
    """Drain ``hash_count`` 32-byte digests from *source* into a flat bit array."""
    if hash_count <= 0:
        raise ValueError("hash_count must be positive")
    buf = bytearray(hash_count * 32)
    for i, (_inp, out) in enumerate(source.hashes(count=hash_count)):
        buf[i * 32:(i + 1) * 32] = out
    return bytes_to_bits(bytes(buf))


class RandomnessBattery:
    """Run NIST SP 800-22 tests against the bit stream of a :class:`HashSource`.

    The battery harvests ``hash_count`` hashes (256 bits each), assembles them
    into a single 1-D bit array, and applies each enabled test.
    """

    def __init__(
        self,
        engine: HashSource | None = None,
        alpha: float = DEFAULT_ALPHA,
        tests: Iterable[Callable[..., TestResult]] | None = None,
    ) -> None:
        self._engine = engine or SoftwareHashEngine()
        self._alpha = alpha
        self._tests = list(tests) if tests is not None else list(ALL_TESTS)

    def run(self, hash_count: int = 1000) -> RandomnessSnapshot:
        """Collect ``hash_count`` digests and run every enabled test once."""
        start = time.monotonic()
        bits = collect_bits(self._engine, hash_count)
        results: list[TestResult] = []
        for test_fn in self._tests:
            if test_fn is cumulative_sums_test:
                results.append(test_fn(bits, mode="forward", alpha=self._alpha))
                results.append(test_fn(bits, mode="reverse", alpha=self._alpha))
            else:
                results.append(test_fn(bits, alpha=self._alpha))
        elapsed = time.monotonic() - start
        return RandomnessSnapshot.from_results(
            engine_name=self._engine.name(),
            sample_count=hash_count,
            bit_count=int(bits.size),
            duration_seconds=elapsed,
            alpha=self._alpha,
            results=results,
        )

    @property
    def engine(self) -> HashSource:
        return self._engine
