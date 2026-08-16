# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Communication layer and analysis tools for the Butterfly Labs BF0005G Jalapeno SHA-256 ASIC miner. Provides protocol encoding/decoding, serial transport, device simulation, statistical analysis of hash output, iterated-hash dynamics research, and NIST SP 800-22 randomness validation.

## Common Commands

```bash
# Install (editable, with dev deps)
pip install -e ".[dev]"

# Install with optional ML subsystem (adds PyTorch)
pip install -e ".[ml]"

# Run all tests (848 total, ~65s, no hardware required; 846 pass in the fast suite — 2 slow ML training tests excluded by -m "not slow")
pytest

# Run a single test file
pytest tests/test_device.py

# Run a single test by name
pytest tests/test_device.py -k "test_identify"

# CLI entry point (installed via pip install -e .)
bfl-asic --help
bfl-asic --simulate identify
bfl-asic --port COM3 temperature
```

## Architecture

Four-layer design with strict separation of concerns:

**Protocol layer** (`bfl_asic/protocol/`) — Pure functions, no I/O. Builds command byte sequences (ZGX, ZLX, ZTX, ZDX, ZFX, ZPX; SC queued ZNX/ZWX/ZOX/ZQX/ZCX), parses responses into dataclasses, computes SHA-256 midstates. `queued.parse_details` turns the multi-line `ZCX` reply into a `DeviceDetails` census with typed, case-/dash-insensitive accessors (`firmware`, `engines`, `frequency`/`frequency_mhz`, `mining_speed`, `critical_temperature`, `processors` → `list[Processor]`, `jobs_in_queue`); unrecognised firmware fields are preserved verbatim in `.fields`. `protocol/probe.py` holds the undocumented probe commands `ZJX`/`ZUX`/`ZSX` (firmware / load-string / save-string) with lenient parsers. All protocol logic is independently testable.

**Transport layer** (`bfl_asic/transport/`) — I/O abstraction via `BaseTransport` ABC. `SerialTransport` wraps pyserial for real hardware (FTDI VID 0x0403, PID 0x6014, 115200 8N1). `SimulatorTransport` provides an in-process fake device with thermal model and real SHA-256d computation — all tests run against the simulator. Async methods default to `asyncio.to_thread()` wrapping of sync implementations.

**Device layer** (`bfl_asic/device.py`, `async_device.py`) — High-level API. `BFLDevice` (sync) and `AsyncBFLDevice` (async with stream iterators). Both are context managers that own transport lifecycle.

**Application layer** (independent subsystems):
- `bfl_asic/stats/` — SHA-256 statistical analysis: 7 numpy-vectorized accumulators, FFT spectral analysis, pipeline orchestrator, matplotlib visualization (including an animated bit-frequency convergence GIF for teaching the law of large numbers).
- `bfl_asic/dynamics/` — Iterated hash orbit/cycle analysis: Floyd's and Brent's cycle detection (O(1) memory), multi-seed convergence analysis.
- `bfl_asic/randomness/` — NIST SP 800-22 randomness test battery over any `HashSource`. Six tests as pure numpy functions: frequency (monobit), block frequency, runs, longest-run-in-block, DFT spectral, cumulative sums (forward + reverse). Designed to plug an ASIC-backed hash source in unchanged when one exists.
- `bfl_asic/cli.py` — Click-based CLI: top-level `characterize`, `report-issue`, `benchmark`, `probe`, `discover`, `identify`, `temperature`, `hash`, `fan`; groups `device details/firmware/note/health`, `stats`, `dynamics`, `randomness`, `ml`. When neither `--port` nor `--simulate` is given, `get_transport` **auto-detects** the connected FTDI device (falls back to the simulator with a note). `device note --write` is gated behind `--confirm-nvram-write` (`--verify TEXT` checks persistence); `device health` runs dead-core detection; `characterize` wraps `bfl_asic/characterization.py`; `report-issue` opens a prefilled GitHub issue URL.
- `bfl_asic/characterization.py` — library-level sustained-work characterization (throughput, nonce histogram, dead-core health), bounding in-flight jobs by submitted-minus-drained. `bfl_asic/transport/*.flush_input()` (no-op simulator, real serial buffer reset) is wired into all device read paths so the chatty firmware doesn't desync reads on hardware.
- `bfl_asic/health.py` — dead-core detection from the winning-nonce histogram. Pure functions (`nonce_histogram`, `detect_dead_cores`, `detect_dead_cores_from_counts` → `EngineHealthReport`): a dead engine that scans a contiguous nonce sub-range leaves a cold band; a per-bin Poisson test flags contiguous cold runs and estimates dead-engine count. **Only** localizes dead cores if engines cover contiguous ranges (else a dead engine thins the histogram uniformly — the yield rate is the signal). CLI: `device health --from-run <json>` or `--demo [--inject-dead LO:HI]`.
- `bfl_asic/nonce_source.py` — honest device nonce stream (`NonceSource`); wraps `QueuedWorkSession` for continuous drain via SC queued protocol. **Not** a `HashSource` — the device yields nonces (mining winners), not full digests.
- `BFLDevice.set_fan_auto()` / `BFLDevice.set_fan(level)` / `fan_fixed(level)` context manager — thermal-safety-guarded fan control; low fixed levels during hashing risk ASIC damage; `fan_fixed` restores `auto` on exit.
- `bfl_asic/ml/` — Optional ML learnability instrument (PyTorch behind the
  `[ml]` extra; lazy-imported by the CLI). Numpy-vectorized round-reduced
  SHA-256 (hashlib-anchored), distinguisher/orbit datasets, TinyCNN/
  LinearProbe, a deterministic train/eval harness with positive/negative
  controls, and a `ml` CLI group (`sweep`/`run`/`report`/`plot`/`publish`).
  The core install never requires torch; the default `pytest` fast run
  stays torch-optional (heavy training tests are marked `slow`).

