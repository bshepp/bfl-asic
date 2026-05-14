"""Unit tests for the NIST SP 800-22 test functions.

Reference p-values are taken from the worked examples in SP 800-22 Rev 1a
Section 2 (§2.1.8, §2.2.8, §2.3.8, etc.).  We allow a small tolerance against
the published values to absorb rounding differences in the textbook.
"""

from __future__ import annotations

import numpy as np
import pytest

from bfl_asic.randomness.tests import (
    block_frequency_test,
    cumulative_sums_test,
    dft_test,
    frequency_test,
    longest_run_test,
    runs_test,
)


def _bits(s: str) -> np.ndarray:
    return np.array([int(c) for c in s], dtype=np.uint8)


# -------------------------------------------------------------------
# frequency_test
# -------------------------------------------------------------------


class TestFrequency:
    def test_nist_example_2_1_8(self):
        # SP 800-22 §2.1.8: bits=1011010101, n=10, expected p ≈ 0.527089
        result = frequency_test(_bits("1011010101"))
        assert result.name == "frequency_monobit"
        assert result.n == 10
        assert result.passed
        assert result.p_value == pytest.approx(0.527089, abs=1e-4)

    def test_all_zeros_fails(self):
        result = frequency_test(np.zeros(1000, dtype=np.uint8))
        assert not result.passed
        assert result.p_value < 1e-9

    def test_all_ones_fails(self):
        result = frequency_test(np.ones(1000, dtype=np.uint8))
        assert not result.passed
        assert result.p_value < 1e-9

    def test_perfectly_balanced(self):
        # Equal zeros and ones -> p-value = 1.0
        bits = np.array([0, 1] * 500, dtype=np.uint8)
        result = frequency_test(bits)
        assert result.p_value == pytest.approx(1.0)
        assert result.passed

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            frequency_test(np.array([], dtype=np.uint8))

    def test_rejects_non_binary(self):
        with pytest.raises(ValueError):
            frequency_test(np.array([0, 1, 2], dtype=np.uint8))

    def test_rejects_multidim(self):
        with pytest.raises(ValueError):
            frequency_test(np.zeros((10, 10), dtype=np.uint8))

    def test_accepts_python_list(self):
        result = frequency_test([1, 0, 1, 0, 1, 0, 1, 0, 1, 0])
        assert result.p_value == pytest.approx(1.0)


# -------------------------------------------------------------------
# block_frequency_test
# -------------------------------------------------------------------


class TestBlockFrequency:
    def test_nist_example_2_2_8(self):
        # SP 800-22 §2.2.8: bits=0110011010, n=10, M=3 -> 3 blocks
        # Published p-value ≈ 0.801252
        result = block_frequency_test(_bits("0110011010"), block_size=3)
        assert result.name == "block_frequency"
        assert result.passed
        assert result.p_value == pytest.approx(0.801252, abs=1e-4)
        assert result.details["n_blocks"] == 3

    def test_all_zeros_fails(self):
        result = block_frequency_test(
            np.zeros(1000, dtype=np.uint8), block_size=100
        )
        assert not result.passed
        assert result.p_value < 1e-9

    def test_rejects_zero_block_size(self):
        with pytest.raises(ValueError):
            block_frequency_test(_bits("0110011010"), block_size=0)

    def test_rejects_block_size_larger_than_n(self):
        with pytest.raises(ValueError):
            block_frequency_test(_bits("01"), block_size=100)


# -------------------------------------------------------------------
# runs_test
# -------------------------------------------------------------------


class TestRuns:
    def test_nist_example_2_3_8(self):
        # SP 800-22 §2.3.8: bits=1001101011, expected p ≈ 0.147232
        result = runs_test(_bits("1001101011"))
        assert result.name == "runs"
        assert result.p_value == pytest.approx(0.147232, abs=1e-4)
        assert result.passed

    def test_all_zeros_skipped(self):
        result = runs_test(np.zeros(1000, dtype=np.uint8))
        assert not result.passed
        assert result.details.get("skipped") is True

    def test_alternating_bits(self):
        # Maximum transitions -> very high V_n -> tiny p-value (fail)
        bits = np.array([0, 1] * 500, dtype=np.uint8)
        result = runs_test(bits)
        assert not result.passed


# -------------------------------------------------------------------
# longest_run_test
# -------------------------------------------------------------------


