#!/usr/bin/env python3
"""OPT-IN, SUPERVISED error-rate-vs-temperature sweep. HARDWARE-DANGEROUS.

This deliberately LOWERS the fan while the ASIC hashes to raise its
temperature, then measures the hardware error rate as a function of
temperature. Reducing cooling on a running miner can physically damage
it, so this must ONLY be run with a human watching and ready to pull
power. It is NOT part of any unattended run.

Safety design (all always-on):
  * Requires --i-am-supervising to run at all.
  * Hard temperature ceiling (--max-temp, default 65 C) checked on EVERY
    loop iteration; crossing it aborts instantly and restores fan AUTO.
  * Fan is restored to firmware AUTO on normal exit, exception, Ctrl-C,
    and ceiling-abort (finally block).
  * The fan steps DOWN one level at a time (never straight to off), and
    each level dwells only until the temperature plateaus or --dwell
    seconds elapse.

Error metric is model-free: at each sample, one fixed work unit is
submitted `--reps` times and the fraction of reps whose returned nonce
set differs from the consensus (modal) set is the error rate. 0.0 means
the silicon is computing correctly at that temperature.

Usage (example, conservative):
    python scripts/hw/temp_sweep.py --port COM3 --i-am-supervising \
        --max-temp 65 --out docs/characterization/temp_sweep.json

Excluded from pytest.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

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


def _submit(t, mid, tail) -> bytes:
    from bfl_asic.protocol.queued import build_queue_job
    _flush(t)
    t.write(build_queue_job(mid, tail))
    return t.readline().strip()


def _drain(t) -> list:
    from bfl_asic.protocol.queued import build_queue_results, parse_queue_results
    _flush(t)
    t.write(build_queue_results())
    return parse_queue_results(_read_block(t))


def _flush_queue(t) -> None:
    from bfl_asic.protocol.queued import build_queue_flush
    _flush(t)
    t.write(build_queue_flush())
    t.readline()


def _settle(t, quiet_needed: int = 3, max_iter: int = 60) -> None:
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


def _one_rep(t, mid, tail, per_timeout: float = 5.0) -> tuple[int, ...]:
    _flush_queue(t)
    while _drain(t):
        pass
    ack = _submit(t, mid, tail)
    got: list[int] = []
    if b"ERR:" not in ack:
        deadline = time.monotonic() + per_timeout
        while time.monotonic() < deadline:
            res = _drain(t)
            if res:
                for r in res:
                    got.extend(r.nonces)
                break
            time.sleep(0.15)
    return tuple(sorted(got))


def _error_rate(t, reps: int) -> tuple[float, list[list[int]]]:
    """Fraction of reps whose nonce set differs from the modal set."""
    mid, tail = _fixed_work()
    _one_rep(t, mid, tail)  # discarded warm-up
    sets = [_one_rep(t, mid, tail) for _ in range(reps)]
    consensus, _ = Counter(sets).most_common(1)[0]
    errors = sum(1 for s in sets if s != consensus)
    distinct = sorted({s for s in sets})
    return errors / reps if reps else 0.0, [list(x) for x in distinct]


def _temp(dev) -> float:
    return max(dev.get_temperature().sensors)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Supervised error-rate-vs-temperature sweep "
                    "(HARDWARE-DANGEROUS; opt-in; not run in CI).")
    ap.add_argument("--port", default="COM3")
    ap.add_argument("--i-am-supervising", action="store_true",
                    help="Required. Confirms a human is watching the device.")
    ap.add_argument("--max-temp", type=float, default=65.0,
                    help="Hard ceiling in C; crossing it aborts (default 65).")
    ap.add_argument("--start-fan", type=int, default=3,
                    help="Fan level to start at (0..4, default 3).")
    ap.add_argument("--min-fan", type=int, default=0,
                    help="Lowest fan level to step down to (default 0).")
    ap.add_argument("--dwell", type=float, default=120.0,
                    help="Max seconds per fan level (default 120).")
    ap.add_argument("--reps", type=int, default=16,
                    help="Determinism reps per error sample (default 16).")
    ap.add_argument("--probe-interval", type=float, default=20.0,
                    help="Seconds between error samples within a level.")
    ap.add_argument("--out", default="docs/characterization/temp_sweep.json")
    args = ap.parse_args()

    if not args.i_am_supervising:
        print("[hw] REFUSING: --i-am-supervising is required. This sweep "
              "reduces cooling on a running ASIC and must be watched.",
              file=sys.stderr)
        return 3
    if not (0 <= args.min_fan <= args.start_fan <= 4):
        print("[hw] invalid fan range (need 0 <= min-fan <= start-fan <= 4)",
              file=sys.stderr)
        return 3

    from bfl_asic.transport.serial import SerialTransport
    from bfl_asic.device import BFLDevice

    t = SerialTransport(port=args.port)
    t.open()
    dev = BFLDevice(t)

    results: dict = {"meta": {
        "port": args.port, "max_temp_c": args.max_temp,
        "start_fan": args.start_fan, "min_fan": args.min_fan,
        "reps": args.reps, "started_utc": datetime.now(timezone.utc).isoformat(),
    }, "samples": []}
    aborted = None

    def dump() -> None:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

    def guard(temp: float) -> bool:
        """True if we must abort (ceiling crossed)."""
        if temp >= args.max_temp:
            nonlocal aborted
            aborted = f"temperature {temp:.1f}C >= ceiling {args.max_temp}C"
            return True
        return False

    def work_stream():
        i = 0
        while True:
            i += 1
            s = i.to_bytes(4, "big")
            yield (s * 8, s * 3)

    try:
        info = dev.identify()
        results["meta"]["device"] = info.model
        print(f"[hw] {info.model}")
        t0 = _temp(dev)
        print(f"[hw] start temp {t0:.1f}C, ceiling {args.max_temp}C. "
              f"Fan {args.start_fan} -> {args.min_fan}. WATCH THE DEVICE.")
        if guard(t0):
            print(f"[hw] already at/over ceiling; aborting.", file=sys.stderr)
            return 2

        wk = work_stream()
        in_flight = 0
        for lvl in range(args.start_fan, args.min_fan - 1, -1):
            print(f"[hw] --- fan level {lvl} ---")
            dev.set_fan(lvl)  # emits ThermalSafetyWarning
            level_start = time.monotonic()
            next_probe = 0.0
            last_temp = None
            stable = 0
            while time.monotonic() - level_start < args.dwell:
                # Heat: keep the pipeline busy.
                while in_flight < INFLIGHT_CAP:
                    ack = _submit(t, *next(wk))
                    if b"ERR:" in ack:
                        break
                    in_flight += 1
                for _ in _drain(t):
                    in_flight = max(0, in_flight - 1)
                # Guard on EVERY iteration.
                temp = _temp(dev)
                if guard(temp):
                    break
                # Periodic error sample.
                if time.monotonic() - level_start >= next_probe:
                    _settle(t)
                    in_flight = 0
                    err, distinct = _error_rate(t, args.reps)
                    d = dev.get_details()
                    ts = _temp(dev)
                    if guard(ts):
                        break
                    sample = {
                        "fan": lvl, "temp_c": ts, "error_rate": err,
                        "engines": d.engines, "mining_speed": d.mining_speed,
                        "freq_mhz": d.frequency_mhz,
                        "distinct_sets": distinct if err > 0 else None,
                    }
                    results["samples"].append(sample)
                    dump()
                    flag = "  <-- ERRORS" if err > 0 else ""
                    print(f"[hw]   temp={ts:4.1f}C fan={lvl} "
                          f"err={err:.3f} eng={d.engines} "
                          f"mining={d.mining_speed}{flag}")
                    next_probe += args.probe_interval
                    if last_temp is not None and abs(ts - last_temp) < 1.0:
                        stable += 1
                    else:
                        stable = 0
                    last_temp = ts
                    if stable >= 2:
                        print(f"[hw]   temp plateaued at {ts:.1f}C, "
                              f"next fan level")
                        break
            if aborted:
                break
        return 0
    except KeyboardInterrupt:
        aborted = "operator interrupt (Ctrl-C)"
        return 130
    except Exception as e:
        results.setdefault("fatal_error", str(e))
        print(f"[hw] FAILED: {e}", file=sys.stderr)
        raise
    finally:
        # ALWAYS restore firmware thermal management first.
        try:
            dev.set_fan_auto()
            print("[hw] fan restored to AUTO")
        except Exception:
            pass
        if aborted:
            results.setdefault("aborted", aborted)
            print(f"[hw] ABORTED: {aborted}", file=sys.stderr)
        try:
            _flush_queue(t)
        except Exception:
            pass
        try:
            dump()
        except Exception:
            pass
        try:
            t.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
