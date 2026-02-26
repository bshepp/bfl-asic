import pytest
from bfl_asic.stats.pipeline import StatsPipeline
from bfl_asic.stats.engine import SoftwareHashEngine
from bfl_asic.stats.accumulators import CompositeAccumulator
from bfl_asic.stats.snapshot import StatsSnapshot

class TestPipelineRun:
    def test_run_returns_snapshot(self):
        pipeline = StatsPipeline()
        result = pipeline.run(samples=100)
        assert isinstance(result, StatsSnapshot)

    def test_run_correct_sample_count(self):
        pipeline = StatsPipeline()
        result = pipeline.run(samples=500)
        assert result.sample_count == 500

    def test_run_engine_name(self):
        pipeline = StatsPipeline()
        result = pipeline.run(samples=100)
        assert result.engine_name == "software-sha256d"

    def test_run_duration_positive(self):
        pipeline = StatsPipeline()
        result = pipeline.run(samples=100)
        assert result.duration_seconds > 0

    def test_run_hash_rate_positive(self):
        pipeline = StatsPipeline()
        result = pipeline.run(samples=1000)
        assert result.hash_rate > 0

    def test_run_has_bit_frequency_data(self):
        pipeline = StatsPipeline()
        result = pipeline.run(samples=1000)
        assert "bit_frequencies" in result.bit_frequency or "max_bias" in result.bit_frequency

    def test_run_has_avalanche_data(self):
        pipeline = StatsPipeline()
        result = pipeline.run(samples=1000)
        assert "mean" in result.avalanche

    def test_run_has_entropy_data(self):
        pipeline = StatsPipeline()
        result = pipeline.run(samples=1000)
        assert "shannon_entropy" in result.entropy

class TestPipelineProgress:
    def test_progress_callback_fires(self):
        calls = []
        def on_progress(count, report):
            calls.append(count)

        pipeline = StatsPipeline(report_interval=50, on_progress=on_progress)
        pipeline.run(samples=200)
        assert calls == [50, 100, 150, 200]

    def test_progress_callback_receives_report(self):
        reports = []
        def on_progress(count, report):
            reports.append(report)

        pipeline = StatsPipeline(report_interval=100, on_progress=on_progress)
        pipeline.run(samples=100)
        assert len(reports) == 1
        assert isinstance(reports[0], dict)

    def test_no_callback_is_fine(self):
        pipeline = StatsPipeline(on_progress=None)
        result = pipeline.run(samples=100)
        assert result.sample_count == 100

class TestPipelineRunTimed:
    def test_run_timed_returns_snapshot(self):
        pipeline = StatsPipeline()
        result = pipeline.run_timed(seconds=0.5)
        assert isinstance(result, StatsSnapshot)

    def test_run_timed_processes_hashes(self):
        pipeline = StatsPipeline()
        result = pipeline.run_timed(seconds=0.5)
        assert result.sample_count > 0

    def test_run_timed_respects_duration(self):
        pipeline = StatsPipeline()
        result = pipeline.run_timed(seconds=0.5)
        assert result.duration_seconds >= 0.4  # allow some tolerance
        assert result.duration_seconds < 2.0   # shouldn't run much longer

class TestPipelineCustomConfig:
    def test_custom_engine(self):
        engine = SoftwareHashEngine(start=9999)
        pipeline = StatsPipeline(engine=engine)
        result = pipeline.run(samples=50)
        assert result.sample_count == 50

    def test_custom_accumulator(self):
        acc = CompositeAccumulator()
        pipeline = StatsPipeline(accumulator=acc)
        pipeline.run(samples=100)
        assert acc.sample_count == 100

    def test_properties(self):
        pipeline = StatsPipeline()
        assert pipeline.engine is not None
        assert pipeline.accumulator is not None
        assert pipeline.spectral is not None

class TestPipelineJsonRoundTrip:
    def test_snapshot_serializes(self):
        pipeline = StatsPipeline()
        result = pipeline.run(samples=100)
        json_str = result.to_json()
        restored = StatsSnapshot.from_json(json_str)
        assert restored.sample_count == 100