## Key Conventions

- **Exception hierarchy**: All package exceptions inherit from `BFLError`. Subtypes: `BFLConnectionError`, `BFLProtocolError`, `BFLTimeoutError`, `BFLDeviceError`.
- **Protocol commands**: ASCII 3-byte codes. Work packets are 60 bytes (8-byte delimiter + 32-byte midstate + 12-byte tail + 8-byte delimiter). Responses delimited by `>>>>>>>>` (8 × 0x3E).
- **pytest-asyncio**: Configured with `asyncio_mode = "auto"` — async test functions are auto-detected.
- **Matplotlib**: Uses `Agg` backend (headless) for all visualization to avoid display dependencies.
- **CLI outputs**: Default writes go under `runs/<command>/<timestamp>/` (or a single timestamped filename for standalone artefacts). Explicit `-o` is honoured verbatim. The no-overwrite policy applies to every write path: collisions get a timestamp suffix. Root is configurable via `$BFL_ASIC_OUTPUT_DIR`. The `runs/` folder is gitignored.
- **Python ≥ 3.10** required.

## Hardware Notes

- **Physical interface (this rig):** normally host USB 3.0 port ->
  **4-port ADuM3160 USB isolator** (onboard 2W 5V regulated supply;
  2.5 kV signal / 1.5 kV voltage galvanic isolation) -> isolated shielded
  **USB 2.0** downstream -> Jalapeno FT232H. The reason to keep the
  isolator is the **galvanic isolation** (protects the host from the
  miner's 12V power domain), not USB speed. Link runs at USB Full Speed
  (12 Mbps) regardless, ~100x the 115200-baud serial, so the interface is
  NOT the serial-throughput limiter (~1.2 jobs/s is serial baud +
  round-trip latency).
- **Direct USB 3.0 is UNSTABLE for the bare device (tested 2026-08-15).**
  Plugged DIRECTLY into a host USB 3.0 (xHCI) jack the Jalapeno
  enumerates and works INITIALLY — identify, census, sustained work
  (0 errors, deterministic), and NVRAM all fine, and throughput while up
  is identical to the isolated path (**1.232 jobs/s direct vs 1.227
  isolated**). But it is **not reliable**: after several minutes on
  direct 3.0 the FTDI (`FTWLK8HJ`) was observed **faulting into Device
  Manager Code 10 "This device cannot start" (ProblemStatus 0xC0000001),
  the COM port vanishing** (`comports()` then returns nothing). The
  **isolated path** (host 3.0 -> ADuM3160 isolator -> USB 2.0 -> device)
  ran 4 h + 30 min with zero drops. So the isolator is **NOT optional**
  for reliable use here — it provides a stable, re-clocked full-speed
  link (plus clean power and galvanic isolation), not merely nice-to-have
  protection. This matches the operator's long-standing "doesn't work on
  USB 3.0" experience: it's intermittent instability, not immediate
  failure. Recovery from the Code 10 state: unplug/replug (into the
  isolator). [Earlier commits in this repo over-corrected to "USB 3.0
  works fine" after only a short direct test — that was premature.]

- The naive `ZDX`/`ZFX` work path stalls after **42 submissions per power
  cycle** — but this is an artifact of never draining the firmware queue,
  **not** a hardware limit (the device mined for days via cgminer without
  power-cycling). Use `QueuedWorkSession` (SC queued `ZNX`/`ZOX`/`ZCX`
  path) for sustained work; the naive path is left unchanged on purpose.
- Temperature/voltage commands were discovered to be **reversed** from initial protocol assumptions: ZLX reads temperature, ZTX reads voltage (not vice versa).
- VCC1 readings show anomalous ~1.2V drops after ZTX queries (suspected ADC settling time issue).
- The `ZCX` census reports **more than cgminer ever documented**. The real
  physical unit (firmware 1.0.0, captured 2026-08-15 via
  `scripts/hw/read_details.py`) returns: `ENGINES: 26`, a **real**
  `FREQUENCY: 189 MHz` (not the reference build's `[UNKNOWN]`),
  per-processor topology (`PROCESSOR 3: 12 engines @ 199 MHz`,
  `PROCESSOR 7: 14 engines @ 200 MHz` — sparse indices imply fused-off
  cores; 12+14 = 26 = ENGINES), a firmware-estimated `MINIG SPEED:
  5.15 GH/s` (the firmware's own typo for "MINING"), and `CRITICAL
  TEMPERATURE: 0`. Reported fields are firmware-build-dependent; the
  simulator emits the leaner cgminer-reference variant on purpose, and
  the parser handles both. The self-reported topology also **fluctuates
  live** between queries (26–27 engines, PROCESSOR 3 = 12–13 engines @
  198–199 MHz, MINIG SPEED 5.15–5.34 GH/s) — it is a live health readout,
  not a fixed spec.
- **Provenance / novelty (checked 2026-08-15):** these commands are NOT
  novel discoveries. `ZJX` (firmware) and `ZMX` (**Blink** — an LED
  identify; cgminer names it `BFLSC_FLASH`/`bflsc_flash_led` = "flash the
  LED", which is CORRECT — do NOT claim cgminer mislabels it; we initially
  misread the name as firmware-flash, there is no serial flash command)
  are in BFL's official 2012 protocol spec
  (`BitFORCE SC Communication Protocol Rev 1.0.0 DRAFT`). `ZSX`/`ZUX`
  (save/load string, the NVRAM scratchpad) and `ZVX`/`ZKX` (set/get
  frequency factor) are NOT in that published spec but ARE fully
  implemented in BFL's open-source firmware (`github.com/luke-jr/
  BitForce_SC`, e.g. `Protocol_save_string`/`load_string`, the literal
  `"MEMORY EMPTY\n"`). We re-derived them from hardware because the
  MINING software (cgminer) defines but never sends them. Frame all of
  this as re-derivation/confirmation, never discovery.
- Probe commands (what they do on real hardware): `ZJX` returns a bare
  firmware version (`1.0.0`, no framing); `ZUX` returns the NVRAM scratch
  string or `MEMORY EMPTY`; `ZSX` writes NVRAM (`SaveString` = length
  byte + payload), gated in the CLI. `ZVX`/`ZKX` (frequency factor) are
  the real lever for Phase 3 (set the clock). Implemented in the toolkit
  (`protocol/freq.py`, `BFLDevice.get_freq_factor`/`set_freq_factor`,
  guarded to the firmware's 10 known-good words). **Hardware status
  (2026-08-15): ZVX handshake SOLVED, but the firmware overrides the
  setting.** Root cause of the earlier `ERR:INVALID DATA` (found by
  reading `USB_wait_stream`): the double-stage payload is
  **length-prefixed** — first byte = data length, then the data. A bare 4
  bytes was read as "expect 255", never reached EOS -> invalid. Fixed:
  payload is now `[0x04][4 LE bytes]`; `ZVX` returns `OK` and
  `set_freq_factor` returns True. **BUT the clock does not change** — even
  the slowest word (0x0000) left the census at 189 MHz. So the setting is
  accepted but neutralized, most likely by the firmware's thermal-hover
  loop re-asserting its own frequency word (or the raw 0x60 write not
  reconfiguring the live PLL without a trigger the command doesn't issue).
  `ZKX` returns 0 (unimplemented). **Conclusion: the frequency sweep is
  NOT achievable via ZVX on this firmware** — controlling the clock would
  need to bypass/disable the firmware's own frequency management, which
  isn't exposed over serial. `scripts/hw/freq_underclock.py` is the probe. **The scratchpad is
  non-volatile** — a `ZSX` marker survived a full power cycle (verified
  2026-08-15 via `nvram_roundtrip.py`). `ZUX` quirks on real hardware:
  no newline terminator, one stray trailing byte appended (match by
  prefix), and reads need an input-buffer flush + ~0.3 s settle or they
  desync (the library `read_note`/`write_note` are simulator-clean; the
  hw script handles the real-device quirks).
- Queued submit acks: real firmware answers `ZNX` with `OK` **or**
  `INPROCESS:<n>` under load — both are accepts. Only a reply containing
  `ERR:` is a rejection (matches cgminer's `isokerr`); `QueuedWorkSession.submit`
  was fixed accordingly (previously it wrongly rejected `INPROCESS:`).
- Driving the queued protocol on real hardware requires an input-buffer
  flush before every command — the firmware is chatty (multi-line details
  blocks, `INPROCESS:n` result prefixes) and unflushed sequential reads
  desync. `scripts/hw/characterize.py` drives the protocol directly with
  per-command flushes for this reason; `JOBS IN QUEUE` reads ~0 even
  mid-scan, so it is not usable for backpressure (bound in-flight jobs by
  submitted-minus-drained instead).
