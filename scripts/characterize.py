#!/usr/bin/env python3
"""Hardware characterization suite for the BFL Jalapeno.

Runs a series of increasing-intensity tests, logging temperature, voltage,
timing, and throughput at each stage.  Designed to be non-stressing — the
heaviest test is ~30 work units.

Usage:
    python scripts/characterize.py [--port COM3] [--output results.json]
    python scripts/characterize.py --simulate   # dry-run against simulator
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Ensure the package is importable when running from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bfl_asic.device import BFLDevice
from bfl_asic.exceptions import BFLError
from bfl_asic.protocol.work import build_synthetic_work
from bfl_asic.transport.simulator import SimulatorTransport


# -------------------------------------------------------------------
# Data classes for structured logging
# -------------------------------------------------------------------

@dataclass
class Reading:
    """A single temperature + voltage snapshot."""
    timestamp: str
    elapsed_s: float
    temps_c: list[float]
    vcc1_v: float | None = None
    vcc2_v: float | None = None
    vmain_v: float | None = None


@dataclass
class WorkEntry:
    """Timing and result for one work unit."""
    index: int
    submit_time_s: float
    result_time_s: float
    round_trip_ms: float
    status: str
    nonces_found: int


@dataclass
class TestResult:
    """Complete result for one characterization level."""
    level: int
    name: str
    description: str
    pre_reading: Reading | None = None
    post_reading: Reading | None = None
    work_entries: list[WorkEntry] = field(default_factory=list)
    total_work: int = 0
    total_nonces: int = 0
    duration_s: float = 0.0
    throughput_wps: float = 0.0
    mean_round_trip_ms: float = 0.0
    temp_delta_c: float = 0.0
    cooldown_s: float = 0.0
    error: str | None = None


@dataclass
class CharacterizationLog:
    """Top-level log for the entire characterization run."""
    start_time: str
    end_time: str = ""
    device_id: str = ""
    port: str = ""
    ambient_note: str = ""
    tests: list[TestResult] = field(default_factory=list)


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def take_reading(device: BFLDevice, t0: float) -> Reading:
    """Capture temperature and voltage from the device."""
    temp = device.get_temperature()
    try:
        volts = device.get_voltage()
        vcc1, vcc2, vmain = volts.vcc1, volts.vcc2, volts.vmain
    except Exception:
        vcc1 = vcc2 = vmain = None

    return Reading(
        timestamp=datetime.now(timezone.utc).isoformat(),
        elapsed_s=round(time.monotonic() - t0, 3),
        temps_c=temp.sensors,
        vcc1_v=round(vcc1, 3) if vcc1 is not None else None,
        vcc2_v=round(vcc2, 3) if vcc2 is not None else None,
        vmain_v=round(vmain, 3) if vmain is not None else None,
    )


def print_reading(label: str, r: Reading) -> None:
    temps = ", ".join(f"{t:.1f}C" for t in r.temps_c)
    volts = ""
    if r.vcc1_v is not None:
        volts = f"  VCC1={r.vcc1_v:.3f}V  VCC2={r.vcc2_v:.3f}V  VMAIN={r.vmain_v:.3f}V"
    print(f"  {label}: Temp=[{temps}]{volts}")


def recover_device(device: BFLDevice) -> bool:
    """Flush serial state and re-sync with the device.

    Flushes serial buffers, drains pending results, and re-identifies.
    Returns True if recovery succeeded.
    """
    transport = device.transport
    # Flush serial buffers if we have access to the underlying port
    if hasattr(transport, '_serial') and transport._serial is not None:
        transport._serial.reset_input_buffer()
        transport._serial.reset_output_buffer()

    time.sleep(1.0)

    # Drain any pending poll results
    try:
        for _ in range(5):
            result = device.poll_result()
            if result.status.value == "idle":
                break
            time.sleep(0.2)
    except Exception:
        pass

    try:
        info = device.identify()
        print(f"  [recovered] Device: {info.model}")
        return True
    except Exception as exc:
        print(f"  [recovery failed] {exc}")
        return False


def cooldown(device: BFLDevice, baseline_temp: float, t0: float,
             max_wait: float = 30.0, interval: float = 2.0) -> float:
    """Wait for temperature to drop back near baseline.  Returns seconds waited."""
    start = time.monotonic()
    while time.monotonic() - start < max_wait:
        r = take_reading(device, t0)
        avg = sum(r.temps_c) / len(r.temps_c)
        if avg <= baseline_temp + 1.0:
            break
        time.sleep(interval)
    return round(time.monotonic() - start, 2)


def submit_work_unit(device: BFLDevice, counter: int, t0: float,
                     retries: int = 2) -> WorkEntry:
    """Submit one synthetic work unit and return timing data.

    On empty-response errors, waits briefly and retries before raising.
    """
    seed = struct.pack(">Q", counter).ljust(64, b"\x00")
    midstate, tail = build_synthetic_work(seed)

    last_exc: Exception | None = None
    for attempt in range(1 + retries):
        if attempt > 0:
            time.sleep(0.5)  # brief pause before retry
        try:
            submit_t = time.monotonic()
            result = device.submit_and_wait(midstate, tail)
            result_t = time.monotonic()

            return WorkEntry(
                index=counter,
                submit_time_s=round(submit_t - t0, 3),
                result_time_s=round(result_t - t0, 3),
                round_trip_ms=round((result_t - submit_t) * 1000, 1),
                status=result.status.value,
                nonces_found=len(result.nonces),
            )
        except BFLError as exc:
            last_exc = exc
            if attempt < retries:
                print(f"  [retry {attempt+1}] {exc}")

    raise last_exc  # type: ignore[misc]


# -------------------------------------------------------------------
# Test levels
# -------------------------------------------------------------------

def run_level_0(device: BFLDevice, t0: float) -> TestResult:
    """Level 0: Idle baseline — 5 readings at 1-second intervals."""
    tr = TestResult(level=0, name="idle_baseline",
                    description="5 temperature/voltage readings at idle, 1s apart")
    print("\n--- Level 0: Idle Baseline ---")

    readings: list[Reading] = []
    for i in range(5):
        r = take_reading(device, t0)
        readings.append(r)
        print_reading(f"Reading {i+1}/5", r)
        if i < 4:
            time.sleep(1.0)

    tr.pre_reading = readings[0]
    tr.post_reading = readings[-1]
    tr.duration_s = round(readings[-1].elapsed_s - readings[0].elapsed_s, 2)
    tr.temp_delta_c = round(readings[-1].temps_c[0] - readings[0].temps_c[0], 1)
    print(f"  Idle temp drift: {tr.temp_delta_c:+.1f}C over {tr.duration_s:.1f}s")
    return tr


def run_work_level(device: BFLDevice, t0: float, level: int, name: str,
                   desc: str, count: int, pause: float = 0.0,
                   mid_read_every: int = 0) -> TestResult:
    """Generic work-submission test level.

    Parameters
    ----------
    mid_read_every:
        Take a mid-test temperature reading every N work units (0 = off).
    """
    tr = TestResult(level=level, name=name, description=desc)
    print(f"\n--- Level {level}: {name} ({count} work units, pause={pause}s) ---")

    tr.pre_reading = take_reading(device, t0)
    print_reading("Pre", tr.pre_reading)

    start = time.monotonic()
    counter_base = level * 1000  # offset to avoid seed collisions between levels

    try:
        for i in range(count):
            entry = submit_work_unit(device, counter_base + i, t0)
            tr.work_entries.append(entry)
            tr.total_nonces += entry.nonces_found
            if (i + 1) % max(1, count // 5) == 0 or i == count - 1:
                # Progress line with inline temp check for longer tests
                msg = (f"  Work {i+1}/{count}: {entry.round_trip_ms:.0f}ms  "
                       f"status={entry.status}  nonces={entry.nonces_found}")
                if mid_read_every > 0 and (i + 1) % mid_read_every == 0:
                    mid = take_reading(device, t0)
                    msg += f"  temp={mid.temps_c[0]:.0f}C"
                print(msg)
            if pause > 0 and i < count - 1:
                time.sleep(pause)
    except BFLError as exc:
        tr.error = str(exc)
        print(f"  ERROR: {exc}")
        recover_device(device)

    elapsed = time.monotonic() - start
    tr.total_work = len(tr.work_entries)
    tr.duration_s = round(elapsed, 2)
    tr.throughput_wps = round(tr.total_work / max(elapsed, 0.001), 2)

    if tr.work_entries:
        rts = [e.round_trip_ms for e in tr.work_entries]
        tr.mean_round_trip_ms = round(sum(rts) / len(rts), 1)

    try:
        tr.post_reading = take_reading(device, t0)
    except Exception:
        # If device is still unresponsive, use a placeholder
        tr.post_reading = Reading(
            timestamp=datetime.now(timezone.utc).isoformat(),
            elapsed_s=round(time.monotonic() - t0, 3),
            temps_c=tr.pre_reading.temps_c if tr.pre_reading else [0.0],
        )
    print_reading("Post", tr.post_reading)

    tr.temp_delta_c = round(
        tr.post_reading.temps_c[0] - tr.pre_reading.temps_c[0], 1)

    print(f"  Summary: {tr.total_work} units in {tr.duration_s:.1f}s "
          f"({tr.throughput_wps:.2f} wps), "
          f"mean RT={tr.mean_round_trip_ms:.0f}ms, "
          f"temp delta={tr.temp_delta_c:+.1f}C")

    return tr


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="BFL Jalapeno hardware characterization")
    parser.add_argument("--port", "-p", default=None,
                        help="Serial port (e.g. COM3)")
    parser.add_argument("--simulate", "-s", action="store_true",
                        help="Run against simulator instead of real hardware")
    parser.add_argument("--output", "-o", default=None,
                        help="Output JSON log file")
    args = parser.parse_args()

    # Build transport
    if args.simulate:
        from bfl_asic.transport.simulator import SimulatorTransport
        transport = SimulatorTransport()
        port_name = "simulator"
    else:
        if args.port is None:
            # Auto-discover
            from bfl_asic.transport.discovery import discover_devices
            devices = discover_devices()
            if not devices:
                print("ERROR: No BFL devices found. Use --port or --simulate.")
                sys.exit(1)
            args.port = devices[0].port
            print(f"Auto-discovered device on {args.port}")
        from bfl_asic.transport.serial import SerialTransport
        transport = SerialTransport(port=args.port)
        port_name = args.port

    log = CharacterizationLog(
        start_time=datetime.now(timezone.utc).isoformat(),
        port=port_name,
    )

    t0 = time.monotonic()

    with BFLDevice(transport) as device:
        # Identify
        info = device.identify()
        log.device_id = info.model
        print(f"Device: {info.model}")
        print(f"Port:   {port_name}")
        print(f"Time:   {log.start_time}")

        # --- Level 0: Idle baseline ---
        result0 = run_level_0(device, t0)
        log.tests.append(result0)
        baseline_temp = sum(result0.post_reading.temps_c) / len(result0.post_reading.temps_c)

        # --- Level 1: Single work unit ---
        result1 = run_work_level(device, t0, level=1, name="single_work",
                                 desc="1 work unit — measure baseline round-trip",
                                 count=1)
        log.tests.append(result1)
        cd = cooldown(device, baseline_temp, t0)
        result1.cooldown_s = cd
        print(f"  Cooldown: {cd:.1f}s")

        # --- Level 2: Light burst (5 units) ---
        result2 = run_work_level(device, t0, level=2, name="light_burst",
                                 desc="5 work units back-to-back — short burst",
                                 count=5)
        log.tests.append(result2)
        cd = cooldown(device, baseline_temp, t0)
        result2.cooldown_s = cd
        print(f"  Cooldown: {cd:.1f}s")

        # --- Level 3: Medium burst (15 units) ---
        result3 = run_work_level(device, t0, level=3, name="medium_burst",
                                 desc="15 work units back-to-back — medium load",
                                 count=15, mid_read_every=5)
        log.tests.append(result3)
        cd = cooldown(device, baseline_temp, t0)
        result3.cooldown_s = cd
        print(f"  Cooldown: {cd:.1f}s")

        # --- Level 4: Extended run (30 units, 100ms spacing) ---
        result4 = run_work_level(device, t0, level=4, name="extended_run",
                                 desc="30 work units with 100ms spacing — extended load",
                                 count=30, pause=0.1, mid_read_every=10)
        log.tests.append(result4)
        cd = cooldown(device, baseline_temp, t0)
        result4.cooldown_s = cd
        print(f"  Cooldown: {cd:.1f}s")
        recover_device(device)

        # --- Level 5: Sustained paced (20 units, 2s gaps) ---
        result5 = run_work_level(device, t0, level=5, name="sustained_paced",
                                 desc="20 work units with 2s pauses — steady state",
                                 count=20, pause=2.0, mid_read_every=5)
        log.tests.append(result5)
        cd = cooldown(device, baseline_temp, t0)
        result5.cooldown_s = cd
        print(f"  Cooldown: {cd:.1f}s")

        # --- Final idle reading ---
        print("\n--- Final Idle Reading ---")
        final = take_reading(device, t0)
        print_reading("Final", final)

    log.end_time = datetime.now(timezone.utc).isoformat()
    total_elapsed = time.monotonic() - t0

    # --- Summary ---
    print("\n" + "=" * 60)
    print("CHARACTERIZATION SUMMARY")
    print("=" * 60)
    print(f"Device:         {log.device_id}")
    print(f"Port:           {log.port}")
    print(f"Total duration: {total_elapsed:.1f}s")
    print(f"Tests run:      {len(log.tests)}")
    print()

    for t in log.tests:
        print(f"  Level {t.level} ({t.name}):")
        if t.total_work > 0:
            print(f"    Work units:    {t.total_work}")
            print(f"    Throughput:    {t.throughput_wps:.2f} units/s")
            print(f"    Mean RT:       {t.mean_round_trip_ms:.0f}ms")
        print(f"    Temp delta:    {t.temp_delta_c:+.1f}C")
        if t.cooldown_s > 0:
            print(f"    Cooldown:      {t.cooldown_s:.1f}s")
        if t.error:
            print(f"    ERROR:         {t.error}")
        print()

    # --- Save JSON log ---
    if args.output is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"characterize_{ts}.json"

    log_dict = asdict(log)
    Path(args.output).write_text(json.dumps(log_dict, indent=2))
    print(f"Full log saved to: {args.output}")


if __name__ == "__main__":
    main()
