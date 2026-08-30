"""Opt-in hardware driver for Icarus-protocol miners (Antminer U-series /
ASICMiner Block Erupter / GekkoScience BM1384) over a live serial port.

The deep, hardware-only counterpart to the library's simulator-backed tests --
mirrors how ``scripts/hw/characterize.py`` relates to the BFL device. Everything
here is a thin orchestration over already-tested primitives
(``bfl_asic.protocol.icarus``, ``IcarusSerialTransport``, ``characterize_source``).

Subcommands
-----------
  identify      golden-work self-test: is it alive and speaking Icarus?
  characterize  bounded sustained run -> throughput + linear-scan hashrate
  freq-sweep    Antminer U ANU clock control: set frequency and measure the
                hashrate response. UNDERCLOCK-ONLY by default (safe: cooler than
                stock, reversible); default 200 MHz is restored on exit.

Examples
--------
  python scripts/hw/icarus.py identify
  python scripts/hw/icarus.py characterize --duration 20
  python scripts/hw/icarus.py freq-sweep --targets 200,150,100

Port: auto-detected by CP210x VID/PID (0x10C4:0xEA60) unless --port is given;
the COM/tty number is not stable across replug, so prefer auto-detect.

SAFETY: an *overclock* (target above stock 200 MHz) is refused unless
--allow-overclock is passed, and the U1 has no serial temperature readout, so
overclocking needs external thermal monitoring. Underclocking is always safe.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

# Make the package importable when run from a checkout without installing.
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")))

from bfl_asic.characterization import characterize_source
from bfl_asic.nonce_source import IcarusNonceSource
from bfl_asic.protocol.icarus import (
    ANT_U1_DEFFREQ, GOLDEN_NONCE, GOLDEN_WORK, NONCE_SIZE, anu_freq_to_reg,
    anu_reg_to_freq, build_anu_read_freq, build_anu_set_freq, build_work,
    linear_scan_hashrate, parse_nonce,
)
from bfl_asic.transport.icarus_serial import IcarusSerialTransport

CP210X_VID = 0x10C4
CP210X_PID = 0xEA60
STOCK_MHZ = ANT_U1_DEFFREQ  # 200


def autodetect_port() -> str:
    from serial.tools import list_ports
    for p in list_ports.comports():
        if p.vid == CP210X_VID and p.pid == CP210X_PID:
            return p.device
    raise SystemExit(
        f"no CP210x Icarus device found (VID 0x{CP210X_VID:04X} "
        f"PID 0x{CP210X_PID:04X}); pass --port explicitly")


# --- shared helpers (thin, over tested primitives) ----------------------

def _golden_pair():
    return (GOLDEN_WORK[:32][::-1], GOLDEN_WORK[52:64][::-1])


def _set_freq(t, mhz):
    reg = anu_freq_to_reg(mhz)
    t.flush_input()
    t.write(build_anu_set_freq(reg=reg))
    time.sleep(0.3)          # let the PLL relock (mirrors cgminer's settle)
    t.flush_input()
    return reg


def _read_freq_reg(t):
    t.flush_input()
    t.write(build_anu_read_freq())
    return t.read(NONCE_SIZE, timeout=1.0)


def _measure_hashrate(t, seconds, read_timeout=5.0):
    pairs = []
    works = nonces = 0
    start = time.monotonic()
    while time.monotonic() - start < seconds:
        t.flush_input()
        w0 = time.monotonic()
        t.write(build_work(os.urandom(32), os.urandom(12)))
        raw = t.read(NONCE_SIZE, timeout=read_timeout)
        dt = time.monotonic() - w0
        works += 1
        if len(raw) == NONCE_SIZE:
            nonces += 1
            pairs.append((parse_nonce(raw), dt))
    hr = linear_scan_hashrate(pairs)
    return {"works": works, "nonces": nonces, "samples": len(pairs),
            "mhps": (hr / 1e6) if hr is not None else None}


# --- subcommands --------------------------------------------------------

def cmd_identify(t, _args):
    print("golden-work self-test ...", flush=True)
    src = IcarusNonceSource(t, work_iter=[_golden_pair()])
    res = list(src.results(count=1))
    nonces = res[0].nonces if res else []
    ok = nonces == [GOLDEN_NONCE]
    verdict = "ALIVE, speaks Icarus" if ok else "no/unexpected reply"
    print(f"  nonces={[hex(n) for n in nonces]}  "
          f"expected=[{hex(GOLDEN_NONCE)}]  -> {verdict}", flush=True)
    return 0 if ok else 1


def cmd_characterize(t, args):
    print(f"sustained run ({args.duration:.0f}s) ...", flush=True)
    src = IcarusNonceSource(t, work_iter=_rand_forever())
    report = characterize_source(src, duration=args.duration)
    tp, ex = report["throughput"], report["extras"]
    print(f"  works={tp['jobs_completed']} nonces={tp['nonces_found']} "
          f"works/s={tp['jobs_per_s']}", flush=True)
    print(f"  hashrate ~ {ex.get('hashrate_mhps')} MH/s "
          f"(samples={ex.get('samples')})", flush=True)
    print(f"  health: {report['health']['summary']}", flush=True)
    return 0


def cmd_freq_sweep(t, args):
    targets = [int(x) for x in args.targets.split(",")]
    over = [f for f in targets if f > STOCK_MHZ]
    if over and not args.allow_overclock:
        raise SystemExit(
            f"refusing overclock target(s) {over} MHz above stock {STOCK_MHZ} "
            f"MHz. Underclock is safe; to overclock pass --allow-overclock and "
            f"ensure EXTERNAL thermal monitoring (the U1 has no serial temp).")
    if over:
        print(f"!! OVERCLOCK ENABLED: {over} MHz above stock {STOCK_MHZ}. "
              f"Above-stock clocks raise heat/power; the U1 has no serial "
              f"temperature readout -- monitor temperature externally and stop "
              f"if hot.", flush=True)

    print("reg<->freq (host-side pre-flight):", flush=True)
    for f in targets:
        reg = anu_freq_to_reg(f)
        print(f"  {f:>4} MHz -> reg 0x{reg:04X} -> {anu_reg_to_freq(reg):.1f} MHz",
              flush=True)

    results = {}
    try:
        for f in targets:
            reg = _set_freq(t, f)
            rb = _read_freq_reg(t)
            m = _measure_hashrate(t, args.window)
            results[f] = m
            hr = f"{m['mhps']:.0f} MH/s" if m["mhps"] else "(no samples)"
            print(f"  set {f:>4} MHz (reg 0x{reg:04X}, rdreg={rb.hex() or '-'}): "
                  f"{hr:>12}  [{m['nonces']}/{m['works']} works]", flush=True)
    finally:
        _set_freq(t, args.restore)
        print(f"  restored {args.restore} MHz", flush=True)

    pts = [(f, results[f]["mhps"]) for f in targets if results[f]["mhps"]]
    if len(pts) >= 2:
        print("\nfreq -> hashrate (MH/s per MHz constant => clock moved):",
              flush=True)
        for f, hr in pts:
            print(f"  {f:>4} MHz : {hr:6.0f} MH/s  ({hr / f:5.2f} MH/s/MHz)",
                  flush=True)
    return 0


def _rand_forever():
    while True:
        yield (os.urandom(32), os.urandom(12))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default=None,
                    help="serial port (default: auto-detect CP210x)")
    ap.add_argument("--read-timeout", type=float, default=5.0,
                    help="default serial read timeout, seconds")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("identify", help="golden-work self-test")

    c = sub.add_parser("characterize", help="sustained throughput + hashrate")
    c.add_argument("--duration", type=float, default=20.0)

    s = sub.add_parser("freq-sweep", help="ANU clock control (underclock-safe)")
    s.add_argument("--targets", default="200,150,100",
                   help="comma-separated MHz targets (default underclock sweep)")
    s.add_argument("--window", type=float, default=15.0,
                   help="hashrate measurement window per target, seconds")
    s.add_argument("--restore", type=int, default=STOCK_MHZ,
                   help="frequency to restore on exit (default stock 200)")
    s.add_argument("--allow-overclock", action="store_true",
                   help="permit targets above stock (needs external thermal watch)")
    args = ap.parse_args(argv)

    port = args.port or autodetect_port()
    print(f"port: {port}", flush=True)
    t = IcarusSerialTransport(port, timeout=args.read_timeout)
    t.open()
    try:
        handler = {"identify": cmd_identify, "characterize": cmd_characterize,
                   "freq-sweep": cmd_freq_sweep}[args.cmd]
        return handler(t, args)
    finally:
        t.close()


if __name__ == "__main__":
    sys.exit(main())
