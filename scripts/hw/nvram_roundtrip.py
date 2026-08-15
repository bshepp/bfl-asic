#!/usr/bin/env python3
"""OPT-IN, GUARDED ZSX/ZUX NVRAM round-trip + persistence test.

Purpose: find out what the undocumented ZSX (SAVESTR) / ZUX (LOADSTR)
scratch buffer actually is, and whether it survives a power cycle. This
is the ONE probe command that WRITES persistent on-device state, so it is
gated behind an explicit --confirm-nvram-write flag and split into two
phases around a manual power cycle.

Phase 1 (write):
    python scripts/hw/nvram_roundtrip.py --port COM3 \
        --write "BFL-NVRAM-TEST-001" --confirm-nvram-write
  Reads the current scratch value, writes the marker, reads it back
  immediately to confirm the write took, and prints power-cycle
  instructions.

Phase 2 (verify persistence), AFTER unplugging/replugging the device:
    python scripts/hw/nvram_roundtrip.py --port COM3 \
        --verify "BFL-NVRAM-TEST-001"
  Reads the scratch value and reports whether the marker survived the
  power cycle (persistent NVRAM) or was lost (volatile).

Excluded from pytest. Restores nothing dangerous; ZSX only writes a short
ASCII marker you choose.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Guarded ZSX/ZUX NVRAM round-trip + persistence test "
                    "(opt-in; not run in CI).")
    ap.add_argument("--port", default="COM3")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", metavar="MARKER",
                   help="Write MARKER to NVRAM (needs --confirm-nvram-write).")
    g.add_argument("--verify", metavar="MARKER",
                   help="Read NVRAM and report whether MARKER persisted.")
    g.add_argument("--read", action="store_true",
                   help="Just read and print the current scratch value.")
    ap.add_argument("--confirm-nvram-write", action="store_true",
                    help="Required to actually write NVRAM via ZSX.")
    args = ap.parse_args()

    from bfl_asic.transport.serial import SerialTransport
    from bfl_asic.device import BFLDevice

    t = SerialTransport(port=args.port)
    t.open()
    try:
        dev = BFLDevice(t)
        print(f"[hw] {dev.identify().model}")

        current = dev.read_note()
        print(f"[hw] current scratch: {current!r}"
              + ("  (empty)" if current == "" else ""))

        if args.read:
            return 0

        if args.verify is not None:
            persisted = (current == args.verify)
            print(f"[hw] expected marker: {args.verify!r}")
            print(f"[hw] PERSISTENCE: {'CONFIRMED (survived power cycle)' if persisted else 'NOT persisted (volatile or not written)'}")
            return 0 if persisted else 2

        # --write path
        if not args.confirm_nvram_write:
            print("[hw] REFUSING to write NVRAM without --confirm-nvram-write",
                  file=sys.stderr)
            return 3
        print(f"[hw] writing marker {args.write!r} via ZSX ...")
        ok = dev.write_note(args.write)
        readback = dev.read_note()
        print(f"[hw] write ack={ok}; immediate read-back: {readback!r}")
        if readback == args.write:
            print("[hw] IMMEDIATE WRITE: CONFIRMED")
        else:
            print("[hw] IMMEDIATE WRITE: read-back does not match marker "
                  "(unexpected ZSX/ZUX semantics)")
        print("[hw] ---")
        print("[hw] NEXT: power-cycle the device (unplug USB + power, wait a")
        print("[hw]       few seconds, replug), then run:")
        print(f"[hw]       python scripts/hw/nvram_roundtrip.py --port "
              f"{args.port} --verify {args.write!r}")
        return 0
    except Exception as e:
        print(f"[hw] FAILED: {e}", file=sys.stderr)
        raise
    finally:
        try:
            t.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
