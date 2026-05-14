"""Tests for the ``bfl-asic randomness`` CLI command group."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from bfl_asic.cli import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ======================================================================
# randomness run
# ======================================================================


class TestRandomnessRun:
    def test_run_default(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["randomness", "run", "--hashes", "20"])
        assert result.exit_code == 0, result.output
        assert "Results" in result.output

    def test_run_shows_engine(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["randomness", "run", "--hashes", "20"])
        assert result.exit_code == 0
        assert "software-sha256d" in result.output

    def test_run_shows_all_test_names(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["randomness", "run", "--hashes", "50"])
        assert result.exit_code == 0
        for name in (
            "frequency_monobit",
            "block_frequency",
            "runs",
            "longest_run",
            "dft_spectral",
            "cumulative_sums_forward",
            "cumulative_sums_reverse",
        ):
            assert name in result.output

    def test_run_shows_summary_counts(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["randomness", "run", "--hashes", "50"])
        assert result.exit_code == 0
        assert "passed" in result.output
        assert "failed" in result.output

    def test_run_writes_snapshot(self, runner: CliRunner, tmp_path: Path) -> None:
        out = tmp_path / "rand.json"
        result = runner.invoke(
            main, ["randomness", "run", "--hashes", "20", "-o", str(out)]
        )
        assert result.exit_code == 0, result.output
        assert out.exists()
        data = json.loads(out.read_text())
        assert "results" in data
        assert data["sample_count"] == 20

    def test_run_alpha_override(self, runner: CliRunner) -> None:
        result = runner.invoke(
            main, ["randomness", "run", "--hashes", "20", "--alpha", "0.05"]
        )
        assert result.exit_code == 0


# ======================================================================
# randomness report
# ======================================================================


class TestRandomnessReport:
    def test_report_loads_snapshot(self, runner: CliRunner, tmp_path: Path) -> None:
        out = tmp_path / "rand.json"
        runner.invoke(
            main, ["randomness", "run", "--hashes", "20", "-o", str(out)]
        )
        result = runner.invoke(main, ["randomness", "report", str(out)])
        assert result.exit_code == 0, result.output
        assert "Randomness Report" in result.output
        assert "software-sha256d" in result.output

    def test_report_missing_file(self, runner: CliRunner) -> None:
        # Click's exists=True turns missing files into exit code 2
        result = runner.invoke(main, ["randomness", "report", "no-such-file.json"])
        assert result.exit_code != 0

    def test_report_corrupt_file(self, runner: CliRunner, tmp_path: Path) -> None:
        bad = tmp_path / "broken.json"
        bad.write_text("{not valid json")
        result = runner.invoke(main, ["randomness", "report", str(bad)])
        assert result.exit_code != 0
        assert "Failed to load" in result.output
