from __future__ import annotations
import time
from typing import Callable

from bfl_asic.stats.engine import HashSource, SoftwareHashEngine
from bfl_asic.stats.accumulators import CompositeAccumulator
from bfl_asic.stats.spectral import BitPositionTimeSeries
from bfl_asic.stats.snapshot import StatsSnapshot


class StatsPipeline:
    """Orchestrates the full SHA-256 statistical analysis run.

    Connects a HashSource to accumulators and manages the run loop.
    """

    def __init__(
        self,
        engine: HashSource | None = None,
        accumulator: CompositeAccumulator | None = None,
        spectral: BitPositionTimeSeries | None = None,
        report_interval: int = 10_000,
        on_progress: Callable[[int, dict], None] | None = None,
    ) -> None:
        """
        Args:
            engine: Hash source. Default: SoftwareHashEngine()
            accumulator: Composite accumulator. Default: CompositeAccumulator()
            spectral: Spectral tracker. Default: BitPositionTimeSeries()
            report_interval: Generate interim report every N hashes.
            on_progress: Callback(sample_count, interim_report) at each interval.
        """
        self._engine = engine or SoftwareHashEngine()
        self._accumulator = accumulator or CompositeAccumulator()
        self._spectral = spectral or BitPositionTimeSeries()
        self._report_interval = report_interval
        self._on_progress = on_progress

    def run(self, samples: int) -> StatsSnapshot:
        """Run the pipeline for exactly `samples` hashes.

        Returns a final StatsSnapshot.
        """
        start_time = time.monotonic()

        for i, (hash_input, hash_output) in enumerate(self._engine.hashes(count=samples)):
            self._accumulator.ingest(hash_input, hash_output)
            self._spectral.ingest(hash_input, hash_output)

            # Fire progress callback at intervals
            if self._on_progress and (i + 1) % self._report_interval == 0:
                elapsed = time.monotonic() - start_time
                report = self._accumulator.report()
                report["hash_rate"] = (i + 1) / max(elapsed, 0.001)
                self._on_progress(i + 1, report)

        elapsed = time.monotonic() - start_time
        return StatsSnapshot.from_pipeline(
            engine_name=self._engine.name(),
            sample_count=samples,
            duration_seconds=elapsed,
            report=self._accumulator.report(),
        )

    def run_timed(self, seconds: float) -> StatsSnapshot:
        """Run the pipeline for approximately `seconds` wall-clock time.

        Returns a final StatsSnapshot.
        """
        start_time = time.monotonic()
        count = 0

        for hash_input, hash_output in self._engine.hashes(count=None):
            self._accumulator.ingest(hash_input, hash_output)
            self._spectral.ingest(hash_input, hash_output)
            count += 1

            if self._on_progress and count % self._report_interval == 0:
                elapsed = time.monotonic() - start_time
                report = self._accumulator.report()
                report["hash_rate"] = count / max(elapsed, 0.001)
                self._on_progress(count, report)

            if time.monotonic() - start_time >= seconds:
                break

        elapsed = time.monotonic() - start_time
        return StatsSnapshot.from_pipeline(
            engine_name=self._engine.name(),
            sample_count=count,
            duration_seconds=elapsed,
            report=self._accumulator.report(),
        )

    @property
    def accumulator(self) -> CompositeAccumulator:
        """Access the underlying accumulator."""
        return self._accumulator

    @property
    def spectral(self) -> BitPositionTimeSeries:
        """Access the underlying spectral tracker."""
        return self._spectral

    @property
    def engine(self) -> HashSource:
        """Access the underlying hash engine."""
        return self._engine
