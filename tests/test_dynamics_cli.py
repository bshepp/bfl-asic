"""Tests for the ``bfl-asic dynamics`` CLI command group.

Uses the Click CliRunner and small iteration counts to keep tests fast.
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
# dynamics run
# ======================================================================


class TestDynamicsRun:
    def test_run_default(self, runner: CliRunner) -> None:
        """Default run exits 0 and shows orbit summary."""
        result = runner.invoke(
            main, ["dynamics", "run", "--seeds", "2", "--max-iterations", "500"],
        )
        assert result.exit_code == 0
        assert "Orbit Summary" in result.output

    def test_run_shows_convergence_summary(self, runner: CliRunner) -> None:
        result = runner.invoke(
            main, ["dynamics", "run", "--seeds", "2", "--max-iterations", "500"],
        )
        assert result.exit_code == 0
        assert "Convergence Summary" in result.output
        assert "Pairs found:" in result.output
        assert "Common states:" in result.output

    def test_run_shows_orbit_details(self, runner: CliRunner) -> None:
        result = runner.invoke(
            main, ["dynamics", "run", "--seeds", "2", "--max-iterations", "500"],
        )
        assert result.exit_code == 0
        assert "Iterations:" in result.output
        assert "Mean Hamming:" in result.output
        assert "Min Hamming:" in result.output
        assert "Max Hamming:" in result.output
        assert "Fixed point:" in result.output

    def test_run_custom_seeds(self, runner: CliRunner) -> None:
        """Custom --seeds count works."""
        result = runner.invoke(
            main, ["dynamics", "run", "--seeds", "4", "--max-iterations", "200"],
        )
        assert result.exit_code == 0
        # Should have 4 seed entries
        assert result.output.count("Seed") >= 4

    def test_run_output_json(self, runner: CliRunner, tmp_path: Path) -> None:
        """The -o flag saves a valid JSON results file."""
        out = tmp_path / "results.json"
        result = runner.invoke(
            main, [
                "dynamics", "run",
                "--seeds", "2", "--max-iterations", "500",
                "-o", str(out),
            ],
        )
        assert result.exit_code == 0
        assert out.exists()
        data = json.loads(out.read_text())
        assert "seed_count" in data
        assert data["seed_count"] == 2
        assert "orbits" in data
        assert len(data["orbits"]) == 2
        assert "convergence_pairs" in data
        assert "common_states" in data

    def test_run_output_orbits_have_hex_seeds(self, runner: CliRunner, tmp_path: Path) -> None:
        """Orbit seeds are stored as hex strings in JSON."""
        out = tmp_path / "results.json"
        runner.invoke(
            main, [
                "dynamics", "run",
                "--seeds", "1", "--max-iterations", "200",
                "-o", str(out),
            ],
        )
        data = json.loads(out.read_text())
        orbit = data["orbits"][0]
        # Seed should be a 64-char hex string (32 bytes)
        assert len(orbit["seed"]) == 64
        assert all(c in "0123456789abcdef" for c in orbit["seed"])

    def test_run_small_iterations(self, runner: CliRunner) -> None:
        """Very small --max-iterations still works."""
        result = runner.invoke(
            main, ["dynamics", "run", "--seeds", "1", "--max-iterations", "100"],
        )
        assert result.exit_code == 0


# ======================================================================
# dynamics plot
# ======================================================================


class TestDynamicsPlot:
    def test_plot_generates_files(self, runner: CliRunner, tmp_path: Path) -> None:
        """dynamics plot generates PNGs from a results JSON."""
        out = tmp_path / "results.json"
        runner.invoke(
            main, [
                "dynamics", "run",
                "--seeds", "2", "--max-iterations", "500",
                "-o", str(out),
            ],
        )
        assert out.exists()

        result = runner.invoke(main, ["dynamics", "plot", str(out)])
        assert result.exit_code == 0

        # Check PNGs were created
        convergence_png = tmp_path / "results_convergence.png"
        tail_cycle_png = tmp_path / "results_tail_cycle.png"
        orbit_0_png = tmp_path / "results_orbit_0.png"
        orbit_1_png = tmp_path / "results_orbit_1.png"

        assert convergence_png.exists()
        assert tail_cycle_png.exists()
        assert orbit_0_png.exists()
        assert orbit_1_png.exists()

    def test_plot_missing_file(self, runner: CliRunner) -> None:
        """Plot on a nonexistent file should fail."""
        result = runner.invoke(main, ["dynamics", "plot", "nonexistent.json"])
        assert result.exit_code != 0

    def test_plot_prints_paths(self, runner: CliRunner, tmp_path: Path) -> None:
        """dynamics plot prints saved file paths."""
        out = tmp_path / "results.json"
        runner.invoke(
            main, [
                "dynamics", "run",
                "--seeds", "1", "--max-iterations", "200",
                "-o", str(out),
            ],
        )

        result = runner.invoke(main, ["dynamics", "plot", str(out)])
        assert result.exit_code == 0
        assert "Orbit 0 plot saved to:" in result.output
        assert "Convergence plot saved to:" in result.output
        assert "Tail/cycle plot saved to:" in result.output


# ======================================================================
# dynamics help
# ======================================================================


class TestDynamicsHelp:
    def test_dynamics_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["dynamics", "--help"])
        assert result.exit_code == 0
        assert "run" in result.output
        assert "plot" in result.output

    def test_dynamics_run_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["dynamics", "run", "--help"])
        assert result.exit_code == 0
        assert "--seeds" in result.output
        assert "--max-iterations" in result.output
        assert "--output" in result.output or "-o" in result.output
