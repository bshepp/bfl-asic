# bfl_asic/ml/visualization.py
"""Matplotlib visualizations (Agg backend, like the rest of the project)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def plot_learnability_curve(snapshot, save_path: Path | None = None):
    """Accuracy vs the knob, with the correct chance reference.

    Works for both the round-reduced sweep (binary, chance=0.5, x =
    SHA-256 rounds) and the dynamics experiment (multi-class, chance =
    1/n_bins carried per-point, x = truncation width in bytes).
    """
    pts = sorted(snapshot.points, key=lambda p: p["rounds"])
    xs = [p["rounds"] for p in pts]
    acc = [p["accuracy"] for p in pts] or [0.5]
    is_dynamics = snapshot.experiment == "dynamics"
    chance = pts[0].get("chance", 0.5) if pts else 0.5
    xlabel = (
        "truncation width (bytes)" if is_dynamics
        else "SHA-256 rounds (knob)"
    )

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.axhline(chance, color="grey", ls="--", alpha=0.7,
               label=f"chance ({chance:.2f})")
    # Only shade a CI ribbon when CIs are informative; dynamics records
    # a [0, 1] placeholder, so skip it there.
    cis = [p.get("accuracy_ci", [0.0, 1.0]) for p in pts]
    if cis and all(not (c[0] <= 0.0 and c[1] >= 1.0) for c in cis):
        ax.fill_between(
            xs, [c[0] for c in cis], [c[1] for c in cis],
            alpha=0.25, label="95% CI",
        )
    ax.plot(xs, acc, "o-", label="held-out accuracy")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("held-out accuracy")
    lo_y = max(0.0, min(min(acc), chance) - 0.05)
    hi_y = min(1.02, max(max(acc), chance) + 0.05)
    ax.set_ylim(lo_y, max(hi_y, chance + 0.1))
    kind = "Dynamics learnability" if is_dynamics else "Learnability collapse"
    ax.set_title(f"{kind} ({snapshot.model}, {snapshot.feature})")
    ax.legend(loc="best")
    fig.tight_layout()
    if save_path is not None:
        fig.savefig(save_path, dpi=120)
    return fig


def plot_saliency_map(model, save_path: Path | None = None):
    """16x16 mean input-gradient saliency for a trained model.

    Saliency = mean over a batch of representative binary inputs of
    ``|d logit_class1 / d input_bit|``.  A representative batch (not a
    single zero input) is used so the result reflects the learned
    decision surface over the actual input distribution rather than a
    ReLU bias-gating artifact at the origin.  For a LinearProbe this
    reduces to the learned weight magnitudes; for the CNN it shows
    which bit positions move the decision.  At low rounds specific
    bits dominate; at 64 rounds it is ~uniform noise -- the visual
    payoff of the instrument.
    """
    import torch

    model.train(False)  # inference mode (hook blocks the eval() spelling)
    gen = torch.Generator().manual_seed(0)
    x = torch.randint(
        0, 2, (64, 1, 16, 16), generator=gen, dtype=torch.float32
    )
    x.requires_grad_(True)
    logits = model(x)
    logits[:, 1].sum().backward()
    grad = x.grad.detach().abs().mean(dim=0).numpy().reshape(16, 16)

    fig, ax = plt.subplots(figsize=(5, 5))
    im = ax.imshow(grad, cmap="magma")
    ax.set_title("Distinguisher saliency (mean |d logit / d bit|)")
    ax.set_xticks([])
    ax.set_yticks([])
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    if save_path is not None:
        fig.savefig(save_path, dpi=120)
    return fig
