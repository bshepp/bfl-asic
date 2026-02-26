"""Matplotlib-based plotting for statistical analysis results.

Provides standalone plot functions for each statistical metric and a combined
dashboard view.  All functions use the ``Agg`` backend (headless) and return
:class:`matplotlib.figure.Figure` objects so the caller can display or save
them as needed.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from bfl_asic.stats.snapshot import StatsSnapshot  # noqa: E402


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _save_if_requested(fig: plt.Figure, save_path: Path | None) -> None:
    """Save figure to disk if *save_path* is not ``None``."""
    if save_path is not None:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")


def _empty_axes_message(ax: plt.Axes, message: str) -> None:
    """Place a centred text message on *ax* and hide tick marks."""
    ax.text(
        0.5, 0.5, message,
        transform=ax.transAxes,
        ha="center", va="center",
        fontsize=12, color="gray",
    )
    ax.set_xticks([])
    ax.set_yticks([])


# -------------------------------------------------------------------
# Standalone plots
# -------------------------------------------------------------------

def plot_bit_frequency_heatmap(
    snapshot: StatsSnapshot,
    save_path: Path | None = None,
) -> plt.Figure:
    """16x16 heatmap showing per-bit frequency deviation from 0.5.

    Colour scheme: blue (< 0.5) -- white (= 0.5) -- red (> 0.5) using
    a diverging colourmap (``RdBu_r``).

    Data comes from ``snapshot.bit_frequency["bit_frequencies"]`` (list of
    256 floats).  Reshaped to 16x16 for display.
    """
    fig, ax = plt.subplots(figsize=(8, 7))

    freqs = snapshot.bit_frequency.get("bit_frequencies")
    if not freqs or len(freqs) != 256:
        _empty_axes_message(ax, "No bit-frequency data available")
        _save_if_requested(fig, save_path)
        return fig

    data = np.array(freqs, dtype=np.float64).reshape(16, 16)
    deviation = data - 0.5

    vmax = max(abs(deviation.min()), abs(deviation.max()), 0.01)
    im = ax.imshow(
        deviation,
        cmap="RdBu_r",
        vmin=-vmax,
        vmax=vmax,
        aspect="equal",
        interpolation="nearest",
    )
    fig.colorbar(im, ax=ax, label="Frequency deviation from 0.5")
    ax.set_title("Bit Frequency Deviation (16x16)")
    ax.set_xlabel("Bit position (column)")
    ax.set_ylabel("Bit position (row)")

    _save_if_requested(fig, save_path)
    return fig


def plot_hamming_histogram(
    snapshot: StatsSnapshot,
    save_path: Path | None = None,
) -> plt.Figure:
    """Hamming distance histogram overlaid on theoretical Binomial(256, 0.5).

    Bar chart of empirical data from ``snapshot.avalanche["histogram"]``.
    Smooth curve of theoretical distribution via ``scipy.stats.binom``.

    Title shows observed mean vs theoretical 128.0.
    """
    from scipy.stats import binom  # local import to keep scipy optional at module level

    fig, ax = plt.subplots(figsize=(10, 6))

    histogram = snapshot.avalanche.get("histogram")
    if not histogram or all(v == 0 for v in histogram):
        _empty_axes_message(ax, "No avalanche data available")
        _save_if_requested(fig, save_path)
        return fig

    histogram = np.array(histogram, dtype=np.float64)
    distances = np.arange(len(histogram))

    # Normalise histogram to probability
    total = histogram.sum()
    if total == 0:
        _empty_axes_message(ax, "No avalanche data available")
        _save_if_requested(fig, save_path)
        return fig
    probs = histogram / total

    # Only plot the region where data is non-zero (with some padding)
    nonzero = np.nonzero(histogram)[0]
    lo = max(0, nonzero[0] - 5)
    hi = min(len(histogram) - 1, nonzero[-1] + 5)

    ax.bar(
        distances[lo:hi + 1],
        probs[lo:hi + 1],
        color="steelblue",
        alpha=0.7,
        label="Empirical",
    )

    # Theoretical binomial overlay
    x_theory = np.arange(lo, hi + 1)
    y_theory = binom.pmf(x_theory, n=256, p=0.5)
    ax.plot(x_theory, y_theory, "r-", lw=2, label="Binomial(256, 0.5)")

    observed_mean = snapshot.avalanche.get("mean", 0.0)
    ax.set_title(f"Hamming Distance Distribution (mean={observed_mean:.1f}, expected=128.0)")
    ax.set_xlabel("Hamming distance")
    ax.set_ylabel("Probability")
    ax.legend()

    _save_if_requested(fig, save_path)
    return fig


def plot_byte_distribution(
    snapshot: StatsSnapshot,
    save_path: Path | None = None,
) -> plt.Figure:
    """256-bin bar chart of byte values with uniform reference line.

    Data from ``snapshot.byte_distribution["histogram"]``.
    Horizontal line at expected count = ``total_bytes / 256``.
    """
    fig, ax = plt.subplots(figsize=(12, 5))

    histogram = snapshot.byte_distribution.get("histogram")
    if not histogram or all(v == 0 for v in histogram):
        _empty_axes_message(ax, "No byte-distribution data available")
        _save_if_requested(fig, save_path)
        return fig

    histogram = np.array(histogram, dtype=np.float64)
    total_bytes = snapshot.byte_distribution.get("total_bytes", histogram.sum())
    expected = total_bytes / 256.0

    ax.bar(
        np.arange(256),
        histogram,
        width=1.0,
        color="steelblue",
        alpha=0.7,
        label="Observed",
    )
    ax.axhline(expected, color="red", linestyle="--", lw=1.5, label=f"Expected ({expected:.1f})")
    ax.set_title("Byte Value Distribution")
    ax.set_xlabel("Byte value")
    ax.set_ylabel("Count")
    ax.set_xlim(-0.5, 255.5)
    ax.legend()

    _save_if_requested(fig, save_path)
    return fig


def plot_correlation_matrix(
    snapshot: StatsSnapshot,
    save_path: Path | None = None,
) -> plt.Figure:
    """Heatmap of bit correlation matrix.

    Data from ``snapshot.correlation["correlation_matrix"]`` (2D list).
    Uses diverging colourmap centred on 0.25 (expected co-occurrence under
    independence).
    """
    fig, ax = plt.subplots(figsize=(8, 7))

    corr_matrix = snapshot.correlation.get("correlation_matrix")
    if not corr_matrix or len(corr_matrix) == 0:
        _empty_axes_message(ax, "No correlation data available")
        _save_if_requested(fig, save_path)
        return fig

    data = np.array(corr_matrix, dtype=np.float64)
    deviation = data - 0.25

    vmax = max(abs(deviation.min()), abs(deviation.max()), 0.01)
    im = ax.imshow(
        deviation,
        cmap="RdBu_r",
        vmin=-vmax,
        vmax=vmax,
        aspect="equal",
        interpolation="nearest",
    )
    fig.colorbar(im, ax=ax, label="Deviation from 0.25")
    ax.set_title("Bit Correlation Matrix (deviation from independence)")
    ax.set_xlabel("Bit position")
    ax.set_ylabel("Bit position")

    _save_if_requested(fig, save_path)
    return fig


def plot_power_spectrum(
    frequencies: np.ndarray,
    power: np.ndarray,
    position: int,
    save_path: Path | None = None,
) -> plt.Figure:
    """Power spectrum plot for a single bit position.

    Line plot of *power* vs *frequencies*.
    Title includes the bit position number.
    """
    fig, ax = plt.subplots(figsize=(10, 5))

    if len(frequencies) == 0 or len(power) == 0:
        _empty_axes_message(ax, "No spectral data available")
        _save_if_requested(fig, save_path)
        return fig

    ax.plot(frequencies, power, color="steelblue", lw=1.0)
    ax.set_title(f"Power Spectrum (bit position {position})")
    ax.set_xlabel("Frequency")
    ax.set_ylabel("Power")
    ax.grid(True, alpha=0.3)

    _save_if_requested(fig, save_path)
    return fig


def plot_dashboard(
    snapshot: StatsSnapshot,
    save_path: Path | None = None,
) -> plt.Figure:
    """2x2 summary dashboard combining 4 key plots.

    Layout::

        [bit frequency heatmap | hamming histogram  ]
        [byte distribution     | correlation matrix ]

    Uses ``plt.subplots(2, 2, figsize=(14, 10))``.
    Each panel is a simplified version of the standalone plot.
    """
    from scipy.stats import binom

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(
        f"Statistical Dashboard  ({snapshot.sample_count:,} samples, "
        f"{snapshot.engine_name})",
        fontsize=14,
        fontweight="bold",
    )

    # --- Top-left: bit frequency heatmap ---
    ax = axes[0, 0]
    freqs = snapshot.bit_frequency.get("bit_frequencies")
    if freqs and len(freqs) == 256:
        data = np.array(freqs, dtype=np.float64).reshape(16, 16)
        deviation = data - 0.5
        vmax = max(abs(deviation.min()), abs(deviation.max()), 0.01)
        im = ax.imshow(
            deviation, cmap="RdBu_r", vmin=-vmax, vmax=vmax,
            aspect="equal", interpolation="nearest",
        )
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        ax.set_title("Bit Frequency Deviation")
    else:
        _empty_axes_message(ax, "No bit-frequency data")

    # --- Top-right: hamming histogram ---
    ax = axes[0, 1]
    histogram = snapshot.avalanche.get("histogram")
    if histogram and any(v != 0 for v in histogram):
        hist_arr = np.array(histogram, dtype=np.float64)
        total = hist_arr.sum()
        if total > 0:
            probs = hist_arr / total
            nonzero = np.nonzero(hist_arr)[0]
            lo = max(0, nonzero[0] - 5)
            hi = min(len(hist_arr) - 1, nonzero[-1] + 5)
            x_range = np.arange(lo, hi + 1)
            ax.bar(x_range, probs[lo:hi + 1], color="steelblue", alpha=0.7)
            y_theory = binom.pmf(x_range, n=256, p=0.5)
            ax.plot(x_range, y_theory, "r-", lw=1.5)
            observed_mean = snapshot.avalanche.get("mean", 0.0)
            ax.set_title(f"Hamming Dist. (mean={observed_mean:.1f})")
        else:
            _empty_axes_message(ax, "No avalanche data")
    else:
        _empty_axes_message(ax, "No avalanche data")

    # --- Bottom-left: byte distribution ---
    ax = axes[1, 0]
    byte_hist = snapshot.byte_distribution.get("histogram")
    if byte_hist and any(v != 0 for v in byte_hist):
        byte_arr = np.array(byte_hist, dtype=np.float64)
        total_bytes = snapshot.byte_distribution.get("total_bytes", byte_arr.sum())
        expected = total_bytes / 256.0
        ax.bar(np.arange(256), byte_arr, width=1.0, color="steelblue", alpha=0.7)
        ax.axhline(expected, color="red", linestyle="--", lw=1.0)
        ax.set_title("Byte Distribution")
        ax.set_xlim(-0.5, 255.5)
    else:
        _empty_axes_message(ax, "No byte-distribution data")

    # --- Bottom-right: correlation matrix ---
    ax = axes[1, 1]
    corr_matrix = snapshot.correlation.get("correlation_matrix")
    if corr_matrix and len(corr_matrix) > 0:
        data = np.array(corr_matrix, dtype=np.float64)
        deviation = data - 0.25
        vmax = max(abs(deviation.min()), abs(deviation.max()), 0.01)
        im = ax.imshow(
            deviation, cmap="RdBu_r", vmin=-vmax, vmax=vmax,
            aspect="equal", interpolation="nearest",
        )
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        ax.set_title("Correlation Matrix")
    else:
        _empty_axes_message(ax, "No correlation data")

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    _save_if_requested(fig, save_path)
    return fig
