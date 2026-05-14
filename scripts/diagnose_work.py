#!/usr/bin/env python3
"""Diagnose work submission behavior on the real BFL device.

Tests whether the ASIC actually processes work by using the Bitcoin genesis
block (difficulty 1, known nonce 2083236893).  Polls aggressively to catch
BUSY→result transitions.

NOTE: The device must be power-cycled before running this if the 42-work
limit has been hit in a previous session.
"""

from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bfl_asic.device import BFLDevice
from bfl_asic.protocol.commands import build_work, build_poll
from bfl_asic.protocol.responses import parse_work_result
from bfl_asic.protocol.work import compute_midstate


# -------------------------------------------------------------------
# Bitcoin Genesis Block (Block #0)
# -------------------------------------------------------------------
# Layout: version(4) + prev_hash(32) + merkle_root(32) + time(4) + bits(4) + nonce(4)
GENESIS_HEADER = bytes.fromhex(
    "01000000"                                          # version
    "0000000000000000000000000000000000000000000000000000000000000000"  # prev_hash
    "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"  # merkle_root
    "29ab5f49"                                          # timestamp
    "ffff001d"                                          # bits (difficulty 1)
    "1dac2b7c"                                          # nonce (winning: 2083236893)
)

GENESIS_NONCE = 2083236893  # 0x7C2BAC1D big-endian, 0x1DAC2B7C little-endian
GENESIS_HASH = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"


