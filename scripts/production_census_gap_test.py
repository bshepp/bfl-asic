#!/usr/bin/env python3
"""Is the ~9,000 gap in the Jalapeno serial run real, or just sparse sampling?

Reports the maximum-spacing test for the largest gap, both analytically and by
Monte Carlo, plus what a genuine skip would do to the production estimate.

    python scripts/production_census_gap_test.py
"""
from __future__ import annotations
import math
import random

SERIALS = [2659, 5794, 6068, 7857, 10216, 10265, 13626, 22662,
           23617, 24017, 24991, 24992, 25327]
TRIALS = 400_000
SEED = 0


def max_spacing_p(frac: float, spacings: int) -> float:
    """P(largest of `spacings` uniform spacings >= `frac` of the span)."""
    return sum((-1) ** (j + 1) * math.comb(spacings, j) * (1 - j * frac) ** (spacings - 1)
               for j in range(1, int(1 / frac) + 1))


def monte_carlo_p(frac: float, k: int, trials: int, seed: int) -> float:
    rng = random.Random(seed)
    hits = 0
    for _ in range(trials):
        pts = sorted(rng.random() for _ in range(k - 2))   # interior points
        prev = 0.0
        biggest = 0.0
        for x in pts + [1.0]:
            biggest = max(biggest, x - prev)
            prev = x
        hits += biggest >= frac
    return hits / trials


def main() -> None:
    s = sorted(set(SERIALS))
    k = len(s)
    span = s[-1] - s[0]
    mean_gap = span / (k - 1)
    gaps = sorted(((s[i + 1] - s[i], s[i], s[i + 1]) for i in range(k - 1)),
                  reverse=True)
    g, lo, hi = gaps[0]
    frac = g / span

    print(f"k={k}  span {s[0]:,}-{s[-1]:,} = {span:,}  mean gap {mean_gap:,.0f}")
    print("\nlargest gaps:")
    for gg, a, b in gaps[:3]:
        print(f"  {gg:>6,}  {a:06d} -> {b:06d}  ({gg/mean_gap:.1f}x mean, "
              f"{100*gg/span:.1f}% of span)")

    pa = max_spacing_p(frac, k - 1)
    pm = monte_carlo_p(frac, k, TRIALS, SEED)
    print(f"\nP(largest gap >= {g:,} | uniform sampling)")
    print(f"  analytic     {pa:.4f}")
    print(f"  monte carlo  {pm:.4f}   ({TRIALS:,} trials, seed {SEED})")

    est = s[-1] + mean_gap
    compressed = sorted(x if x < lo else x - g for x in s)
    cspan = compressed[-1] - compressed[0]
    est_c = compressed[-1] + cspan / (len(compressed) - 1)
    print("\nif the block was never issued:")
    print(f"  contiguous estimate            ~{est:,.0f}")
    print(f"  minus the skipped block        ~{est - g:,.0f}")
    print(f"  re-fit on gap-removed serials  ~{est_c:,.0f} built "
          f"(+ {g:,} numbers never issued)")


if __name__ == "__main__":
    main()
