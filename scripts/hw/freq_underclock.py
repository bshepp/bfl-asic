#!/usr/bin/env python3
"""OPT-IN, SUPERVISED safe-underclock confirmation for ZVX/ZKX.

Proves the frequency lever works with zero risk: it sets a SLOWER
firmware word (an underclock; the firmware's own slow-hover range),
confirms the census FREQUENCY drops and the chip still computes
deterministically, and leaves you to power-cycle to restore the default.

It only ever sets a word from the firmware's known-good table, and only
in the slow direction by default. Restore is a power cycle (ZKX can't
read the factor back). Excluded from pytest.

Usage:  python scripts/hw/freq_underclock.py --port COM3 --word 0xFFFF
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from collections import Counter

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


def _flush(t):
    ser = getattr(t, "_serial", None)
    if ser is not None:
        try:
            ser.reset_input_buffer()
        except Exception:
            pass


def _read_block(t, maxlines=120):
    raw = b""
    for _ in range(maxlines):
        line = t.readline()
        raw += line
        if line.strip() in (b"OK", b"SUCCESS") or not line:
            break
    return raw


def _determinism(t, reps=12, per_timeout=5.0):
    """Fraction of reps whose identical-job nonce set differs from consensus."""
    from bfl_asic.protocol.queued import (
        build_queue_job, build_queue_results, build_queue_flush,
        parse_queue_results)
    mid = bytes((i * 37 + 11) & 0xFF for i in range(32))
    tail = bytes((i * 53 + 7) & 0xFF for i in range(12))

    def one():
        _flush(t)
        t.write(build_queue_flush())
        t.readline()
        _flush(t)
        while True:  # drain any leftovers
            _flush(t)
            t.write(build_queue_results())
            if not parse_queue_results(_read_block(t)):
                break
        _flush(t)
        t.write(build_queue_job(mid, tail))
        t.readline()
        got = []
        deadline = time.monotonic() + per_timeout
        while time.monotonic() < deadline:
            _flush(t)
            t.write(build_queue_results())
            res = parse_queue_results(_read_block(t))
            if res:
                for r in res:
                    got.extend(r.nonces)
                break
            time.sleep(0.15)
        return tuple(sorted(got))

    one()  # discarded warm-up
    sets = [one() for _ in range(reps)]
    consensus, _ = Counter(sets).most_common(1)[0]
    err = sum(1 for s in sets if s != consensus) / reps if reps else 0.0
    return err, len(consensus)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Supervised safe-underclock confirmation (opt-in).")
    ap.add_argument("--port", default="COM3")
    ap.add_argument("--word", default="0xFFFF",
                    help="Firmware frequency word to set (default 0xFFFF, a "
                         "slow/underclock word). Must be in the firmware table.")
    args = ap.parse_args()
    word = int(args.word, 0)

    from bfl_asic.transport.serial import SerialTransport
    from bfl_asic.device import BFLDevice
    from bfl_asic.protocol.freq import ASIC_FREQUENCY_WORDS, is_known_word

    if not is_known_word(word):
        print(f"[hw] REFUSING: {word:#06x} is not a firmware word "
              f"{[hex(w) for w in ASIC_FREQUENCY_WORDS]}", file=sys.stderr)
        return 3
    slowest, fastest = ASIC_FREQUENCY_WORDS[0], ASIC_FREQUENCY_WORDS[-1]

    t = SerialTransport(port=args.port)
    t.open()
    try:
        dev = BFLDevice(t)
        print(f"[hw] {dev.identify().model}")

        f0 = dev.get_details().frequency_mhz
        print(f"[hw] BASELINE census frequency: {f0} MHz")
        e0, n0 = _determinism(t)
        print(f"[hw] BASELINE determinism: err={e0:.3f} ({n0} nonces/rep)")

        print(f"[hw] setting frequency word {word:#06x} (underclock) ...")
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ok = dev.set_freq_factor(word)
        print(f"[hw] ZVX ack: {ok}")
        time.sleep(2.0)

        # Sample the measured frequency a few times (the firmware measures
        # the real clock; thermal hover may also move it).
        freqs = []
        for _ in range(5):
            freqs.append(dev.get_details().frequency_mhz)
            time.sleep(1.0)
        print(f"[hw] AFTER-set census frequency samples: {freqs} MHz")
        e1, n1 = _determinism(t)
        print(f"[hw] AFTER determinism: err={e1:.3f} ({n1} nonces/rep)")

        dropped = any(f is not None and f0 is not None and f < f0
                      for f in freqs)
        print("[hw] ---")
        print(f"[hw] RESULT: frequency {'DROPPED (underclock took effect)' if dropped else 'did NOT drop (firmware may override ZVX via thermal hover)'};"
              f" compute {'stayed correct (err 0)' if e1 == 0 else 'showed errors!'}")
        print(f"[hw] Both determinism errs: baseline {e0:.3f}, underclock {e1:.3f}")
        print("[hw] NEXT: power-cycle the device to restore the default clock.")
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
