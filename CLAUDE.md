# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Communication layer and analysis tools for the Butterfly Labs BF0005G Jalapeno SHA-256 ASIC miner. Provides protocol encoding/decoding, serial transport, device simulation, statistical analysis of hash output, iterated-hash dynamics research, and NIST SP 800-22 randomness validation.

## Common Commands

```bash
# Install (editable, with dev deps)
pip install -e ".[dev]"

# Run all tests (~671 tests, ~20s, no hardware required)
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

**Protocol layer** (`bfl_asic/protocol/`) — Pure functions, no I/O. Builds command byte sequences (ZGX, ZLX, ZTX, ZDX, ZFX, ZPX), parses responses into dataclasses, computes SHA-256 midstates. All protocol logic is independently testable.

**Transport layer** (`bfl_asic/transport/`) — I/O abstraction via `BaseTransport` ABC. `SerialTransport` wraps pyserial for real hardware (FTDI VID 0x0403, PID 0x6014, 115200 8N1). `SimulatorTransport` provides an in-process fake device with thermal model and real SHA-256d computation — all tests run against the simulator. Async methods default to `asyncio.to_thread()` wrapping of sync implementations.

**Device layer** (`bfl_asic/device.py`, `async_device.py`) — High-level API. `BFLDevice` (sync) and `AsyncBFLDevice` (async with stream iterators). Both are context managers that own transport lifecycle.

**Application layer** (independent subsystems):
- `bfl_asic/stats/` — SHA-256 statistical analysis: 7 numpy-vectorized accumulators, FFT spectral analysis, pipeline orchestrator, matplotlib visualization (including an animated bit-frequency convergence GIF for teaching the law of large numbers).
- `bfl_asic/dynamics/` — Iterated hash orbit/cycle analysis: Floyd's and Brent's cycle detection (O(1) memory), multi-seed convergence analysis.
- `bfl_asic/randomness/` — NIST SP 800-22 randomness test battery over any `HashSource`. Six tests as pure numpy functions: frequency (monobit), block frequency, runs, longest-run-in-block, DFT spectral, cumulative sums (forward + reverse). Designed to plug an ASIC-backed hash source in unchanged when one exists.
- `bfl_asic/cli.py` — Click-based CLI with subcommand groups (`stats run/report/animate-convergence`, `dynamics run/plot`, `randomness run/report`).

## Key Conventions

- **Exception hierarchy**: All package exceptions inherit from `BFLError`. Subtypes: `BFLConnectionError`, `BFLProtocolError`, `BFLTimeoutError`, `BFLDeviceError`.
- **Protocol commands**: ASCII 3-byte codes. Work packets are 60 bytes (8-byte delimiter + 32-byte midstate + 12-byte tail + 8-byte delimiter). Responses delimited by `>>>>>>>>` (8 × 0x3E).
- **pytest-asyncio**: Configured with `asyncio_mode = "auto"` — async test functions are auto-detected.
- **Matplotlib**: Uses `Agg` backend (headless) for all visualization to avoid display dependencies.
- **CLI outputs**: Default writes go under `runs/<command>/<timestamp>/` (or a single timestamped filename for standalone artefacts). Explicit `-o` is honoured verbatim. The no-overwrite policy applies to every write path: collisions get a timestamp suffix. Root is configurable via `$BFL_ASIC_OUTPUT_DIR`. The `runs/` folder is gitignored.
- **Python ≥ 3.10** required.

## Hardware Notes

- The SC firmware has a **42 work submission limit** per power cycle — the device stops accepting work after 42 submissions and must be power-cycled.
- Temperature/voltage commands were discovered to be **reversed** from initial protocol assumptions: ZLX reads temperature, ZTX reads voltage (not vice versa).
- VCC1 readings show anomalous ~1.2V drops after ZTX queries (suspected ADC settling time issue).
