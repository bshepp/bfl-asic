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


def est_for_power(serials, k):
    """German-tank point estimate; the denominator for p_hit."""
    return serials[-1] + (serials[-1] - serials[0]) / (k - 1)


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
    print()
    print("stopping rule -- if the window STAYS empty, how much more is needed?")
    print("  The window is now PRE-REGISTERED, so future serials are a clean")
    print("  test. The existing serials do NOT count toward it: the window was")
    print("  derived from them, so reusing them would be circular.")
    est_p = est_for_power(s, k)
    p_hit = g / est_p
    p_miss = 1 - p_hit
    print(f"  a new serial lands inside it with p = {g:,}/{est_p:,.0f}"
          f" = {p_hit:.3f}")
    print()
    print(f"  {'new serials':>12} {'p-value':>11} {'census size':>12}")
    for m in (3, 5, 8, 12, 18, 23, 35):
        print(f"  {m:>12} {p_miss ** m:>11.5f} {k + m:>12}")
    print()
    print("  thresholds:")
    for thr, lab in ((0.05, "unlikely"), (0.01, "strong"),
                     (0.001, "very strong"), (1e-6, "~impossible")):
        m = math.ceil(math.log(thr) / math.log(p_miss))
        print(f"    p < {thr:<7g} {lab:<13} {m:>3} more  (census -> {k + m})")
    print()
    print("  NOTE: assumes uniform sampling. The real sample is whatever got")
    print("  listed, so treat these as a floor on the data needed, not a promise.")
    print("\nif the block was never issued:")
    print(f"  contiguous estimate            ~{est:,.0f}")
    print(f"  minus the skipped block        ~{est - g:,.0f}")
    print(f"  re-fit on gap-removed serials  ~{est_c:,.0f} built "
          f"(+ {g:,} numbers never issued)")


if __name__ == "__main__":
    main()
