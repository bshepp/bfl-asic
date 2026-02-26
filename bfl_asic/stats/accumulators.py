"""Real-time statistical accumulators for SHA-256d hash analysis.

Each accumulator processes ``(input, output)`` pairs and maintains compact
internal counters.  All share a common protocol:

* :meth:`ingest` -- accept one ``(hash_input, hash_output)`` pair.
* :meth:`report` -- return a summary dict of the accumulated statistics.
* :meth:`reset` -- clear all state back to initial values.
* :attr:`sample_count` -- number of ``ingest`` calls since last reset.

Accumulators
------------
* :class:`BitFrequencyAccumulator` -- per-bit frequency of 1s.
* :class:`AvalancheAccumulator` -- Hamming distance between consecutive outputs.
* :class:`BitCorrelationAccumulator` -- pairwise bit co-occurrence.
* :class:`NearCollisionAccumulator` -- hash pairs within small Hamming distance.
* :class:`ByteDistributionAccumulator` -- byte value histogram.
* :class:`EntropyAccumulator` -- running Shannon entropy estimate.
* :class:`CompositeAccumulator` -- runs all accumulators in parallel.
"""

from __future__ import annotations

import collections
import math

import numpy as np


# -------------------------------------------------------------------
# BitFrequencyAccumulator
# -------------------------------------------------------------------

class BitFrequencyAccumulator:
    """Track how often each of 256 bit positions is 1.

    Internal state is a ``numpy.ndarray`` of shape ``(256,)`` with dtype
    ``int64`` counting 1-bits at each position.
    """

    def __init__(self) -> None:
        self._counts: np.ndarray = np.zeros(256, dtype=np.int64)
        self._sample_count: int = 0

    def ingest(self, hash_input: bytes, hash_output: bytes) -> None:
        """Record one hash output, updating per-bit counts."""
        bits = np.unpackbits(np.frombuffer(hash_output, dtype=np.uint8))
        self._counts += bits.astype(np.int64)
        self._sample_count += 1

    def report(self) -> dict:
        """Return bit frequency statistics.

        Keys
        ----
        bit_frequencies : list[float]
            256 floats -- count / total for each bit position.
        max_bias : float
            Maximum ``|frequency - 0.5|`` across all positions.
        mean_bias : float
            Mean ``|frequency - 0.5|`` across all positions.
        chi_squared : float
            Chi-squared statistic vs expected 0.5 for each bit.
        """
        if self._sample_count == 0:
            return {
                "bit_frequencies": [0.0] * 256,
                "max_bias": 0.0,
                "mean_bias": 0.0,
                "chi_squared": 0.0,
            }
        freqs = self._counts / self._sample_count
        biases = np.abs(freqs - 0.5)
        expected = self._sample_count * 0.5
        chi_squared = float(np.sum((self._counts - expected) ** 2 / expected))
        return {
            "bit_frequencies": freqs.tolist(),
            "max_bias": float(biases.max()),
            "mean_bias": float(biases.mean()),
            "chi_squared": chi_squared,
        }

    def reset(self) -> None:
        """Clear all state back to initial values."""
        self._counts[:] = 0
        self._sample_count = 0

    @property
    def sample_count(self) -> int:
        """Number of ingested samples."""
        return self._sample_count


# -------------------------------------------------------------------
# AvalancheAccumulator
# -------------------------------------------------------------------

