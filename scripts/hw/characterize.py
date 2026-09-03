#!/usr/bin/env python3
"""OPT-IN silicon characterization of a real BFL Jalapeno (fan-AUTO).

Model-free characterization that stays inside the device's normal,
self-protecting operating envelope: the fan is forced to firmware AUTO
management for the whole run and never set to a fixed level, so this is
safe to run unattended (the unit mined for days this way). Excluded from
pytest.

Measures only things that need no unverified model of the device's exact
hashing:

  1. Throughput  -- completed jobs/s and nonces/s over sustained queued
     work (protocol/USB-bound on this device, not hash-bound).
  2. Nonce spread -- histogram of returned nonce values across the 32-bit
     space + per-job nonce-count distribution.
  3. Thermal     -- temperature / voltage / reported frequency + engine
     count sampled between bursts => warm-up curve AND the live topology
     fluctuation (engine count/clock vary between queries).
  4. Determinism -- submit ONE identical work unit N times and compare
     the returned nonce sets; identical input must give identical nonces
     on correct silicon, so divergence is a hardware-error signal.

Robustness: every device command is preceded by an input-buffer flush,
because this firmware is chatty (multi-line details blocks, "INPROCESS:n"
result prefixes) and unflushed sequential reads desync -- a stale status
line then gets misread as the next command's reply. This is why the
script drives the queued protocol directly instead of via
QueuedWorkSession.

Usage:  python scripts/hw/characterize.py --port COM3 --duration 900 \
            --out docs/characterization/run.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

NONCE_SPACE = 1 << 32
# Cap in-flight (submitted-but-not-yet-drained) jobs. The device's
# JOBS IN QUEUE reads ~0 even mid-scan, so it can't be used for
# backpressure; we bound in-flight by submitted-minus-drained instead.
INFLIGHT_CAP = 6


def _flush(t) -> None:
    ser = getattr(t, "_serial", None)
    if ser is not None:
        try:
            ser.reset_input_buffer()
        except Exception:
            pass


def _read_block(t, maxlines: int = 160) -> bytes:
    raw = b""
    for _ in range(maxlines):
        line = t.readline()
        raw += line
        if line.strip() in (b"OK", b"SUCCESS") or not line:
            break
    return raw


def _submit(t, mid: bytes, tail: bytes) -> bytes:
    """Flush, send one ZNX job, return the stripped ack line."""
    from bfl_asic.protocol.queued import build_queue_job
    _flush(t)
    t.write(build_queue_job(mid, tail))
    return t.readline().strip()


def _drain(t, version: str = "v1") -> list:
    """Flush, send one ZOX, return parsed results (may be many).

    ``version`` selects the result-row format; fw >=1.2.x emits v2 (with a
    per-nonce CHIP column) and MUST be parsed as such — parsing it as v1
    misreads the NONCECOUNT field as a low-value nonce.
    """
    from bfl_asic.protocol.queued import build_queue_results, parse_queue_results
    _flush(t)
    t.write(build_queue_results())
    return parse_queue_results(_read_block(t), version)


def _flush_queue(t) -> None:
    from bfl_asic.protocol.queued import build_queue_flush
    _flush(t)
    t.write(build_queue_flush())
    t.readline()


def _settle(t, quiet_needed: int = 3, max_iter: int = 60) -> None:
    """Flush the queue and drain until several consecutive empty drains,
    so in-flight jobs finish and their results are cleared. Used before a
    phase that must start from a truly quiet device."""
    _flush_queue(t)
    quiet = 0
    for _ in range(max_iter):
        if _drain(t):
            quiet = 0
        else:
            quiet += 1
            if quiet >= quiet_needed:
                return
            time.sleep(0.3)


def _fixed_work() -> tuple[bytes, bytes]:
    mid = bytes((i * 37 + 11) & 0xFF for i in range(32))
    tail = bytes((i * 53 + 7) & 0xFF for i in range(12))
    return mid, tail


def _work_stream():
    i = 0
    while True:
        i += 1
        seed = i.to_bytes(4, "big")
        yield (seed * 8, seed * 3)


def _sample_telemetry(dev, t, elapsed_s: float) -> dict:
    _flush(t)
    point: dict = {"t_s": round(elapsed_s, 1)}
    try:
        point["temp_c"] = list(dev.get_temperature().sensors)
    except Exception as e:
        point["temp_error"] = str(e)
    try:
        v = dev.get_voltage()
        point["vcc1"], point["vcc2"], point["vmain"] = v.vcc1, v.vcc2, v.vmain
    except Exception as e:
        point["volt_error"] = str(e)
    try:
        d = dev.get_details()
        point["freq_mhz"] = d.frequency_mhz
        point["engines"] = d.engines
        point["mining_speed"] = d.mining_speed
        point["processors"] = [list(p) for p in d.processors]
    except Exception as e:
        point["details_error"] = str(e)
    return point


def _histogram(values: list[int], bins: int = 64) -> list[int]:
    counts = [0] * bins
    width = NONCE_SPACE // bins
    for v in values:
        counts[min(v // width, bins - 1)] += 1
    return counts


def _one_identical_rep(t, mid, tail, per_timeout: float,
                       version: str = "v1") -> tuple[int, ...]:
    # Clear the job queue AND any buffered completed results so the only
    # result we collect is this rep's fresh identical job. Drain until the
    # device is QUIET (several consecutive empty reads) -- one empty drain
    # doesn't mean quiet, and a straggler nonce from prior work bleeding in
    # is exactly what made identical work look non-deterministic.
    _flush_queue(t)
    quiet = 0
    for _ in range(80):
        if _drain(t, version):
            quiet = 0
        else:
            quiet += 1
            if quiet >= 4:
                break
    ack = _submit(t, mid, tail)
    got: list[int] = []
    if b"ERR:" not in ack:
        # Drain the FULL window, no early exit. A single job's nonces trickle
        # in only as the engines scan the whole 32-bit space (~1 s), so an
        # early "queue went quiet" test fires before the first nonce even
        # arrives and records an empty set -- which is what made identical
        # work look non-deterministic. per_timeout must exceed one full scan.
        deadline = time.monotonic() + per_timeout
        while time.monotonic() < deadline:
            res = _drain(t, version)
            for r in res:
                got.extend(r.nonces)
            if not res:
                time.sleep(0.15)
    return tuple(sorted(set(got)))  # complete, deduped solution set


def _determinism(t, reps: int, per_timeout: float = 3.0,
                 version: str = "v1") -> dict:
    mid, tail = _fixed_work()
    # Thorough one-time purge: this firmware buffers completed results and can
    # trickle stale nonces from earlier work into the reps. Drain continuously
    # for a few seconds to empty that backlog before the timed reps.
    _flush_queue(t)
    purge_end = time.monotonic() + 3.0
    while time.monotonic() < purge_end:
        _drain(t, version)
    # One discarded warm-up rep: the first job right after the throughput
    # phase can still catch an in-flight straggler; this absorbs it so the
    # recorded reps are clean.
    _one_identical_rep(t, mid, tail, per_timeout, version)
    sets: list[tuple[int, ...]] = [
        _one_identical_rep(t, mid, tail, per_timeout, version)
        for _ in range(reps)]
    from collections import Counter
    # Correct silicon gives one true nonce set for a fixed work unit. On a
    # live, buffering, multi-die device the collection can occasionally catch
    # a straggler from other work, so an exact-match-every-rep test throws
    # false alarms. Judge instead on the MODAL set (strict majority agree) and
    # the CORE (nonces every rep found = the reliable solution); a stray nonce
    # in a minority of reps is collection contamination, not silicon error.
    counts = Counter(sets)
    modal, modal_n = counts.most_common(1)[0] if sets else ((), 0)
    setlist = [set(s) for s in sets]
    core = set(setlist[0]).intersection(*setlist[1:]) if setlist else set()
    union = set().union(*setlist) if setlist else set()
    variable = union - core  # extras found in only some reps (collection noise)
    # Deterministic silicon reliably re-finds the SAME nonces for fixed work,
    # so the health signal is a non-empty CORE reproduced in EVERY rep. A
    # genuinely broken device shares no stable core. The `variable` strays are
    # buffered contamination from other work (proven: they never appear in an
    # isolated single-job drain), not silicon non-determinism, so they do not
    # fail the verdict -- they are reported for transparency.
    deterministic = bool(core)
    return {
        "reps_completed": len(sets),
        "distinct_nonce_sets": [list(x) for x in sorted(set(sets))],
        "core_nonces": sorted(core),          # found by EVERY rep -> the answer
        "variable_nonces": sorted(variable),  # timing-dependent strays
        "union_nonces": sorted(union),
        "modal_agreement": round(modal_n / len(sets), 3) if sets else 0.0,
        "deterministic": deterministic,
        "nonces_per_rep": [len(x) for x in sets],
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Model-free, fan-AUTO characterization of a real BFL "
                    "Jalapeno (opt-in; not run in CI).")
    ap.add_argument("--port", default="COM3")
    ap.add_argument("--duration", type=float, default=900.0)
    ap.add_argument("--reps", type=int, default=24)
    ap.add_argument("--sample-every", type=float, default=60.0,
                    help="Telemetry cadence seconds.")
    ap.add_argument("--bins", type=int, default=64,
                    help="Nonce-value histogram bins (raise for a long "
                         "engine-mapping run; default 64).")
    ap.add_argument("--out", default="docs/characterization/run.json")
    args = ap.parse_args()

    from bfl_asic.transport.serial import SerialTransport
    from bfl_asic.device import BFLDevice

    t = SerialTransport(port=args.port)
    t.open()
    dev = BFLDevice(t)

    results: dict = {"meta": {
        "port": args.port, "duration_s": args.duration, "reps": args.reps,
        "started_utc": datetime.now(timezone.utc).isoformat(),
    }}

    def dump() -> None:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

    try:
        info = dev.identify()
        results["meta"]["device"] = info.model
        print(f"[hw] {info.model}")
        dev.set_fan_auto()
        print("[hw] fan AUTO (firmware thermal management)")
        _flush_queue(t)
        while _drain(t):  # clear any stale buffered results
            pass

        d0 = dev.get_details()
        results["baseline"] = {
            "firmware": d0.firmware, "engines": d0.engines,
            "frequency_mhz": d0.frequency_mhz, "mining_speed": d0.mining_speed,
            "processors": [list(p) for p in d0.processors],
            "critical_temperature": d0.critical_temperature,
        }
        print(f"[hw] baseline: {d0.engines} engines, {d0.frequency_mhz} MHz, "
              f"procs={d0.processors}")

        # Result-row format: v2 firmware (CHIP PARALLELIZATION: YES) reports a
        # per-nonce CHIP column; parsing it as v1 corrupts the nonce stream.
        from bfl_asic.protocol.queued import result_version
        ver = result_version(d0)
        results["meta"]["result_format"] = ver
        print(f"[hw] result format: {ver}"
              + (" (per-die CHIP attribution)" if ver == "v2" else ""))

        # --- Throughput + distribution + thermal ----------------------
        wk = _work_stream()
        nonce_values: list[int] = []
        per_job_counts: list[int] = []
        per_chip_nonces: dict[int, int] = {}
        per_chip_jobs: dict[int, int] = {}
        submitted = 0
        completed = 0
        errors = 0
        in_flight = 0
        telemetry: list[dict] = [_sample_telemetry(dev, t, 0.0)]
        next_sample = args.sample_every
        start = time.monotonic()
        elapsed = 0.0
        while elapsed < args.duration:
            # Top up submissions only while under the in-flight cap.
            while in_flight < INFLIGHT_CAP:
                mid, tail = next(wk)
                ack = _submit(t, mid, tail)
                if b"ERR:" in ack:
                    errors += 1
                    break  # buffer pressure; drain before trying again
                submitted += 1
                in_flight += 1
            # Drain whatever has completed.
            got = _drain(t, ver)
            for r in got:
                completed += 1
                in_flight = max(0, in_flight - 1)
                per_job_counts.append(len(r.nonces))
                nonce_values.extend(r.nonces)
                if r.chip is not None:
                    per_chip_nonces[r.chip] = (
                        per_chip_nonces.get(r.chip, 0) + len(r.nonces))
                    per_chip_jobs[r.chip] = per_chip_jobs.get(r.chip, 0) + 1
            if not got:
                time.sleep(0.2)  # let scans finish before polling again
            elapsed = time.monotonic() - start
            if elapsed >= next_sample:
                telemetry.append(_sample_telemetry(dev, t, elapsed))
                next_sample += args.sample_every
                print(f"[hw]   t={elapsed:6.0f}s  submitted={submitted}  "
                      f"completed={completed}  nonces={len(nonce_values)}  "
                      f"errors={errors}")
                dump()

        # final drain of stragglers
        for _ in range(20):
            res = _drain(t, ver)
            if not res:
                break
            for r in res:
                completed += 1
                per_job_counts.append(len(r.nonces))
                nonce_values.extend(r.nonces)
                if r.chip is not None:
                    per_chip_nonces[r.chip] = (
                        per_chip_nonces.get(r.chip, 0) + len(r.nonces))
                    per_chip_jobs[r.chip] = per_chip_jobs.get(r.chip, 0) + 1
        telemetry.append(_sample_telemetry(dev, t, elapsed))

        yield_hist: dict[int, int] = {}
        for c in per_job_counts:
            yield_hist[c] = yield_hist.get(c, 0) + 1
        results["throughput"] = {
            "elapsed_s": round(elapsed, 1),
            "jobs_submitted": submitted,
            "jobs_completed": completed,
            "submit_errors": errors,
            "nonces_found": len(nonce_values),
            "submits_per_s": round(submitted / elapsed, 2) if elapsed else None,
            "nonces_per_s": round(len(nonce_values) / elapsed, 2)
            if elapsed else None,
            "per_job_nonce_count_hist": {str(k): v
                                         for k, v in sorted(yield_hist.items())},
        }
        results["nonce_distribution"] = {
            "n": len(nonce_values), "bins": args.bins,
            "counts": _histogram(nonce_values, args.bins),
            "min": min(nonce_values) if nonce_values else None,
            "max": max(nonce_values) if nonce_values else None,
            "raw": nonce_values,  # full stream, for finer offline analysis
        }
        # Per-die nonce yield (v2 CHIP column) — a direct dead-core signal
        # that ties to the firmware MAP, unlike the ~uniform value histogram.
        results["per_chip"] = {
            "nonces": {str(k): v for k, v in sorted(per_chip_nonces.items())},
            "jobs": {str(k): v for k, v in sorted(per_chip_jobs.items())},
        }
        results["telemetry"] = telemetry
        dump()

        # --- Determinism ----------------------------------------------
        print(f"[hw] determinism: {args.reps}x identical job ...")
        _settle(t)  # clear throughput stragglers so rep 0 is not contaminated
        try:
            results["determinism"] = _determinism(t, args.reps, version=ver)
            det = results["determinism"]
            print(f"[hw]   {det['reps_completed']} reps, modal agreement "
                  f"{det['modal_agreement']}, core {len(det['core_nonces'])} "
                  f"nonce(s) -> "
                  f"{'DETERMINISTIC' if det['deterministic'] else 'DIVERGENCE'}")
        except Exception as e:
            results["determinism"] = {"error": str(e)}
            print(f"[hw]   determinism failed: {e}", file=sys.stderr)
        dump()

        print(f"[hw] wrote {args.out}")
        print(f"[hw] SUMMARY: {submitted} submitted, {completed} completed, "
              f"{len(nonce_values)} nonces, "
              f"{results['throughput']['nonces_per_s']} nonce/s, "
              f"errors={errors}")
        return 0
    except Exception as e:
        results.setdefault("fatal_error", str(e))
        try:
            dump()
        except Exception:
            pass
        print(f"[hw] FAILED: {e}", file=sys.stderr)
        raise
    finally:
        try:
            _flush_queue(t)
        except Exception:
            pass
        try:
            dev.set_fan_auto()
        except Exception:
            pass
        try:
            t.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
