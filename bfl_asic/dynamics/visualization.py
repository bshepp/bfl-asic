"""Matplotlib-based plotting for iterated hash dynamics results.

Provides visualisation functions for orbit trajectories, convergence
analysis, and cycle/tail length distributions.  All functions use the
``Agg`` backend (headless) and return :class:`matplotlib.figure.Figure`
objects.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from bfl_asic.dynamics.orbit import OrbitResult  # noqa: E402
from bfl_asic.dynamics.convergence import ConvergenceResult  # noqa: E402


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
# Orbit plots
# -------------------------------------------------------------------

def plot_orbit_hamming(
    orbit: OrbitResult,
    save_path: Path | None = None,
) -> plt.Figure:
    """Plot Hamming distance between consecutive orbit samples.

    X-axis: iteration number (from ``trajectory_sample``).
    Y-axis: Hamming distance.
    Horizontal reference line at 128 (expected for random).
    Title includes seed (first 8 hex chars) and mean Hamming.
    """
    fig, ax = plt.subplots(figsize=(10, 5))

    if not orbit.hamming_distances:
        _empty_axes_message(ax, "No Hamming distance data available")
        _save_if_requested(fig, save_path)
        return fig

    # X-axis: iterations corresponding to each Hamming distance measurement
    # trajectory_sample[0] is the seed; distances[i] is between sample i and i+1
    iterations = [pt.iteration for pt in orbit.trajectory_sample[1:]]
    # If lengths don't match (shouldn't happen, but be defensive), trim
    n = min(len(iterations), len(orbit.hamming_distances))
    iterations = iterations[:n]
    distances = orbit.hamming_distances[:n]

    seed_hex = orbit.seed[:4].hex()
    mean_hd = orbit.mean_hamming if orbit.mean_hamming is not None else 0.0

    ax.plot(iterations, distances, color="steelblue", lw=1.0, alpha=0.8, marker=".", markersize=3)
    ax.axhline(128, color="red", linestyle="--", lw=1.0, label="Expected (128)")
    if orbit.mean_hamming is not None:
        ax.axhline(
            orbit.mean_hamming, color="orange", linestyle=":",
            lw=1.5, label=f"Mean ({mean_hd:.1f})",
        )
    ax.set_title(f"Orbit Hamming Distances (seed={seed_hex}..., mean={mean_hd:.1f})")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Hamming distance")
    ax.legend()
    ax.grid(True, alpha=0.3)

    _save_if_requested(fig, save_path)
    return fig


def plot_convergence(
    result: ConvergenceResult,
    save_path: Path | None = None,
) -> plt.Figure:
    """Plot multiple orbit trajectories showing convergence.

    Simple 2D projection: use the first 2 bytes of each trajectory
    sample as ``(x, y)``.  Different colour per seed.  Mark convergence
    points (if any) with special markers.
    """
    fig, ax = plt.subplots(figsize=(10, 8))

    if not result.orbits:
        _empty_axes_message(ax, "No orbit data available")
        _save_if_requested(fig, save_path)
        return fig

    cmap = matplotlib.colormaps["tab10"]

    for idx, orbit in enumerate(result.orbits):
        if not orbit.trajectory_sample:
            continue
        xs = [pt.value[0] for pt in orbit.trajectory_sample]
        ys = [pt.value[1] for pt in orbit.trajectory_sample]
        colour = cmap(idx % 10)
        seed_hex = orbit.seed[:4].hex()
        ax.plot(xs, ys, "-o", color=colour, markersize=3, alpha=0.6, label=f"Seed {seed_hex}...")
        # Mark start
        ax.plot(xs[0], ys[0], "s", color=colour, markersize=8, zorder=5)

    # Mark convergence points
    for seed_a, seed_b, iteration in result.convergence_pairs:
        ax.annotate(
            f"Conv @{iteration}",
            xy=(0.5, 0.5), xycoords="axes fraction",
            fontsize=8, color="red", alpha=0.7,
        )

    ax.set_title(
        f"Orbit Convergence ({result.seed_count} seeds, "
        f"{len(result.convergence_pairs)} convergence events)"
    )
    ax.set_xlabel("Byte 0 value")
    ax.set_ylabel("Byte 1 value")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.3)

    _save_if_requested(fig, save_path)
    return fig


def plot_tail_cycle_distribution(
    orbits: list[OrbitResult],
    save_path: Path | None = None,
) -> plt.Figure:
    """Histogram of tail lengths and cycle lengths across many seeds.

    Two subplots side by side:
    - Left: tail lengths (only where detected, i.e. not ``None``).
    - Right: cycle lengths (only where detected).

    If no cycles are detected, a text message is shown instead.
    """
    fig, (ax_tail, ax_cycle) = plt.subplots(1, 2, figsize=(12, 5))

    tail_lengths = [o.tail_length for o in orbits if o.tail_length is not None]
    cycle_lengths = [o.cycle_length for o in orbits if o.cycle_length is not None]

    # Tail lengths
    if tail_lengths:
        ax_tail.hist(tail_lengths, bins="auto", color="steelblue", alpha=0.7, edgecolor="white")
        ax_tail.set_title(f"Tail Lengths (n={len(tail_lengths)})")
        ax_tail.set_xlabel("Tail length")
        ax_tail.set_ylabel("Count")
    else:
        _empty_axes_message(ax_tail, "No tail lengths detected")
        ax_tail.set_title("Tail Lengths")

    # Cycle lengths
    if cycle_lengths:
        ax_cycle.hist(cycle_lengths, bins="auto", color="darkorange", alpha=0.7, edgecolor="white")
        ax_cycle.set_title(f"Cycle Lengths (n={len(cycle_lengths)})")
        ax_cycle.set_xlabel("Cycle length")
        ax_cycle.set_ylabel("Count")
    else:
        _empty_axes_message(ax_cycle, "No cycles detected")
        ax_cycle.set_title("Cycle Lengths")

    fig.suptitle(f"Tail & Cycle Distribution ({len(orbits)} orbits)", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    _save_if_requested(fig, save_path)
    return fig