class AvalancheAccumulator:
    """Track Hamming distance between consecutive hash outputs.

    Internal state is a histogram ``numpy.ndarray`` of shape ``(257,)``
    (distances 0 through 256 inclusive) plus the previous output bytes.
    """

    def __init__(self) -> None:
        self._histogram: np.ndarray = np.zeros(257, dtype=np.int64)
        self._prev_output: bytes | None = None
        self._sample_count: int = 0

    def ingest(self, hash_input: bytes, hash_output: bytes) -> None:
        """Record one hash output, updating the Hamming distance histogram."""
        if self._prev_output is not None:
            xor_bytes = bytes(a ^ b for a, b in zip(self._prev_output, hash_output))
            distance = int(
                np.unpackbits(np.frombuffer(xor_bytes, dtype=np.uint8)).sum()
            )
            self._histogram[distance] += 1
        self._prev_output = hash_output
        self._sample_count += 1

    def report(self) -> dict:
        """Return Hamming distance statistics.

        Keys
        ----
        histogram : list[int]
            257 integers -- count at each Hamming distance 0..256.
        mean : float
            Mean Hamming distance (should be ~128 for random hashes).
        std : float
            Standard deviation.
        min : int
            Minimum observed distance.
        max : int
            Maximum observed distance.
        pairs_counted : int
            Number of consecutive pairs compared (``sample_count - 1``).
        """
        pairs = max(0, self._sample_count - 1)
        if pairs == 0:
            return {
                "histogram": self._histogram.tolist(),
                "mean": 0.0,
                "std": 0.0,
                "min": 0,
                "max": 0,
                "pairs_counted": 0,
            }
        distances = np.arange(257)
        total = self._histogram.sum()
        mean = float(np.sum(distances * self._histogram) / total)
        variance = float(
            np.sum(((distances - mean) ** 2) * self._histogram) / total
        )
        std = math.sqrt(variance)
        nonzero = np.nonzero(self._histogram)[0]
        return {
            "histogram": self._histogram.tolist(),
            "mean": mean,
            "std": std,
            "min": int(nonzero[0]),
            "max": int(nonzero[-1]),
            "pairs_counted": pairs,
        }

    def reset(self) -> None:
        """Clear all state back to initial values."""
        self._histogram[:] = 0
        self._prev_output = None
        self._sample_count = 0

    @property
    def sample_count(self) -> int:
        """Number of ingested samples."""
        return self._sample_count


# -------------------------------------------------------------------
# BitCorrelationAccumulator
# -------------------------------------------------------------------

class BitCorrelationAccumulator:
    """Track pairwise bit co-occurrence for selected bit positions.

    Parameters
    ----------
    positions:
        List of bit positions to track.  ``None`` tracks all 256.
    """

    def __init__(self, positions: list[int] | None = None) -> None:
        if positions is None:
            positions = list(range(256))
        self._positions: list[int] = positions
        k = len(positions)
        self._cooccurrence: np.ndarray = np.zeros((k, k), dtype=np.int64)
        self._sample_count: int = 0

    def ingest(self, hash_input: bytes, hash_output: bytes) -> None:
        """Record one hash output, updating pairwise co-occurrence counts."""
        all_bits = np.unpackbits(np.frombuffer(hash_output, dtype=np.uint8))
        bits = all_bits[self._positions].astype(np.int64)
        self._cooccurrence += bits[:, None] & bits[None, :]
        self._sample_count += 1

    def report(self) -> dict:
        """Return correlation statistics.

        Keys
        ----
        cooccurrence : list[list[int]]
            2D co-occurrence counts.
        positions : list[int]
            Tracked bit position indices.
        expected_cooccurrence : float
            ``0.25 * sample_count`` (independence assumption).
        max_deviation : float
            Maximum ``|observed/total - 0.25|`` across all pairs.
        correlation_matrix : list[list[float]]
            2D matrix of ``observed / total`` values.
        """
        if self._sample_count == 0:
            k = len(self._positions)
            return {
                "cooccurrence": self._cooccurrence.tolist(),
                "positions": self._positions,
                "expected_cooccurrence": 0.0,
                "max_deviation": 0.0,
                "correlation_matrix": [[0.0] * k for _ in range(k)],
            }
        corr = self._cooccurrence / self._sample_count
        deviation = np.abs(corr - 0.25)
        return {
            "cooccurrence": self._cooccurrence.tolist(),
            "positions": self._positions,
            "expected_cooccurrence": 0.25 * self._sample_count,
            "max_deviation": float(deviation.max()),
            "correlation_matrix": corr.tolist(),
        }

    def reset(self) -> None:
        """Clear all state back to initial values."""
        self._cooccurrence[:, :] = 0
        self._sample_count = 0

    @property
    def sample_count(self) -> int:
        """Number of ingested samples."""
        return self._sample_count


