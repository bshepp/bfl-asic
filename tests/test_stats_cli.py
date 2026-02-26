"""Tests for the ``bfl-asic stats`` CLI command group.

Uses the Click CliRunner and small sample counts to keep tests fast.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from bfl_asic.cli import main


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Click CliRunner instance."""
    return CliRunner()


# ======================================================================
# stats run
# ======================================================================


class TestStatsRun:
    def test_run_default(self, runner: CliRunner) -> None:
        """Default run (no args) exits 0 and shows summary."""
        result = runner.invoke(main, ["stats", "run", "--samples", "200"])
        assert result.exit_code == 0
        assert "Summary" in result.output

    def test_run_shows_sample_count(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["stats", "run", "--samples", "100"])
        assert result.exit_code == 0
        assert "Samples:" in result.output

    def test_run_shows_hash_rate(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["stats", "run", "--samples", "100"])
        assert result.exit_code == 0
        assert "Hash rate:" in result.output

    def test_run_shows_max_bias(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["stats", "run", "--samples", "100"])
        assert result.exit_code == 0
        assert "Max bias:" in result.output

    def test_run_shows_mean_hamming(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["stats", "run", "--samples", "100"])
        assert result.exit_code == 0
        assert "Mean Hamming:" in result.output

    def test_run_shows_entropy(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["stats", "run", "--samples", "100"])
        assert result.exit_code == 0
        assert "Shannon entropy:" in result.output

    def test_run_with_samples(self, runner: CliRunner) -> None:
        """Explicit --samples flag works."""
        result = runner.invoke(main, ["stats", "run", "--samples", "500"])
        assert result.exit_code == 0
        assert "500" in result.output

    def test_run_with_duration(self, runner: CliRunner) -> None:
        """--duration flag triggers timed mode."""
        result = runner.invoke(main, ["stats", "run", "--duration", "0.5"])
        assert result.exit_code == 0
        assert "Summary" in result.output

    def test_run_samples_and_duration_exclusive(self, runner: CliRunner) -> None:
        """--samples and --duration cannot be used together."""
        result = runner.invoke(main, ["stats", "run", "--samples", "100", "--duration", "1"])
        assert result.exit_code != 0

    def test_run_output_json(self, runner: CliRunner, tmp_path: Path) -> None:
        """The -o flag saves a valid JSON snapshot."""
        out = tmp_path / "snapshot.json"
        result = runner.invoke(main, ["stats", "run", "--samples", "100", "-o", str(out)])
        assert result.exit_code == 0
        assert out.exists()
        data = json.loads(out.read_text())
        assert "sample_count" in data
        assert data["sample_count"] == 100

    def test_run_plot(self, runner: CliRunner, tmp_path: Path) -> None:
        """--plot generates a dashboard PNG alongside the snapshot."""
        out = tmp_path / "snapshot.json"
        result = runner.invoke(
            main, ["stats", "run", "--samples", "100", "-o", str(out), "--plot"],
        )
        assert result.exit_code == 0
        png_path = tmp_path / "snapshot.png"
        assert png_path.exists()
        assert png_path.stat().st_size > 0

    def test_run_plot_default_path(self, runner: CliRunner, tmp_path: Path) -> None:
        """--plot without -o saves to dashboard.png in cwd."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["stats", "run", "--samples", "100", "--plot"])
            assert result.exit_code == 0
            assert Path("dashboard.png").exists()

    def test_run_report_interval(self, runner: CliRunner) -> None:
        """Custom --report-interval does not break the run."""
        result = runner.invoke(
            main, ["stats", "run", "--samples", "200", "--report-interval", "50"],
        )
        assert result.exit_code == 0
        assert "Summary" in result.output


# ======================================================================
# stats report
# ======================================================================


class TestStatsReport:
    def test_report_loads_snapshot(self, runner: CliRunner, tmp_path: Path) -> None:
        """stats report loads a snapshot and prints a summary."""
        # First create a snapshot
        out = tmp_path / "snap.json"
        runner.invoke(main, ["stats", "run", "--samples", "100", "-o", str(out)])
        assert out.exists()

        # Now report on it
        result = runner.invoke(main, ["stats", "report", str(out)])
        assert result.exit_code == 0
        assert "Stats Report" in result.output
        assert "Samples:" in result.output
        assert "Hash rate:" in result.output
        assert "Max bias:" in result.output
        assert "Shannon entropy:" in result.output

    def test_report_shows_all_sections(self, runner: CliRunner, tmp_path: Path) -> None:
        """Report shows all accumulator sections."""
        out = tmp_path / "snap.json"
        runner.invoke(main, ["stats", "run", "--samples", "100", "-o", str(out)])

        result = runner.invoke(main, ["stats", "report", str(out)])
        assert result.exit_code == 0
        assert "Bit Frequency" in result.output
        assert "Avalanche" in result.output
        assert "Correlation" in result.output
        assert "Near Collision" in result.output
        assert "Byte Distribution" in result.output
        assert "Entropy" in result.output

    def test_report_missing_file(self, runner: CliRunner) -> None:
        """Report on a nonexistent file should fail."""
        result = runner.invoke(main, ["stats", "report", "nonexistent.json"])
        assert result.exit_code != 0


# ======================================================================
# stats help
# ======================================================================


class TestStatsHelp:
    def test_stats_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["stats", "--help"])
        assert result.exit_code == 0
        assert "run" in result.output
        assert "report" in result.output

    def test_stats_run_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["stats", "run", "--help"])
        assert result.exit_code == 0
        assert "--samples" in result.output
        assert "--duration" in result.output
        assert "--report-interval" in result.output
        assert "--output" in result.output or "-o" in result.output
        assert "--plot" in result.output
