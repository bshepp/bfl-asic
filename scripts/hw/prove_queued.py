#!/usr/bin/env python3
"""OPT-IN hardware proof: the SC queued path defeats the 42-wall.

Run against a REAL Jalapeno (default COM3). Excluded from pytest.
Submits >42 jobs via QueuedWorkSession; the naive path stalls at 43,
this must not. Always flushes the queue and restores fan AUTO on exit,
including on exception.

Usage:  python scripts/hw/prove_queued.py --port COM3 --jobs 200
"""
from __future__ import annotations

import argparse
import sys
import time


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Prove the SC queued path defeats the 42-submission "
                    "wall on a real BFL Jalapeno (opt-in; not run in CI)."
    )
    ap.add_argument(
        "--port", default="COM3",
        help="Serial port of the Jalapeno (default: COM3).",
    )
    ap.add_argument(
        "--jobs", type=int, default=200,
        help="Queued jobs to submit; must exceed 42 to prove the wall "
             "is gone (default: 200).",
    )
    args = ap.parse_args()

    from bfl_asic.transport.serial import SerialTransport
    from bfl_asic.device import BFLDevice, QueuedWorkSession

    t = SerialTransport(port=args.port)
    t.open()
    try:
        # NOTE: BFLDevice is used WITHOUT its context manager on purpose.
        # BFLDevice.__exit__ closes the transport, which the queued
        # session below still needs; and re-opening via a second
        # __enter__ is not idempotent on all OS/driver combinations.
        info = BFLDevice(t).identify()
        print(f"[hw] {info.model}")

        n = 0
        with QueuedWorkSession(t) as s:
            def work():
                for i in range(args.jobs):
                    yield (bytes([i % 256]) * 32, bytes([i % 256]) * 12)

            t0 = time.monotonic()
            for _r in s.run(work_iter=work(), max_jobs=args.jobs):
                n += 1
            dt = time.monotonic() - t0

        ok = n >= args.jobs
        print(f"[hw] completed {n}/{args.jobs} queued jobs in {dt:.1f}s "
              f"-> {'PASS (42-wall defeated)' if ok else 'FAIL'}")
        return 0 if ok else 1
    except Exception as e:
        # Operator-legible failure line before the traceback.
        print(f"[hw] FAILED: {e}", file=sys.stderr)
        raise
    finally:
        # Safety: always clear the queue and restore firmware fan auto,
        # even on exception, and never let a flaky cleanup mask the
        # original error.
        try:
            from bfl_asic.protocol.queued import build_queue_flush
            t.write(build_queue_flush())
            t.readline()
        except Exception:
            pass
        try:
            BFLDevice(t).set_fan_auto()
        except Exception:
            pass
        try:
            t.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
