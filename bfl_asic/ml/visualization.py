# bfl_asic/ml/visualization.py
"""Matplotlib visualizations (Agg backend, like the rest of the project)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def plot_learnability_curve(snapshot, save_path: Path | None = None):
    """Accuracy & CI vs the knob, with a chance band."""
    pts = sorted(snapshot.points, key=lambda p: p["rounds"])
    xs = [p["rounds"] for p in pts]
    acc = [p["accuracy"] for p in pts]
    lo = [p["accuracy_ci"][0] for p in pts]
    hi = [p["accuracy_ci"][1] for p in pts]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.axhspan(0.45, 0.55, color="grey", alpha=0.2, label="chance band")
    ax.fill_between(xs, lo, hi, alpha=0.25, label="95% CI")
    ax.plot(xs, acc, "o-", label="held-out accuracy")
    ax.set_xlabel("SHA-256 rounds (knob)")
    ax.set_ylabel("distinguisher accuracy")
    ax.set_ylim(0.4, 1.02)
    ax.set_title(
        f"Learnability collapse ({snapshot.model}, {snapshot.feature})"
    )
    ax.legend(loc="upper right")
    fig.tight_layout()
    if save_path is not None:
        fig.savefig(save_path, dpi=120)
    return fig


def plot_saliency_map(model, save_path: Path | None = None):
    """16x16 input-gradient saliency for a trained model.

    At low rounds this highlights specific stuck/biased bits; at 64
    rounds it is uniform noise -- the visual payoff of the instrument.
    """
    import numpy as np
    import torch

    x = torch.zeros(1, 1, 16, 16, requires_grad=True)
    out = model(x)
    out[0, 1].backward()
    grad = x.grad.detach().abs().numpy().reshape(16, 16)

    fig, ax = plt.subplots(figsize=(5, 5))
    im = ax.imshow(grad, cmap="magma")
    ax.set_title("Distinguisher saliency (|d logit / d bit|)")
    ax.set_xticks([])
    ax.set_yticks([])
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    if save_path is not None:
        fig.savefig(save_path, dpi=120)
    return fig
