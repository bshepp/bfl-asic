"""NIST SP 800-22 randomness test battery for SHA-256 output streams.

This subsystem evaluates the statistical quality of bit streams produced by any
:class:`~bfl_asic.stats.engine.HashSource`.  The tests are pure functions over
numpy bit arrays so they can be exercised independently of any hash backend.
"""

from bfl_asic.randomness.tests import (
    TestResult,
    frequency_test,
    block_frequency_test,
    runs_test,
    longest_run_test,
    dft_test,
    cumulative_sums_test,
    ALL_TESTS,
)
from bfl_asic.randomness.battery import RandomnessBattery
from bfl_asic.randomness.snapshot import RandomnessSnapshot
