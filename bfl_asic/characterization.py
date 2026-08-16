"""Sustained-work characterization of a BFL device.

Drives the SC queued path with the library's flush-aware
``QueuedWorkSession.submit``/``drain`` and bounds in-flight jobs by
submitted-minus-drained (the device's ``JOBS IN QUEUE`` reads ~0 even
mid-scan, so it cannot drive backpressure). Produces throughput,
per-job winner-count distribution, a nonce-value histogram, and a
dead-core health verdict.

This is the quick, library-level characterization used by
``bfl-asic characterize``. The opt-in ``scripts/hw/characterize.py``
remains the deep variant (thermal telemetry over time, determinism
probe, checkpointing) for long unattended runs.
"""
from __future__ import annotations

import time

INFLIGHT_CAP = 6


def _work_stream():
    i = 0
    while True:
        i += 1
        seed = i.to_bytes(4, "big")
        yield (seed * 8, seed * 3)  # 32-byte midstate, 12-byte tail


def characterize(
    transport,
    *,
    duration: float = 60.0,
    bins: int = 256,
    engines: int | None = None,
) -> dict:
    """Run sustained work for *duration* seconds and summarise the device.

    Returns a dict with ``throughput``, ``nonce_distribution`` (histogram
    + counts), and ``health`` (dead-core report as a dict).
    """
    from bfl_asic.device import QueuedWorkSession
    from bfl_asic.health import (
        nonce_histogram, detect_dead_cores_from_counts)

    wk = _work_stream()
    nonce_values: list[int] = []
    per_job_counts: list[int] = []
    submitted = 0
    completed = 0
    errors = 0

    with QueuedWorkSession(transport) as session:
        in_flight = 0
        start = time.monotonic()
        while time.monotonic() - start < duration:
            while in_flight < INFLIGHT_CAP:
                try:
                    session.submit(*next(wk))
                    submitted += 1
                    in_flight += 1
                except Exception:
                    errors += 1
                    break
            got = session.drain()
            for r in got:
                completed += 1
                in_flight = max(0, in_flight - 1)
                per_job_counts.append(len(r.nonces))
                nonce_values.extend(r.nonces)
            if not got:
                time.sleep(0.05)
        elapsed = time.monotonic() - start
        # Drain any stragglers still in flight.
        for _ in range(40):
            got = session.drain()
            if not got:
                break
            for r in got:
                completed += 1
                per_job_counts.append(len(r.nonces))
                nonce_values.extend(r.nonces)

    yield_hist: dict[int, int] = {}
    for c in per_job_counts:
        yield_hist[c] = yield_hist.get(c, 0) + 1
    counts = nonce_histogram(nonce_values, bins)
    health = detect_dead_cores_from_counts(
        counts, len(nonce_values), engines=engines)

    return {
        "throughput": {
            "elapsed_s": round(elapsed, 2),
            "jobs_submitted": submitted,
            "jobs_completed": completed,
            "submit_errors": errors,
            "nonces_found": len(nonce_values),
            "jobs_per_s": round(completed / elapsed, 3) if elapsed else None,
            "nonces_per_s": round(len(nonce_values) / elapsed, 3)
            if elapsed else None,
            "per_job_nonce_count_hist": {str(k): v
                                         for k, v in sorted(yield_hist.items())},
        },
        "nonce_distribution": {
            "n": len(nonce_values), "bins": bins, "counts": counts,
            "min": min(nonce_values) if nonce_values else None,
            "max": max(nonce_values) if nonce_values else None,
        },
        "health": {
            "healthy": health.healthy,
            "dead_regions": [
                {"start_bin": r.start_bin, "end_bin": r.end_bin,
                 "observed": r.observed, "expected": round(r.expected, 1)}
                for r in health.dead_regions
            ],
            "cold_fraction": round(health.cold_fraction, 4),
            "estimated_dead_engines": health.estimated_dead_engines,
            "summary": health.summary(),
        },
    }