# -------------------------------------------------------------------
# NearCollisionAccumulator
# -------------------------------------------------------------------

class NearCollisionAccumulator:
    """Detect hash pairs within small Hamming distance.

    Parameters
    ----------
    max_distance:
        Maximum Hamming distance to record (default 16).
    window_size:
        Number of recent hashes to keep for comparison (default 1000).
    """

    def __init__(
        self, max_distance: int = 16, window_size: int = 1000
    ) -> None:
        self._max_distance = max_distance
        self._window_size = window_size
        self._window: collections.deque[bytes] = collections.deque(
            maxlen=window_size
        )
        self._collision_counts: dict[int, int] = {}
        self._comparisons_made: int = 0
        self._sample_count: int = 0

    def ingest(self, hash_input: bytes, hash_output: bytes) -> None:
        """Compare new hash against the sliding window and record collisions."""
        if len(self._window) > 0:
            # Stack window hashes into a 2D numpy array for vectorised comparison
            window_arr = np.frombuffer(
                b"".join(self._window), dtype=np.uint8
            ).reshape(-1, 32)
            new_arr = np.frombuffer(hash_output, dtype=np.uint8)
            xor_arr = window_arr ^ new_arr  # shape (n, 32)
            # Popcount each row: unpack all bits, reshape, sum per row
            bits = np.unpackbits(xor_arr.ravel()).reshape(-1, 256)
            distances = bits.sum(axis=1)  # shape (n,)
            self._comparisons_made += len(self._window)
            for d in range(1, self._max_distance + 1):
                count = int(np.sum(distances == d))
                if count > 0:
                    self._collision_counts[d] = (
                        self._collision_counts.get(d, 0) + count
                    )
        self._window.append(hash_output)
        self._sample_count += 1

    def report(self) -> dict:
        """Return near-collision statistics.

        Keys
        ----
        collision_counts : dict[int, int]
            Mapping of Hamming distance to number of observed collisions.
        window_size : int
            Current number of hashes in the window.
        max_distance : int
            Maximum tracked distance threshold.
        comparisons_made : int
            Total number of pairwise comparisons performed.
        """
        return {
            "collision_counts": dict(self._collision_counts),
            "window_size": len(self._window),
            "max_distance": self._max_distance,
            "comparisons_made": self._comparisons_made,
        }

    def reset(self) -> None:
        """Clear all state back to initial values."""
        self._window.clear()
        self._collision_counts.clear()
        self._comparisons_made = 0
        self._sample_count = 0

    @property
    def sample_count(self) -> int:
        """Number of ingested samples."""
        return self._sample_count


# -------------------------------------------------------------------
# ByteDistributionAccumulator
# -------------------------------------------------------------------

class ByteDistributionAccumulator:
    """Track byte value distribution across hash outputs.

    Internal state is a histogram ``numpy.ndarray`` of shape ``(256,)`` --
    one bin per possible byte value 0x00..0xFF.
    """

    def __init__(self) -> None:
        self._histogram: np.ndarray = np.zeros(256, dtype=np.int64)
        self._sample_count: int = 0

    def ingest(self, hash_input: bytes, hash_output: bytes) -> None:
        """Record one hash output, incrementing byte-value bins."""
        for b in hash_output:
            self._histogram[b] += 1
        self._sample_count += 1

    def report(self) -> dict:
        """Return byte distribution statistics.

        Keys
        ----
        histogram : list[int]
            256 integers -- count for each byte value 0..255.
        chi_squared : float
            Chi-squared statistic vs uniform distribution.
        min_count : int
            Minimum bin count.
        max_count : int
            Maximum bin count.
        total_bytes : int
            ``sample_count * 32``.
        """
        total_bytes = self._sample_count * 32
        if total_bytes == 0:
            return {
                "histogram": self._histogram.tolist(),
                "chi_squared": 0.0,
                "min_count": 0,
                "max_count": 0,
                "total_bytes": 0,
            }
        expected = total_bytes / 256.0
        chi_squared = float(
            np.sum((self._histogram - expected) ** 2 / expected)
        )
        return {
            "histogram": self._histogram.tolist(),
            "chi_squared": chi_squared,
            "min_count": int(self._histogram.min()),
            "max_count": int(self._histogram.max()),
            "total_bytes": total_bytes,
        }

    def reset(self) -> None:
        """Clear all state back to initial values."""
        self._histogram[:] = 0
        self._sample_count = 0

    @property
    def sample_count(self) -> int:
        """Number of ingested samples."""
        return self._sample_count


