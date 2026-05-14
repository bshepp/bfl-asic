"""NIST SP 800-22 statistical tests as pure functions over bit arrays.

Each test consumes a 1-D numpy array of ``uint8`` values in ``{0, 1}`` and returns
a :class:`TestResult` containing the test statistic and a p-value.  The
convention from NIST SP 800-22 Section 4 is that a test passes when
``p_value >= alpha`` (default ``alpha = 0.01``).

References
----------
NIST SP 800-22 Rev 1a, "A Statistical Test Suite for Random and Pseudorandom
Number Generators for Cryptographic Applications" (April 2010).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy.fft import rfft
from scipy.special import gammaincc, erfc
from scipy.stats import norm


DEFAULT_ALPHA = 0.01


@dataclass
class TestResult:
    """Outcome of a single NIST SP 800-22 test."""

    name: str
    statistic: float
    p_value: float
    passed: bool
    n: int
    details: dict

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        verdict = "PASS" if self.passed else "FAIL"
        return f"<TestResult {self.name} p={self.p_value:.4f} [{verdict}]>"


def _as_bit_array(bits) -> np.ndarray:
    arr = np.asarray(bits, dtype=np.uint8)
    if arr.ndim != 1:
        raise ValueError(f"bits must be 1-D, got shape {arr.shape}")
    if arr.size == 0:
        raise ValueError("bits must be non-empty")
    if not np.all((arr == 0) | (arr == 1)):
        raise ValueError("bits must contain only 0 and 1 values")
    return arr


# -------------------------------------------------------------------
# 2.1  Frequency (Monobit) Test
# -------------------------------------------------------------------

def frequency_test(bits, alpha: float = DEFAULT_ALPHA) -> TestResult:
    """Monobit frequency test (SP 800-22 §2.1).

    Tests whether the proportion of ones and zeros is close to 1/2.  The
    recommended minimum stream length is 100 bits.
    """
    arr = _as_bit_array(bits)
    n = arr.size
    s_n = int(np.sum(2 * arr.astype(np.int64) - 1))
    s_obs = abs(s_n) / math.sqrt(n)
    p_value = math.erfc(s_obs / math.sqrt(2))
    return TestResult(
        name="frequency_monobit",
        statistic=s_obs,
        p_value=p_value,
        passed=p_value >= alpha,
        n=n,
        details={"sum_pm1": s_n},
    )


# -------------------------------------------------------------------
# 2.2  Frequency Test within a Block
# -------------------------------------------------------------------

def block_frequency_test(
    bits, block_size: int = 128, alpha: float = DEFAULT_ALPHA
) -> TestResult:
    """Frequency test within a block (SP 800-22 §2.2).

    Tests whether the proportion of ones within ``block_size``-bit blocks is
    close to 1/2.  Recommended ``block_size >= 20`` and ``block_size > 0.01*n``.
    """
    arr = _as_bit_array(bits)
    n = arr.size
    if block_size <= 0:
        raise ValueError("block_size must be positive")
    n_blocks = n // block_size
    if n_blocks < 1:
        raise ValueError(
            f"need at least one block: block_size={block_size}, n={n}"
        )
    trimmed = arr[: n_blocks * block_size].reshape(n_blocks, block_size)
    pi_i = trimmed.mean(axis=1)
    chi_sq = float(4.0 * block_size * np.sum((pi_i - 0.5) ** 2))
    p_value = float(gammaincc(n_blocks / 2.0, chi_sq / 2.0))
    return TestResult(
        name="block_frequency",
        statistic=chi_sq,
        p_value=p_value,
        passed=p_value >= alpha,
        n=n,
        details={"block_size": block_size, "n_blocks": n_blocks},
    )


# -------------------------------------------------------------------
# 2.3  Runs Test
# -------------------------------------------------------------------

def runs_test(bits, alpha: float = DEFAULT_ALPHA) -> TestResult:
    """Runs test (SP 800-22 §2.3).

    Counts the total number of runs (maximal sequences of identical bits) and
    checks against the expectation for a random stream.  Skipped (returns a
    failing result with ``p_value=0``) when the monobit proportion is too far
    from 1/2 for the runs statistic to be meaningful.
    """
    arr = _as_bit_array(bits)
    n = arr.size
    pi = float(arr.mean())
    threshold = 2.0 / math.sqrt(n)
    if abs(pi - 0.5) >= threshold:
        return TestResult(
            name="runs",
            statistic=float("nan"),
            p_value=0.0,
            passed=False,
            n=n,
            details={
                "skipped": True,
                "reason": "monobit pi too far from 0.5",
                "pi": pi,
                "threshold": threshold,
            },
        )
    # V_n = 1 + number of bit transitions
    transitions = int(np.sum(arr[1:] != arr[:-1]))
    v_n = transitions + 1
    expected = 2.0 * n * pi * (1.0 - pi)
    denom = 2.0 * math.sqrt(2.0 * n) * pi * (1.0 - pi)
    p_value = math.erfc(abs(v_n - expected) / denom)
    return TestResult(
        name="runs",
        statistic=float(v_n),
        p_value=p_value,
        passed=p_value >= alpha,
        n=n,
        details={"pi": pi, "transitions": transitions},
    )


# -------------------------------------------------------------------
# 2.4  Test for the Longest Run of Ones in a Block
# -------------------------------------------------------------------

# Parameters from SP 800-22 Table 2-4 / Table 2-5
# Map n -> (M, K, V_buckets, pi_probabilities)
_LONGEST_RUN_PARAMS: list[tuple[int, int, int, list[int], list[float]]] = [
    (
        128, 8, 3,
        [1, 2, 3, 4],
        [0.2148, 0.3672, 0.2305, 0.1875],
    ),
    (
        6272, 128, 5,
        [4, 5, 6, 7, 8, 9],
        [0.1174, 0.2430, 0.2493, 0.1752, 0.1027, 0.1124],
    ),
    (
        750_000, 10_000, 6,
        [10, 11, 12, 13, 14, 15, 16],
        [0.0882, 0.2092, 0.2483, 0.1933, 0.1208, 0.0675, 0.0727],
    ),
]


def _max_run_of_ones_per_block(blocks: np.ndarray) -> np.ndarray:
    """Vectorized longest-1-run per block.  blocks shape: (n_blocks, block_size)."""
    n_blocks, m = blocks.shape
    out = np.zeros(n_blocks, dtype=np.int64)
    for i in range(n_blocks):
        cur = 0
        best = 0
        for b in blocks[i]:
            if b:
                cur += 1
                if cur > best:
                    best = cur
            else:
                cur = 0
        out[i] = best
    return out


def longest_run_test(bits, alpha: float = DEFAULT_ALPHA) -> TestResult:
    """Longest run of ones in a block (SP 800-22 §2.4).

    Selects ``(block_size, K, buckets, probabilities)`` per the SP 800-22 table
    based on ``n``.  Requires ``n >= 128``.
    """
    arr = _as_bit_array(bits)
    n = arr.size
    params = None
    for min_n, m, k, buckets, probs in reversed(_LONGEST_RUN_PARAMS):
        if n >= min_n:
            params = (m, k, buckets, probs)
            break
    if params is None:
        raise ValueError(f"longest_run_test requires n >= 128, got {n}")
    m, k, buckets, probs = params
    n_blocks = n // m
    trimmed = arr[: n_blocks * m].reshape(n_blocks, m)
    longest = _max_run_of_ones_per_block(trimmed)

    # Bucket counts: <= buckets[0], == buckets[1], ..., >= buckets[-1]
    counts = np.zeros(k + 1, dtype=np.int64)
    counts[0] = int(np.sum(longest <= buckets[0]))
    for i in range(1, k):
        counts[i] = int(np.sum(longest == buckets[i]))
    counts[k] = int(np.sum(longest >= buckets[k]))

    expected = np.array(probs) * n_blocks
    chi_sq = float(np.sum((counts - expected) ** 2 / expected))
    p_value = float(gammaincc(k / 2.0, chi_sq / 2.0))
    return TestResult(
        name="longest_run",
        statistic=chi_sq,
        p_value=p_value,
        passed=p_value >= alpha,
        n=n,
        details={
            "block_size": m,
            "n_blocks": n_blocks,
            "buckets": list(map(int, counts)),
        },
    )


# -------------------------------------------------------------------
# 2.6  Discrete Fourier Transform (Spectral) Test
# -------------------------------------------------------------------

def dft_test(bits, alpha: float = DEFAULT_ALPHA) -> TestResult:
    """Discrete Fourier Transform test (SP 800-22 §2.6).

    Detects periodic features in the bit stream by computing the magnitude
    spectrum of the ±1-mapped sequence and counting components below the 95%
    threshold.  Recommended ``n >= 1000``.
    """
    arr = _as_bit_array(bits)
    n = arr.size
    x = 2.0 * arr.astype(np.float64) - 1.0
    # NIST uses |DFT_k| for k in 0..n/2-1 of the full DFT; rfft gives k=0..n/2.
    spectrum = np.abs(rfft(x))[: n // 2]
    threshold = math.sqrt(math.log(1.0 / 0.05) * n)
    n0 = 0.95 * n / 2.0
    n1 = float(np.sum(spectrum < threshold))
    d = (n1 - n0) / math.sqrt(n * 0.95 * 0.05 / 4.0)
    p_value = math.erfc(abs(d) / math.sqrt(2))
    return TestResult(
        name="dft_spectral",
        statistic=d,
        p_value=p_value,
        passed=p_value >= alpha,
        n=n,
        details={"threshold": threshold, "n0_expected": n0, "n1_observed": n1},
    )


# -------------------------------------------------------------------
# 2.13  Cumulative Sums (Cusum) Test
# -------------------------------------------------------------------

def cumulative_sums_test(
    bits, mode: str = "forward", alpha: float = DEFAULT_ALPHA
) -> TestResult:
    """Cumulative sums test (SP 800-22 §2.13).

    Tests the maximum excursion of the partial-sum random walk built from the
    ±1-mapped bit stream.

    Parameters
    ----------
    mode:
        ``"forward"`` walks left-to-right; ``"reverse"`` walks right-to-left.
    """
    if mode not in ("forward", "reverse"):
        raise ValueError(f"mode must be 'forward' or 'reverse', got {mode!r}")
    arr = _as_bit_array(bits)
    n = arr.size
    x = 2.0 * arr.astype(np.float64) - 1.0
    if mode == "reverse":
        x = x[::-1]
    partial = np.cumsum(x)
    z = float(np.max(np.abs(partial)))

    # P-value formula from SP 800-22 §2.13.4
    sqrt_n = math.sqrt(n)
    # Sum 1: k from floor((-n/z + 1)/4) to floor((n/z - 1)/4)
    k_lo_1 = math.floor((-n / z + 1.0) / 4.0)
    k_hi_1 = math.floor((n / z - 1.0) / 4.0)
    sum1 = 0.0
    for k in range(k_lo_1, k_hi_1 + 1):
        a = (4 * k + 1) * z / sqrt_n
        b = (4 * k - 1) * z / sqrt_n
        sum1 += norm.cdf(a) - norm.cdf(b)
    # Sum 2: k from floor((-n/z - 3)/4) to floor((n/z - 1)/4)
    k_lo_2 = math.floor((-n / z - 3.0) / 4.0)
    k_hi_2 = math.floor((n / z - 1.0) / 4.0)
    sum2 = 0.0
    for k in range(k_lo_2, k_hi_2 + 1):
        a = (4 * k + 3) * z / sqrt_n
        b = (4 * k + 1) * z / sqrt_n
        sum2 += norm.cdf(a) - norm.cdf(b)

    p_value = 1.0 - sum1 + sum2
    # Clamp to [0, 1] for floating-point safety at the boundaries
    p_value = max(0.0, min(1.0, p_value))
    return TestResult(
        name=f"cumulative_sums_{mode}",
        statistic=z,
        p_value=p_value,
        passed=p_value >= alpha,
        n=n,
        details={"mode": mode},
    )


# -------------------------------------------------------------------
# Test registry
# -------------------------------------------------------------------

ALL_TESTS: list[Callable[..., TestResult]] = [
    frequency_test,
    block_frequency_test,
    runs_test,
    longest_run_test,
    dft_test,
    cumulative_sums_test,
]
