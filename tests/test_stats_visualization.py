"""Tests for bfl_asic.stats.visualization."""

import pytest
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from bfl_asic.stats.visualization import (
    plot_bit_frequency_heatmap,
    plot_hamming_histogram,
    plot_byte_distribution,
    plot_correlation_matrix,
    plot_power_spectrum,
    plot_dashboard,
    animate_bit_frequency_convergence,
)
from bfl_asic.stats.pipeline import StatsPipeline


@pytest.fixture
def snapshot():
    """Generate a real snapshot from 1000 hashes for testing."""
    pipeline = StatsPipeline()
    return pipeline.run(samples=1000)


class TestStatsVisualization:
    def test_bit_frequency_heatmap(self, snapshot):
        fig = plot_bit_frequency_heatmap(snapshot)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_hamming_histogram(self, snapshot):
        fig = plot_hamming_histogram(snapshot)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_byte_distribution(self, snapshot):
        fig = plot_byte_distribution(snapshot)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_correlation_matrix(self, snapshot):
        fig = plot_correlation_matrix(snapshot)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_power_spectrum(self):
        freqs = np.linspace(0, 0.5, 100)
        power = np.random.exponential(size=100)
        fig = plot_power_spectrum(freqs, power, position=0)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_power_spectrum_empty(self):
        fig = plot_power_spectrum(np.array([]), np.array([]), position=42)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_dashboard(self, snapshot):
        fig = plot_dashboard(snapshot)
        assert isinstance(fig, plt.Figure)
        # 4 main panels + 2 colorbars (heatmap + correlation) = 6 axes
        assert len(fig.axes) >= 4
        plt.close(fig)

    def test_save_to_file(self, snapshot, tmp_path):
        path = tmp_path / "test.png"
        fig = plot_bit_frequency_heatmap(snapshot, save_path=path)
        assert path.exists()
        assert path.stat().st_size > 0
        plt.close(fig)

    def test_hamming_save_to_file(self, snapshot, tmp_path):
        path = tmp_path / "hamming.png"
        fig = plot_hamming_histogram(snapshot, save_path=path)
        assert path.exists()
        assert path.stat().st_size > 0
        plt.close(fig)

    def test_byte_distribution_save(self, snapshot, tmp_path):
        path = tmp_path / "byte_dist.png"
        fig = plot_byte_distribution(snapshot, save_path=path)
        assert path.exists()
        plt.close(fig)

    def test_dashboard_save(self, snapshot, tmp_path):
        path = tmp_path / "dashboard.png"
        fig = plot_dashboard(snapshot, save_path=path)
        assert path.exists()
        assert path.stat().st_size > 0
        plt.close(fig)

    def test_heatmap_has_colorbar(self, snapshot):
        fig = plot_bit_frequency_heatmap(snapshot)
        # Figure should have more than 1 axes if colorbar is present
        assert len(fig.axes) >= 2
        plt.close(fig)

    def test_correlation_matrix_has_colorbar(self, snapshot):
        fig = plot_correlation_matrix(snapshot)
        assert len(fig.axes) >= 2
        plt.close(fig)


@pytest.mark.filterwarnings("ignore:Animation was deleted without rendering")
class TestAnimateConvergence:
    def test_returns_figure_and_animation(self):
        from matplotlib.animation import FuncAnimation
        fig, anim = animate_bit_frequency_convergence(
            total_samples=500, n_frames=5,
        )
        assert isinstance(fig, plt.Figure)
        assert isinstance(anim, FuncAnimation)
        plt.close(fig)

    def test_saves_gif(self, tmp_path):
        path = tmp_path / "convergence.gif"
        fig, _anim = animate_bit_frequency_convergence(
            total_samples=500, n_frames=5, save_path=path, fps=5,
        )
        assert path.exists()
        assert path.stat().st_size > 0
        plt.close(fig)

    def test_rejects_too_few_samples(self):
        with pytest.raises(ValueError):
            animate_bit_frequency_convergence(total_samples=5, n_frames=3)

    def test_rejects_too_few_frames(self):
        with pytest.raises(ValueError):
            animate_bit_frequency_convergence(total_samples=500, n_frames=1)

    def test_has_two_main_axes(self):
        fig, _anim = animate_bit_frequency_convergence(
            total_samples=500, n_frames=5,
        )
        # Heatmap + line plot + colorbar = at least 3 axes
        assert len(fig.axes) >= 3
        plt.close(fig)