# -------------------------------------------------------------------
# EntropyAccumulator
# -------------------------------------------------------------------

class EntropyAccumulator:
    """Running Shannon entropy estimate from byte distribution.

    Internal state mirrors :class:`ByteDistributionAccumulator` -- a 256-bin
    histogram of byte values.
    """

    def __init__(self) -> None:
        self._histogram: np.ndarray = np.zeros(256, dtype=np.int64)
        self._sample_count: int = 0

    def ingest(self, hash_input: bytes, hash_output: bytes) -> None:
        """Record one hash output, counting byte values."""
        for b in hash_output:
            self._histogram[b] += 1
        self._sample_count += 1

    def report(self) -> dict:
        """Return entropy statistics.

        Keys
        ----
        shannon_entropy : float
            Shannon entropy in bits: ``-sum(p * log2(p))`` for non-zero *p*.
        max_entropy : float
            Theoretical maximum (8.0 bits for 256 values).
        efficiency : float
            ``shannon_entropy / max_entropy``.
        """
        total = self._histogram.sum()
        if total == 0:
            return {
                "shannon_entropy": 0.0,
                "max_entropy": 8.0,
                "efficiency": 0.0,
            }
        probs = self._histogram / total
        nonzero = probs[probs > 0]
        entropy = float(-np.sum(nonzero * np.log2(nonzero)))
        return {
            "shannon_entropy": entropy,
            "max_entropy": 8.0,
            "efficiency": entropy / 8.0,
        }

    def reset(self) -> None:
        """Clear all state back to initial values."""
        self._histogram[:] = 0
        self._sample_count = 0

    @property
    def sample_count(self) -> int:
        """Number of ingested samples."""
        return self._sample_count


# -------------------------------------------------------------------
# CompositeAccumulator
# -------------------------------------------------------------------

# Default mapping from report key to accumulator class
_DEFAULT_ACCUMULATORS: list[tuple[str, type]] = [
    ("bit_frequency", BitFrequencyAccumulator),
    ("avalanche", AvalancheAccumulator),
    ("correlation", BitCorrelationAccumulator),
    ("near_collision", NearCollisionAccumulator),
    ("byte_distribution", ByteDistributionAccumulator),
    ("entropy", EntropyAccumulator),
]


class CompositeAccumulator:
    """Run multiple accumulators in parallel.

    Parameters
    ----------
    accumulators:
        Explicit list of ``(name, accumulator_instance)`` pairs.
        ``None`` creates all six default accumulators.
    """

    def __init__(
        self,
        accumulators: list[tuple[str, object]] | None = None,
    ) -> None:
        if accumulators is None:
            self._children: list[tuple[str, object]] = [
                (name, cls()) for name, cls in _DEFAULT_ACCUMULATORS
            ]
        else:
            self._children = list(accumulators)

    def ingest(self, hash_input: bytes, hash_output: bytes) -> None:
        """Forward one sample to all child accumulators."""
        for _name, acc in self._children:
            acc.ingest(hash_input, hash_output)  # type: ignore[union-attr]

    def report(self) -> dict:
        """Return merged dict keyed by child name."""
        return {
            name: acc.report()  # type: ignore[union-attr]
            for name, acc in self._children
        }

    def reset(self) -> None:
        """Reset all children."""
        for _name, acc in self._children:
            acc.reset()  # type: ignore[union-attr]

    @property
    def sample_count(self) -> int:
        """Sample count from the first child accumulator."""
        if not self._children:
            return 0
        return self._children[0][1].sample_count  # type: ignore[union-attr]
