# Changelog

All notable changes to this project are documented here. This project
adheres loosely to [Semantic Versioning](https://semver.org/).

## [0.2.0] — 2026-08-15

The "protocol surface + silicon forensics" release: a batch of work that
re-derives the BFL SC command surface from real hardware, characterizes
a physical Jalapeno, and adds a dead-core-detection instrument. Nothing
here is a novel protocol discovery — the commands are documented in BFL's
2012 spec and/or the open-source firmware (`luke-jr/BitForce_SC`); we
re-derived and empirically confirmed them because the mining software
(cgminer) never exercised them.

### Added
- **`ZCX` device census** — `parse_details` → `DeviceDetails` with typed,
  case-/dash-insensitive accessors (`firmware`, `engines`, `frequency` /
  `frequency_mhz`, `mining_speed`, `critical_temperature`, `processors` →
  `list[Processor]`), surfacing per-processor topology and other fields
  beyond the 2012 spec. CLI: `device details`.
- **Probe commands** (`bfl_asic/protocol/probe.py`): `ZJX` (firmware),
  `ZUX`/`ZSX` (NVRAM load/save string). CLI: `device firmware`,
  `device note --read/--write/--verify` (write gated by
  `--confirm-nvram-write`). The NVRAM scratchpad is confirmed
  non-volatile (survives a power cycle).
- **Dead-core detection** (`bfl_asic/health.py`, `device health`): flags
  cold bands in the winning-nonce histogram as dead engines.
- **Characterization** (`bfl_asic/characterization.py`, `characterize`):
  throughput, nonce-value distribution, and dead-core health; plus the
  deep opt-in `scripts/hw/characterize.py` (thermal telemetry,
  determinism, checkpointing).
- **Port auto-detection** — `bfl-asic <cmd>` with no `--port`/`--simulate`
  finds the connected FTDI device (falls back to the simulator).
- **`report-issue`** — opens a prefilled GitHub bug/feature issue.
- **Hardware scripts** (`scripts/hw/`): `read_details`, `probe_commands`,
  `nvram_roundtrip`, `temp_sweep` (supervised), plus characterization.
- **Empirical data** in `docs/characterization/` (30-min + 4-hour runs,
  supervised temperature sweep) and `docs/hardware-experiments.md`.

### Fixed
- **`QueuedWorkSession.submit`** wrongly rejected `INPROCESS:<n>`, which
  real firmware sends as a valid queued-job accept under load. Now
  rejects only on `ERR:` (matches cgminer's `isokerr`).
- **Hardware read desync** — added `transport.flush_input()` (no-op on
  the simulator, serial-buffer reset on hardware), wired into all device
  read paths, so the chatty SC firmware no longer desyncs sequential
  reads.

### Characterization findings
- 4 hours of continuous work: **zero compute errors**, fully
  deterministic, winner count Poisson(~1) (full 2³² diff-1 scan).
- Thermally over-provisioned: won't exceed ~41–47 °C even fan-off; no
  thermal-error regime reachable on a desk.
- Throughput is USB/serial-bound (~1.2 jobs/s), identical on direct USB
  3.0 vs the isolated path — though direct USB 3.0 is **unstable** over
  time (Code 10 faults); the ADuM3160 isolator provides stability.

## [0.1.0]
- Initial toolkit: protocol layer, serial + simulator transports, device
  API, statistical/dynamics/randomness analysis, and the optional ML
  learnability instrument.
