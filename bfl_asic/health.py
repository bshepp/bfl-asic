"""Engine-health / dead-core detection from the winning-nonce distribution.

The idea comes from the 2026-08-15 characterization: an aggregate
nonce-value histogram cannot *map* healthy engines (if each engine scans a
contiguous sub-range, their winners sum to a uniform whole), but it *can*
expose a **dead** engine — a range no engine covers shows up as a cold
(under-represented) band.

Detection is a per-bin Poisson test: under "all engines healthy, uniform
coverage" each bin holds ~Poisson(mean = n/bins). A bin far below the mean
(z = (count - mean) / sqrt(mean) below -``z_threshold``) is cold; a
*contiguous run* of cold bins (length >= ``min_run``) is a dead region,
whereas an isolated cold bin is just noise.

Important assumption, stated plainly: this localizes a dead engine only if
engines cover **contiguous** nonce sub-ranges. If engines interleave the
space, a dead one thins the whole histogram uniformly and is not
localizable here — the overall nonce *yield rate* would drop instead. See
``docs/characterization/README.md``.

Pure functions, no I/O.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

NONCE_SPACE = 1 << 32


@dataclass
class DeadRegion:
    """A contiguous band of cold histogram bins (a suspected dead engine)."""

    start_bin: int
    end_bin: int          # inclusive
    nonce_start: int
    nonce_end: int        # exclusive
    observed: int
    expected: float

    @property
    def span_fraction(self) -> float:
        """Fraction of the 32-bit nonce space this region covers."""
        return (self.nonce_end - self.nonce_start) / NONCE_SPACE


@dataclass
class EngineHealthReport:
    total_nonces: int
    bins: int
    mean_per_bin: float
    dead_regions: list[DeadRegion] = field(default_factory=list)
    cold_fraction: float = 0.0
    estimated_dead_engines: float | None = None
    healthy: bool = True

    def summary(self) -> str:
        head = (f"Engine health: {self.total_nonces} nonces over "
                f"{self.bins} bins (mean {self.mean_per_bin:.1f}/bin)")
        if self.healthy:
            return head + "\n  verdict: HEALTHY (no dead cores detected)"
        lines = [head, "  verdict: DEAD CORE(S) DETECTED"]
        if self.estimated_dead_engines is not None:
            lines.append(f"  estimated dead engines: "
                         f"{self.estimated_dead_engines} "
                         f"({self.cold_fraction:.1%} of nonce space cold)")
        else:
            lines.append(f"  cold fraction: {self.cold_fraction:.1%} "
                         f"of nonce space")
        for r in self.dead_regions:
            lines.append(
                f"  - bins {r.start_bin}-{r.end_bin} "
                f"[0x{r.nonce_start:08x}, 0x{r.nonce_end:08x}): "
                f"observed {r.observed}, expected {r.expected:.0f}")
        return "\n".join(lines)


def nonce_histogram(nonces, bins: int) -> list[int]:
    """Count nonce values into ``bins`` equal slices of the 32-bit space."""
    if bins < 1:
        raise ValueError("bins must be >= 1")
    counts = [0] * bins
    width = NONCE_SPACE // bins
    for v in nonces:
        counts[min(v // width, bins - 1)] += 1
    return counts


def _cold_runs(counts: list[int], mean: float, z_threshold: float,
               min_run: int) -> list[tuple[int, int]]:
    """Return (start, end_inclusive) bin runs that are significantly cold."""
    if mean <= 0:
        return []
    sd = math.sqrt(mean)
    cold = [(c - mean) / sd < -z_threshold for c in counts]
    runs: list[tuple[int, int]] = []
    i = 0
    n = len(counts)
    while i < n:
        if cold[i]:
            j = i
            while j + 1 < n and cold[j + 1]:
                j += 1
            if (j - i + 1) >= min_run:
                runs.append((i, j))
            i = j + 1
        else:
            i += 1
    return runs


def detect_dead_cores_from_counts(
    counts: list[int],
    total_nonces: int,
    *,
    engines: int | None = None,
    z_threshold: float = 4.0,
    min_run: int = 2,
) -> EngineHealthReport:
    """Detect dead-core bands from a prebuilt nonce histogram.

    ``counts`` is the per-bin histogram; ``total_nonces`` its sum (passed
    explicitly so a caller can pass a run's stored total).
    """
    bins = len(counts)
    mean = total_nonces / bins if bins else 0.0
    runs = _cold_runs(counts, mean, z_threshold, min_run)
    width = NONCE_SPACE // bins if bins else NONCE_SPACE
    regions: list[DeadRegion] = []
    cold_bins = 0
    for start, end in runs:
        cold_bins += end - start + 1
        nonce_end = NONCE_SPACE if end == bins - 1 else (end + 1) * width
        regions.append(DeadRegion(
            start_bin=start, end_bin=end,
            nonce_start=start * width, nonce_end=nonce_end,
            observed=sum(counts[start:end + 1]),
            expected=mean * (end - start + 1),
        ))
    cold_fraction = cold_bins / bins if bins else 0.0
    est = round(cold_fraction * engines, 1) if engines is not None else None
    return EngineHealthReport(
        total_nonces=total_nonces, bins=bins, mean_per_bin=mean,
        dead_regions=regions, cold_fraction=cold_fraction,
        estimated_dead_engines=est, healthy=(not regions),
    )


def detect_dead_cores(
    nonces,
    *,
    bins: int = 256,
    engines: int | None = None,
    z_threshold: float = 4.0,
    min_run: int = 2,
) -> EngineHealthReport:
    """Histogram ``nonces`` and detect dead-core bands."""
    counts = nonce_histogram(nonces, bins)
    return detect_dead_cores_from_counts(
        counts, sum(counts), engines=engines,
        z_threshold=z_threshold, min_run=min_run)