def verify_genesis():
    """Verify our block header data produces the known genesis hash."""
    h1 = hashlib.sha256(GENESIS_HEADER).digest()
    h2 = hashlib.sha256(h1).digest()
    block_hash = h2[::-1].hex()  # reverse for display (Bitcoin convention)
    print(f"  Computed: {block_hash}")
    print(f"  Expected: {GENESIS_HASH}")
    assert block_hash == GENESIS_HASH, "Genesis block verification FAILED"
    print("  OK - Genesis block header verified\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Diagnose BFL work processing")
    parser.add_argument("--port", "-p", default=None)
    parser.add_argument("--simulate", "-s", action="store_true")
    args = parser.parse_args()

    # Build transport
    if args.simulate:
        from bfl_asic.transport.simulator import SimulatorTransport
        transport = SimulatorTransport()
    else:
        if args.port is None:
            from bfl_asic.transport.discovery import discover_devices
            devices = discover_devices()
            if not devices:
                print("ERROR: No devices found. Use --port or --simulate.")
                sys.exit(1)
            args.port = devices[0].port
        from bfl_asic.transport.serial import SerialTransport
        transport = SerialTransport(port=args.port)

    # -- Step 0: Verify genesis block locally --
    print("=== Step 0: Verify genesis block locally ===")
    verify_genesis()

    # -- Compute midstate and tail --
    first_64 = GENESIS_HEADER[:64]
    tail = GENESIS_HEADER[64:76]   # timestamp + bits (no nonce — ASIC scans those)
    nonce_bytes = GENESIS_HEADER[76:80]

    midstate = compute_midstate(first_64)
    print(f"=== Work Packet ===")
    print(f"  Midstate: {midstate.hex()}")
    print(f"  Tail:     {tail.hex()}")
    print(f"  Known nonce: {GENESIS_NONCE} (0x{GENESIS_NONCE:08x})")
    print(f"  Nonce bytes in header (LE): {nonce_bytes.hex()}")
    print()

    with BFLDevice(transport) as device:
        info = device.identify()
        print(f"Device: {info.model}")
        temp = device.get_temperature()
        print(f"Temp:   {temp.sensors}")
        print()

        # -- Test 1: Old format (raw delimiter packet, no ZDX) --
        print("=== Test 1: Old format (>>>>>>>>+midstate+tail+>>>>>>>>, no ZDX) ===")
        work_packet = build_work(midstate, tail)
        print(f"  Sending {len(work_packet)}-byte packet: {work_packet[:16].hex()}...")
        transport.write(work_packet)
        raw_ok = transport.readline()
        print(f"  Response: {raw_ok!r}")
        print(f"  (empty = readline timeout, device didn't accept it)")
        print()

        # -- Test 2: ZDX + delimiter-wrapped packet (60 bytes) --
        print("=== Test 2: ZDX + 60-byte delimiter-wrapped packet ===")
        transport.write(b"ZDX")
        raw_zdx = transport.readline(timeout=2.0)
        print(f"  ZDX response: {raw_zdx!r}")
        transport.write(work_packet)  # 60 bytes with delimiters
        raw_ok2 = transport.readline()
        print(f"  Work response: {raw_ok2!r}")
        print(f"  (ERR:INVALID DATA = wrong format after ZDX)")
        print()

        # -- Test 3: ZDX + raw 44 bytes (midstate + tail, NO delimiters) --
        # This is what cgminer actually sends!
        print("=== Test 3: ZDX + 44 raw bytes (cgminer format) ===")
        raw_work = midstate + tail  # 32 + 12 = 44 bytes
        print(f"  Sending ZDX...")
        transport.write(b"ZDX")
        raw_zdx = transport.readline(timeout=2.0)
        print(f"  ZDX response: {raw_zdx!r}")

        if b"OK" in raw_zdx:
            print(f"  Sending {len(raw_work)}-byte work data (midstate+tail)...")
            transport.write(raw_work)
            raw_ok3 = transport.readline(timeout=2.0)
            print(f"  Work response: {raw_ok3!r}")

            if b"OK" in raw_ok3:
                print("  Work ACCEPTED! Polling for result...")
                start = time.monotonic()
                for i in range(30):
                    transport.write(build_poll())
                    raw = transport.readline()
                    elapsed = time.monotonic() - start
                    decoded = raw.decode("ascii", errors="replace").strip()
                    print(f"  Poll {i+1:2d} @ {elapsed:.3f}s: {decoded!r}")
                    if b"NONCE" in raw:
                        nonce_hex = decoded.split(":")[-1].strip()
                        nonce_val = int(nonce_hex, 16)
                        print(f"\n  *** NONCE FOUND: {nonce_val} (0x{nonce_val:08x}) ***")
                        print(f"  *** Expected:    {GENESIS_NONCE} (0x{GENESIS_NONCE:08x}) ***")
                        print(f"  *** Match: {nonce_val == GENESIS_NONCE} ***")
                        break
                    if b"NO-NONCE" in raw:
                        print(f"\n  Work completed: NO-NONCE (nonce {GENESIS_NONCE} not found)")
                        break
                    if decoded == "IDLE" and elapsed > 2.0:
                        print(f"\n  Device went IDLE after {elapsed:.1f}s without result")
                        break
                    time.sleep(0.05)
            else:
                print(f"  Work REJECTED: {raw_ok3!r}")
        print()

        # -- Test 4: ZDX + 44 raw bytes with synthetic easy work --
        print("=== Test 4: ZDX + 44 bytes (all zeros - trivial difficulty) ===")
        zero_work = b"\x00" * 44
        transport.write(b"ZDX")
        raw_zdx = transport.readline(timeout=2.0)
        print(f"  ZDX response: {raw_zdx!r}")
        if b"OK" in raw_zdx:
            transport.write(zero_work)
            raw_ok4 = transport.readline(timeout=2.0)
            print(f"  Work response: {raw_ok4!r}")
            if b"OK" in raw_ok4:
                print("  Polling...")
                start = time.monotonic()
                for i in range(30):
                    transport.write(build_poll())
                    raw = transport.readline()
                    elapsed = time.monotonic() - start
                    decoded = raw.decode("ascii", errors="replace").strip()
                    print(f"  Poll {i+1:2d} @ {elapsed:.3f}s: {decoded!r}")
                    if b"NONCE" in raw or b"NO-NONCE" in raw or (decoded == "IDLE" and elapsed > 2.0):
                        break
                    time.sleep(0.05)
        print()

        # -- Final state --
        print("=== Final Device State ===")
        try:
            temp = device.get_temperature()
            print(f"  Temp: {temp.sensors}")
        except Exception as exc:
            print(f"  Temp error: {exc}")

        try:
            volts = device.get_voltage()
            print(f"  VCC1={volts.vcc1:.3f}V  VCC2={volts.vcc2:.3f}V  VMAIN={volts.vmain:.3f}V")
        except Exception as exc:
            print(f"  Voltage error: {exc}")


if __name__ == "__main__":
    main()
