# Hardware experiments (`scripts/hw/`)

Opt-in scripts that talk to a real BFL Jalapeno over serial. None run in
CI. Run them with the project's interpreter (the one that has `bfl_asic`
editable-installed + `pyserial`), and use forward slashes in a bash `!`
line:

```
C:/Python313/python.exe scripts/hw/<script>.py --port COM3
```

Each script self-bootstraps the repo root onto `sys.path`, so an editable
install is not strictly required.

## Physical interface

The reference rig chains the Jalapeno's FTDI (FT232H, 115200 8N1) behind
a **4-port USB isolator based on the Analog Devices ADuM3160**:

```
host USB 3.0 port -> ADuM3160 isolator (upstream) -> isolated, shielded
USB 2.0 downstream -> Jalapeno
```

> **The Jalapeno does not work plugged directly into USB 3.0.** It has to
> sit behind the isolator's full-speed USB 2.0 downstream (a plain USB 2.0
> hub/port works too). The isolator's *upstream* on the 3.0 port is fine —
> it presents a clean full-speed link the device is happy with; a bare
> Jalapeno on an xHCI 3.0 jack is not. If `bfl-asic discover` finds
> nothing, check this first.

The ADuM3160 is a Full/Low-speed isolator, so the USB link runs at
**USB Full Speed (12 Mbps)** — still far above the 115200-baud serial, so
it does not bound the ~1.2 jobs/s throughput (serial baud + per-command
round-trip latency do). The isolator provides **2.5 kV signal / 1.5 kV
voltage galvanic isolation** from an onboard 2W 5V regulated supply,
protecting the host from the miner's 12V power domain — worth having in
place before poking at undocumented commands.

## Safety tiers

| Script | Writes device state? | Cooling | Supervision |
|--------|----------------------|---------|-------------|
| `read_details.py` | no (read-only) | auto | none needed |
| `probe_commands.py` | no (ZJX/ZUX reads only) | auto | none needed |
| `characterize.py` | no (queued work only) | **auto (forced)** | unattended OK |
| `nvram_roundtrip.py` | **yes — ZSX NVRAM write** | auto | attend the write |
| `temp_sweep.py` | no | **REDUCES cooling** | **REQUIRED — watch it** |

The two guarded scripts (`nvram_roundtrip`, `temp_sweep`) refuse to do
their risky action without an explicit flag.

## read_details.py — ZCX census (read-only)

Dumps the full device census and flags any undocumented fields.

```
C:/Python313/python.exe scripts/hw/read_details.py --port COM3
```

## probe_commands.py — ZJX/ZUX probes (read-only)

Fires the undocumented `ZJX` (firmware) and `ZUX` (load-string) reads and
prints raw replies. Never sends `ZSX`. On firmware 1.0.0: `ZJX` → bare
`1.0.0`; `ZUX` → `MEMORY EMPTY` for a blank scratchpad.

## characterize.py — model-free characterization (fan AUTO)

Sustained queued work with the fan forced to firmware AUTO. Measures
throughput, per-job winner-count distribution, a nonce-value histogram,
determinism (identical work → identical nonces), and telemetry over time.
Safe to run unattended (the device mined for days on auto fan). See
[`characterization/README.md`](characterization/README.md) for the
2026-08-15 baseline run.

```
# quick
C:/Python313/python.exe scripts/hw/characterize.py --port COM3 --duration 900

# long engine-mapping run (finer histogram; hours). Winners arrive at
# ~1.2/s, so ~50k nonces for a 512-bin histogram is ~11 h.
C:/Python313/python.exe scripts/hw/characterize.py --port COM3 \
    --duration 39600 --bins 512 \
    --out docs/characterization/engine-map.json
```

Engine mapping is the open Phase-2 question: the 30-minute baseline
histogram was broadly uniform, so resolving the 26–27 engine / 2-processor
structure needs a much larger nonce sample and finer bins.

**Dead-core detection** on a run's histogram is a shipped feature (no
hardware needed to analyze):

```
bfl-asic device health --from-run docs/characterization/engine-map.json
# or demonstrate detection on synthetic data:
bfl-asic device health --demo --inject-dead 0.3:0.4 --engines 27
```

It flags cold (under-represented) nonce bands as suspected dead engines.
It localizes them only if engines cover contiguous ranges; see
[`characterization/README.md`](characterization/README.md).

## nvram_roundtrip.py — ZSX/ZUX persistence (GUARDED write)

Finds out what the `ZSX`/`ZUX` scratch buffer is and whether it survives a
power cycle. `ZSX` writes persistent on-device state, so the write is
gated behind `--confirm-nvram-write` and split around a manual power
cycle.

```
# Phase 1 — write a marker (attend this), read it back immediately
C:/Python313/python.exe scripts/hw/nvram_roundtrip.py --port COM3 \
    --write "BFL-NVRAM-TEST-001" --confirm-nvram-write

# ... now physically power-cycle the device (unplug USB + power, replug) ...

# Phase 2 — did the marker survive?
C:/Python313/python.exe scripts/hw/nvram_roundtrip.py --port COM3 \
    --verify "BFL-NVRAM-TEST-001"
```

`--read` just prints the current scratch value without writing. A
persisted marker confirms the buffer is non-volatile; a lost marker means
it is volatile. Either result is a real finding.

**Result (2026-08-15): the scratchpad is non-volatile.** A marker written
with `ZSX` survived a full power cycle (USB + power removed and replugged)
and read back intact via `ZUX` — so this is a real persistent store
(EEPROM/flash on the controller), not RAM. Two firmware quirks worth
knowing: the `ZUX` reply has **no newline terminator and appends one
stray trailing byte** (so match by prefix, not exact equality), and
reading too soon after a command desyncs — the script flushes the input
buffer and settles ~0.3 s before each read. The write is genuinely
functional; an earlier "empty read-back" was purely a read-timing
artifact, since fixed.

## temp_sweep.py — error rate vs temperature (HARDWARE-DANGEROUS)

**Only run this with a human watching, ready to pull power.** It lowers
the fan while the ASIC hashes to raise temperature, and measures the
model-free hardware error rate (fraction of identical-work reps whose
nonce set diverges from consensus) as temperature climbs.

Always-on guards:

- Requires `--i-am-supervising`.
- Hard temperature ceiling (`--max-temp`, default 65 °C) checked on every
  loop iteration; crossing it aborts instantly.
- Fan restored to AUTO on normal exit, exception, Ctrl-C, and abort.
- Fan steps down one level at a time (never straight to off); each level
  dwells only until temperature plateaus or `--dwell` seconds.

```
C:/Python313/python.exe scripts/hw/temp_sweep.py --port COM3 \
    --i-am-supervising --max-temp 65 \
    --out docs/characterization/temp_sweep.json
```

Choosing `--max-temp`: the device idles ~36 °C and plateaus ~45 °C on auto
fan; the simulator's overheat model triggers at 85 °C. A first sweep
should stay conservative (≤ 65 °C) and be raised deliberately only if no
errors appear and the operator is comfortable pushing further. Errors are
expected to onset well above the 45 °C auto-fan plateau, so a too-low
ceiling may simply return an all-zero (inconclusive) curve — that is the
safe failure mode.
