"""Tests for bfl_asic.dynamics.visualization."""

import pytest
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from bfl_asic.dynamics.visualization import (
    plot_orbit_hamming,
    plot_convergence,
    plot_tail_cycle_distribution,
)
from bfl_asic.dynamics.orbit import compute_orbit, OrbitResult
from bfl_asic.dynamics.convergence import analyze_convergence, generate_random_seeds


@pytest.fixture
def orbit():
    seed = b'\x00' * 32
    return compute_orbit(seed, max_iterations=100, sample_interval=10)


@pytest.fixture
def convergence_result():
    seeds = generate_random_seeds(3)
    return analyze_convergence(seeds, max_iterations=100, check_interval=10)


class TestDynamicsVisualization:
    def test_orbit_hamming(self, orbit):
        fig = plot_orbit_hamming(orbit)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_orbit_hamming_has_reference_line(self, orbit):
        fig = plot_orbit_hamming(orbit)
        ax = fig.axes[0]
        # Check that horizontal lines exist (reference + mean)
        lines = ax.get_lines()
        assert len(lines) >= 2  # data line + at least one hline
        plt.close(fig)

    def test_convergence_plot(self, convergence_result):
        fig = plot_convergence(convergence_result)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_convergence_plot_has_trajectories(self, convergence_result):
        fig = plot_convergence(convergence_result)
        ax = fig.axes[0]
        # Should have at least 3 trajectory lines (one per seed)
        # plus start markers
        assert len(ax.get_lines()) >= 3
        plt.close(fig)

    def test_tail_cycle_distribution(self, orbit):
        fig = plot_tail_cycle_distribution([orbit])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_tail_cycle_no_cycles(self, orbit):
        # With only 100 iterations of SHA-256, no cycles detected
        fig = plot_tail_cycle_distribution([orbit])
        assert isinstance(fig, plt.Figure)
        # Should have 2 subplots
        assert len(fig.axes) == 2
        plt.close(fig)

    def test_save_to_file(self, orbit, tmp_path):
        path = tmp_path / "orbit.png"
        fig = plot_orbit_hamming(orbit, save_path=path)
        assert path.exists()
        assert path.stat().st_size > 0
        plt.close(fig)

    def test_tail_cycle_save(self, orbit, tmp_path):
        path = tmp_path / "tail_cycle.png"
        fig = plot_tail_cycle_distribution([orbit], save_path=path)
        assert path.exists()
        assert path.stat().st_size > 0
        plt.close(fig)