class TestLongestRun:
    def test_n_below_min_raises(self):
        with pytest.raises(ValueError):
            longest_run_test(np.zeros(127, dtype=np.uint8))

    def test_runs_against_sha256_passes(self):
        # SHA-256d output of any seed -> ~random -> should pass
        from bfl_asic.stats.engine import SoftwareHashEngine
        from bfl_asic.randomness.battery import collect_bits

        bits = collect_bits(SoftwareHashEngine(), hash_count=50)  # 12800 bits
        result = longest_run_test(bits)
        assert result.passed

    def test_all_ones_in_block_path(self):
        # 128 bits of all 1s -> one block, longest run = 128
        # Bucket counts will be 0,0,0,1 -> chi-sq is large -> low p
        result = longest_run_test(np.ones(128, dtype=np.uint8))
        assert not result.passed


# -------------------------------------------------------------------
# dft_test
# -------------------------------------------------------------------


class TestDFT:
    def test_dft_on_sha256_passes(self):
        from bfl_asic.stats.engine import SoftwareHashEngine
        from bfl_asic.randomness.battery import collect_bits

        bits = collect_bits(SoftwareHashEngine(), hash_count=50)
        result = dft_test(bits)
        assert result.name == "dft_spectral"
        assert result.passed

    def test_dft_on_periodic_fails(self):
        # Strong periodic signal -> spectral peaks -> low p-value
        bits = np.array([0, 1] * 5000, dtype=np.uint8)
        result = dft_test(bits)
        assert not result.passed


# -------------------------------------------------------------------
# cumulative_sums_test
# -------------------------------------------------------------------


class TestCumulativeSums:
    def test_cusum_forward_on_sha256_passes(self):
        from bfl_asic.stats.engine import SoftwareHashEngine
        from bfl_asic.randomness.battery import collect_bits

        bits = collect_bits(SoftwareHashEngine(), hash_count=50)
        result = cumulative_sums_test(bits, mode="forward")
        assert result.name == "cumulative_sums_forward"
        assert result.passed

    def test_cusum_reverse_on_sha256_passes(self):
        from bfl_asic.stats.engine import SoftwareHashEngine
        from bfl_asic.randomness.battery import collect_bits

        bits = collect_bits(SoftwareHashEngine(), hash_count=50)
        result = cumulative_sums_test(bits, mode="reverse")
        assert result.name == "cumulative_sums_reverse"
        assert result.passed

    def test_cusum_rejects_bad_mode(self):
        with pytest.raises(ValueError):
            cumulative_sums_test(_bits("11001001000011111101"), mode="sideways")

    def test_cusum_all_ones_fails(self):
        # All-ones random walk monotonically climbs -> z = n -> low p
        result = cumulative_sums_test(np.ones(1000, dtype=np.uint8))
        assert not result.passed

    def test_cusum_p_value_clamped(self):
        # Property: p-value always in [0, 1]
        from bfl_asic.stats.engine import SoftwareHashEngine
        from bfl_asic.randomness.battery import collect_bits

        bits = collect_bits(SoftwareHashEngine(), hash_count=50)
        for mode in ("forward", "reverse"):
            r = cumulative_sums_test(bits, mode=mode)
            assert 0.0 <= r.p_value <= 1.0


# -------------------------------------------------------------------
# Property: SHA-256d output passes the full battery
# -------------------------------------------------------------------


class TestSha256dPassesAll:
    """Every NIST test should accept SHA-256d output at reasonable n."""

    @pytest.fixture(scope="class")
    def bits(self):
        from bfl_asic.stats.engine import SoftwareHashEngine
        from bfl_asic.randomness.battery import collect_bits

        # 100 hashes = 25,600 bits — comfortably above all minimums
        return collect_bits(SoftwareHashEngine(), hash_count=100)

    def test_frequency_passes(self, bits):
        assert frequency_test(bits).passed

    def test_block_frequency_passes(self, bits):
        assert block_frequency_test(bits).passed

    def test_runs_passes(self, bits):
        assert runs_test(bits).passed

    def test_longest_run_passes(self, bits):
        assert longest_run_test(bits).passed

    def test_dft_passes(self, bits):
        assert dft_test(bits).passed

    def test_cusum_forward_passes(self, bits):
        assert cumulative_sums_test(bits, mode="forward").passed

    def test_cusum_reverse_passes(self, bits):
        assert cumulative_sums_test(bits, mode="reverse").passed
