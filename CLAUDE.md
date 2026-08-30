# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Started as a communication layer and analysis toolkit for the Butterfly Labs BF0005G Jalapeno SHA-256 ASIC miner; now a **model-free characterization lab for retro mining silicon**. The Jalapeno stays the protagonist (protocol encoding/decoding, serial transport, device simulation, ZCX census, dead-core detection, sustained-work characterization), and the device-agnostic core (`characterize_source`, `health`, `NonceSource`) extends to a growing fleet — the ASICMiner Block Erupter (device #2, Icarus protocol) and the **Antminer U1** (device #3, Icarus; first-contacted and fingerprinted at ~1.5 GH/s, and the first device in this project with **working live clock control** — the ANU frequency lever verified on hardware 2026-08-28), with the GekkoScience NewPac incoming. Plus statistical analysis of hash output, iterated-hash dynamics research, NIST SP 800-22 randomness validation, an optional ML learnability instrument, and a Govee H5075 BLE ambient decoder. The `bfl-asic` name is kept for continuity (dataset/blog/release links); the scope is deliberately broader.

## Common Commands

```bash
# Install (editable, with dev deps)
pip install -e ".[dev]"

# Install with optional ML subsystem (adds PyTorch)
pip install -e ".[ml]"

# Run all tests (890 total, ~65s, no hardware required; 888 pass in the fast suite — 2 slow ML training tests excluded by -m "not slow")
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

**Transport layer** (`bfl_asic/transport/`) — I/O abstraction via `BaseTransport` ABC. `SerialTransport` wraps pyserial for real BFL hardware (FTDI VID 0x0403, PID 0x6014, 115200 8N1). `IcarusSerialTransport` is its Icarus-protocol sibling for the fleet (CP210x/FTDI USB-UART, write-64B-work / read-4B-nonce, long Icarus read timeout, `serial_factory` DI seam); `SimulatedIcarusTransport` is its headless double. `SimulatorTransport` provides an in-process fake device with thermal model and real SHA-256d computation — all tests run against the simulators. Async methods default to `asyncio.to_thread()` wrapping of sync implementations.

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
  the slowest word (0x0000) left the census at 189 MHz. **CORRECTION
  (2026-08-22, from reading `luke-jr/BitForce_SC`):** the earlier
  "thermal-hover loop" explanation was wrong. Three source-level facts
  explain "OK but nothing changes": (1) the census `FREQUENCY:` field is a
  compile-time **constant** (`sprintf` of a fixed table value) — it can
  never reflect a live write, so "stayed 189 MHz" proved nothing (watch the
  per-`PROCESSOR @ N MHz` line instead, which IS a live measurement); (2)
  `ZVX`'s "all chips" broadcast writes chip `0xFF`, but the ASIC's
  chip-address field is only 3 bits, so `0xFF` masks to 7 — it reaches chip
  7 only, never chip 3 (the Jalapeno's two live dies are processors 3 & 7);
  (3) a bare `0x60` write omits the reg-0 reset / reg-`0x61` clock-enable
  relatch the boot path performs. (There is *also* event-driven re-assert —
  `init_ASIC()` re-runs on sustained low engine count and on thermal
  recovery after >90 C — but not a continuous hover.) `ZKX` returns 0
  (unimplemented). **Conclusion: the sweep is NOT achievable via the stock
  `ZVX` handler, but it is NOT fundamentally closed** — custom firmware
  (JTAG/DFU reflash on the sacrificial unit) can drive the clock, and the
  exact patch points are known (freq table `std_defs.c:15`, disable the boot
  auto-OC ramp, fix the `0xFF` broadcast to loop real chips, add the
  reg-`0x61` relatch). `scripts/hw/freq_underclock.py` is the ZVX probe. **The scratchpad is
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
- **Antminer U1 (device #3, Icarus).** Enumerates as a **Silicon Labs CP210x
  USB-UART bridge** (VID `0x10C4`, PID `0xEA60`) — not FTDI, so the BFL
  auto-detect doesn't see it; the COM number is not stable across replug
  (re-detect by VID/PID). First contact via the golden-work self-test
  (`GOLDEN_WORK` → `GOLDEN_NONCE` `0x000187A2`, big-endian on the wire).
  Fingerprinted at **~1.5 GH/s** (linear-scan hashrate; nominal ~1.6 @
  200 MHz), healthy, ~1/e of random works yield no nonce (diff-1 Poisson).
  Driven by `IcarusSerialTransport` + `IcarusNonceSource` + `characterize_source`.
  **The ANU frequency lever WORKS** (unlike the Jalapeño): `build_anu_set_freq`
  physically moves the clock — a 200/150/100 MHz underclock sweep scaled
  hashrate linearly at ~7.9 MH/s per MHz, with the read-reg echoing the PLL
  multiplier. The U1 has **no serial temperature readout** (Icarus has no temp
  command), so an *overclock* (above stock) needs an **external** thermal probe
  — e.g. a milieu ambient sensor beside the unit. Underclock verification is
  thermally safe (cooler than stock) and reversible; ANU freq is not persistent
  (a power cycle resets to default). `scripts/hw/icarus.py` is the driver.
