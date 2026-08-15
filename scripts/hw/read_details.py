#!/usr/bin/env python3
"""OPT-IN, READ-ONLY hardware census: dump a real Jalapeno's ZCX reply.

Sends a single ZCX (details) query to a REAL BFL device and prints the
full parsed census plus the raw reply. This is strictly read-only: no
work is queued, no fan level is touched, no NVRAM is written -- safe to
run on the original unit. Excluded from pytest.

The interesting part is the *raw* block: cgminer's reference only ever
consumed a handful of fields, so a real unit may report labels nobody
documented. Anything the parser does not recognise is flagged.

Usage:  python scripts/hw/read_details.py --port COM3
"""
from __future__ import annotations

import argparse
import os
import sys

# Allow running as a bare script (`python scripts/hw/read_details.py`)
# without an editable install: put the repo root on sys.path so
# `import bfl_asic` resolves from the source tree.
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

_KNOWN = {
    "DEVICE", "FIRMWARE", "ENGINES", "FREQUENCY", "XLINK MODE",
    "XLINK PRESENT", "DEVICES IN CHAIN", "CHAIN PRESENCE MASK",
    "JOBS IN QUEUE",
}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Read-only ZCX census dump from a real BFL Jalapeno "
                    "(opt-in; not run in CI)."
    )
    ap.add_argument(
        "--port", default="COM3",
        help="Serial port of the Jalapeno (default: COM3).",
    )
    args = ap.parse_args()

    from bfl_asic.transport.serial import SerialTransport
    from bfl_asic.device import BFLDevice
    from bfl_asic.protocol.queued import build_details

    t = SerialTransport(port=args.port)
    t.open()
    try:
        dev = BFLDevice(t)
        info = dev.identify()
        print(f"[hw] {info.model}")

        # Raw reply first, so the undocumented-surface check sees exactly
        # what the wire produced.
        t.write(build_details())
        raw = b""
        for _ in range(32):
            line = t.readline()
            raw += line
            if line.strip() in (b"OK", b"SUCCESS") or not line:
                break

        from bfl_asic.protocol.queued import parse_details
        det = parse_details(raw)

        print("[hw] --- ZCX census ---")
        print(f"      Device:      {det.device}")
        print(f"      Firmware:    {det.firmware}")
        print(f"      Engines:     {det.engines}")
        print(f"      Frequency:   {det.frequency}")
        print(f"      X-Link:      mode={det.xlink_mode} "
              f"present={det.xlink_present}")
        print(f"      Chain:       devices={det.devices_in_chain} "
              f"mask={det.chain_presence_mask}")
        print(f"      Jobs queued: {det.jobs_in_queue}")

        extra = {
            k: v for k, v in det.fields.items()
            if k.lstrip("-").strip().upper() not in _KNOWN
        }
        if extra:
            print("[hw] undocumented fields (not in cgminer reference):")
            for k, v in extra.items():
                print(f"      {k}: {v}")
        else:
            print("[hw] no undocumented fields beyond the known census set")

        print("[hw] --- raw reply ---")
        sys.stdout.write(raw.decode("ascii", errors="replace"))
        if not raw.endswith(b"\n"):
            print()
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
