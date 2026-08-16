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

# Run all tests (835 total, ~65s, no hardware required; 833 pass in the fast suite — 2 slow ML training tests excluded by -m "not slow")
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
- `bfl_asic/cli.py` — Click-based CLI with subcommand groups (`device details/firmware/note/health`, `stats run/report/animate-convergence`, `dynamics run/plot`, `randomness run/report`, `fan auto|0-4`). `device details` renders the `ZCX` census via the pure `_render_census` helper; `device note --write` is gated behind `--confirm-nvram-write`; `device health` runs dead-core detection.
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
- Undocumented probe commands (recovered from real hardware, since
  cgminer defines but never sends them): `ZJX` returns a bare firmware
  version (`1.0.0`, no framing); `ZUX` returns the NVRAM scratch string
  or the sentinel `MEMORY EMPTY`; `ZSX` writes NVRAM (`SaveString` =
  length byte + payload), gated in the CLI. **The scratchpad is
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
