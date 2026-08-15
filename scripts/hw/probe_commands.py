#!/usr/bin/env python3
"""OPT-IN, READ-ONLY probe of the undocumented ZJX / ZUX commands.

cgminer defines ZJX (FIRMWARE), ZUX (LOADSTR) and ZSX (SAVESTR) but
never sends any of them, so their reply formats are unknown. This script
fires only the two READ commands (ZJX, ZUX) at a real device and dumps
the raw replies verbatim, turning guesses into ground truth.

It deliberately does NOT send ZSX (which writes device NVRAM). Safe on
the original unit. Excluded from pytest.

Usage:  python scripts/hw/probe_commands.py --port COM3
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


def _read_reply(t, max_lines: int = 48) -> bytes:
    """Read reply lines until OK/SUCCESS/ERR or a timeout (empty line)."""
    raw = b""
    for _ in range(max_lines):
        line = t.readline()
        raw += line
        s = line.strip()
        if not s or s in (b"OK", b"SUCCESS") or s.startswith(b"ERR:"):
            break
    return raw


def _dump(label: str, cmd: bytes, raw: bytes) -> None:
    print(f"[hw] --- {label} ({cmd.decode()}) ---")
    text = raw.decode("ascii", errors="replace")
    if not raw:
        print("      (no reply / timeout)")
    for line in text.splitlines():
        print(f"      | {line}")
    print(f"[hw] {label} raw bytes ({len(raw)}): {raw!r}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Read-only probe of undocumented ZJX/ZUX on a real "
                    "BFL Jalapeno (opt-in; not run in CI). Never sends ZSX.")
    ap.add_argument("--port", default="COM3",
                    help="Serial port of the Jalapeno (default: COM3).")
    args = ap.parse_args()

    from bfl_asic.transport.serial import SerialTransport
    from bfl_asic.device import BFLDevice
    from bfl_asic.protocol.probe import (
        build_firmware, build_loadstr, parse_firmware, parse_loadstr)

    t = SerialTransport(port=args.port)
    t.open()
    try:
        info = BFLDevice(t).identify()
        print(f"[hw] {info.model}")

        t.write(build_firmware())          # ZJX
        fw_raw = _read_reply(t)
        _dump("FIRMWARE", build_firmware(), fw_raw)
        fw = parse_firmware(fw_raw)
        if fw.fields:
            print(f"[hw] FIRMWARE parsed fields: {fw.fields}")

        t.write(build_loadstr())           # ZUX
        note_raw = _read_reply(t)
        _dump("LOADSTR", build_loadstr(), note_raw)
        print(f"[hw] LOADSTR stored string: {parse_loadstr(note_raw)!r}")

        print("[hw] (ZSX / SAVESTR intentionally NOT sent - it writes NVRAM)")
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
