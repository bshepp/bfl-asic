#!/usr/bin/env python3
"""Regenerate docs/images/production-census.png from the confirmed serials.

The figure previously existed with no generator, so it silently went stale
whenever a serial was added. Edit HELD/OBSERVED below and re-run.

    python scripts/production_census_figure.py
"""
from __future__ import annotations
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HELD = [2659, 5794, 24991, 24992]
OBSERVED = [6068, 7857, 10216, 10265, 13626, 22662, 23617, 24017, 25327]

# (x, label, stagger level) -- levels avoid collisions in the high cluster
LABELS = [
    (2659, "002659", 0), (5794, "005794", 0), (6068, "006068", 1),
    (7857, "007857", 0), (10240, "010216 / 010265\n(near-pair, 49 apart)", 1),
    (13626, "013626", 0), (22662, "022662", 0), (23617, "023617", 1),
    (24017, "024017", 2), (24991, "024991 / 024992\n(pair, 1 apart)", 0),
    (25327, "025327", 1),
]

BLUE, DARK, RED, ORANGE = "#1f77b4", "#333333", "#a01020", "#d2820a"


def main() -> None:
    serials = sorted(HELD + OBSERVED)
    k, mn, mx = len(serials), serials[0], serials[-1]
    gap = (mx - mn) / (k - 1)
    est = mx + gap
    hi = est + est / k                      # ceiling + ~1 SE

    fig, ax = plt.subplots(figsize=(14, 4))
    ax.axvspan(mx, hi, color=ORANGE, alpha=0.15, lw=0,
               label=f"estimate band (~{mx/1000:.1f}k-{hi/1000:.1f}k)")
    ax.axvline(est, color=ORANGE, ls="--", lw=2,
               label=f"point estimate ~{est:,.0f}")
    ax.axvline(mx, color=RED, lw=2, label=f"confirmed ceiling {mx:,}")
    ax.scatter(OBSERVED, [0] * len(OBSERVED), s=200, color=DARK, zorder=3,
               label="observed (listing photo)")
    ax.scatter(HELD, [0] * len(HELD), s=200, color=BLUE, zorder=4,
               label="held (this project)")

    for x, text, lvl in LABELS:
        ax.annotate(text, (x, 0), textcoords="offset points",
                    xytext=(0, 18 + lvl * 22), ha="center", fontsize=8)

    ax.set_xlim(0, hi * 1.03)
    ax.set_ylim(-0.5, 1.2)
    ax.set_yticks([])
    ax.set_xlabel("BFL Jalapeño board serial number")
    ax.set_title(f"BFL Jalapeño production census — {k} confirmed "
                 f"serials → ~{round(est, -2):,.0f} units built "
                 f"(German-tank estimate)")
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="x", ls=":", alpha=0.4)
    ax.legend(loc="lower left", ncol=2, fontsize=9, framealpha=0.95)
    fig.tight_layout()

    out = os.path.join("docs", "images", "production-census.png")
    fig.savefig(out, dpi=100)
    print(f"wrote {out}  (k={k}, max={mx:,}, est={est:,.0f}, band {mx:,}-{hi:,.0f})")


if __name__ == "__main__":
    main()
