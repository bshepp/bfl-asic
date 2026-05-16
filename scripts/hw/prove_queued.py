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
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM3")
    ap.add_argument("--jobs", type=int, default=200)
    args = ap.parse_args()

    from bfl_asic.transport.serial import SerialTransport
    from bfl_asic.device import BFLDevice, QueuedWorkSession

    t = SerialTransport(port=args.port)
    t.open()
    try:
        with BFLDevice(t) as dev:
            info = dev.identify()
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
    finally:
        # Safety: never leave the device queued or the fan in a fixed
        # level, even if the run above raised.
        try:
            from bfl_asic.protocol.queued import build_queue_flush
            t.write(build_queue_flush())
            t.readline()
        except Exception:
            pass
        try:
            with BFLDevice(t) as dev:
                dev.set_fan_auto()
        except Exception:
            pass
        t.close()


if __name__ == "__main__":
    sys.exit(main())
