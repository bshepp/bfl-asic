# Development Log

## 2026-02-25 — Phase 1: Device Communication Layer

### Session 1: Specification and Design

Started from a seed document (`bfl-asic-repurpose.md`) outlining 9 potential applications for repurposing a Butterfly Labs SHA-256 ASIC miner. The target device is a **BF0005G Jalapeno** (5 GH/s).

**Design decisions made:**
- Python package (`bfl-asic`) with layered abstraction architecture
- Cross-platform (Linux + Windows)
- Built-in simulator for development without hardware
- Async support alongside sync API
- Protocol → Transport → Device → Application layer separation

**Protocol research:**
- BFL BitFORCE serial protocol: ASCII commands over USB serial at 115200 8N1
- FTDI USB-serial chip (VID `0x0403`)
- Commands: ZGX (identify), ZTX (temperature¹), ZDX (work), ZFX (poll), ZPX (nonce range)
- Work packets: 60 bytes — 8-byte delimiter `>>>>>>>>` + 32-byte SHA-256 midstate + 12-byte block tail + 8-byte delimiter
- Midstate requires pure-Python SHA-256 compression (hashlib doesn't expose internal state)

¹ *Later corrected: ZTX is voltages, ZLX is temperature — see 2026-03-01 entry.*

### Session 1: Implementation (Phase 1 complete)

Built the full communication layer in a single session:

**Step 1: Scaffolding** — `pyproject.toml`, package init, constants, exception hierarchy. Fixed build-backend from `setuptools.backends._legacy:_Backend` to `setuptools.build_meta`. (31 tests)

**Step 2: Protocol layer** — `commands.py` (pure command builders), `responses.py` (parser functions + data classes), `work.py` (pure-Python SHA-256 compression for midstate computation with FIPS 180-4 constants). Fixed `_ch` function parenthesization: `((x & y) ^ (~x & z)) & _MASK32`. (126 tests)

**Step 3: Transport layer** — `base.py` (ABC with sync + async defaults), `serial.py` (pyserial wrapper), `discovery.py` (FTDI device scanning). Fixed 7 test failures: mock reference saved before `close()`, corrected mock path for discovery. (179 tests)

**Step 4: Simulator** — `SimulatedDevice` state machine with thermal model (IDLE/HASHING/OVERHEATED), real SHA-256d computation, configurable error injection. `SimulatorTransport` bridges BaseTransport to SimulatedDevice. (237 tests)

**Step 5: Device APIs** — `BFLDevice` (sync) and `AsyncBFLDevice` (async with `hash_stream` and `entropy_stream` iterators). (291 tests)

**Step 6: CLI** — Click-based CLI with `identify`, `temperature`, `probe`, `discover`, `benchmark`, `hash` subcommands. Group-level `--port/-p`, `--simulate/-s`, `--baudrate/-b` options. Defaults to simulator when no port specified. (308 tests)

**Verification:** Installed with `pip install -e .`, smoke tested all CLI commands against the simulator.

---

## 2026-02-25/26 — Phase 2: Statistical Analysis Pipeline

### Design

Device was on order (with UPS and USB isolator). Designed a statistical analysis pipeline for SHA-256 probability landscape exploration (App 2) and iterated hash dynamics (App 8).

**Key design decision:** Software hash engine now, ASIC swap-in later. The current device API only returns nonces (mining winners), not full hashes. For statistical analysis, every hash is needed. Created `HashSource` ABC as the swap point.

### Implementation

**Step 1: Hash engine** — `HashSource` ABC, `SoftwareHashEngine` (sequential counter inputs), `SequentialInputEngine` (inputs differing by +1 for avalanche analysis). (346 tests)

**Step 2: Statistical accumulators** — Seven numpy-vectorized accumulators with O(1)/O(k) memory:
- `BitFrequencyAccumulator` — 256-position bit frequency tracking
- `AvalancheAccumulator` — Hamming distance histogram (257 bins)
- `BitCorrelationAccumulator` — pairwise bit co-occurrence matrix
- `NearCollisionAccumulator` — rolling window collision detection
- `ByteDistributionAccumulator` — 256-bin byte histogram
- `EntropyAccumulator` — Shannon entropy
- `CompositeAccumulator` — runs all six in parallel
(416 tests)

**Step 3: Snapshot + spectral** — `StatsSnapshot` with JSON serialization (custom numpy encoder), `BitPositionTimeSeries` circular buffer with FFT via `scipy.fft.rfft`, z-score peak detection. (518 tests)

**Step 4: Pipeline** — `StatsPipeline` orchestrator wiring engine → accumulators → spectral → snapshot. `run(samples)` and `run_timed(seconds)` with progress callbacks. (536 tests)

**Step 5: Iterated hash dynamics** — Independent of the stats pipeline:
- `orbit.py` — Orbit computation with sampled trajectories and Hamming distance tracking
- `rho.py` — Floyd's tortoise-and-hare and Brent's power-of-two cycle detection (both O(1) memory)
- `convergence.py` — Multi-seed convergence analysis with dict-based O(1) state matching
- Used toy hash function (SHA-256 truncated to 3 bytes, ~2^24 state space) for testing cycle detection where cycles occur in ~2^12 steps
(474 tests alongside other work)

**Step 6: Visualization** — Matplotlib plotting with Agg backend (headless):
- Stats: bit frequency heatmap (16x16 diverging colormap), Hamming distance histogram with Binomial(256, 0.5) overlay, byte distribution with uniform reference, correlation matrix, power spectrum, 2x2 dashboard
- Dynamics: orbit Hamming distance over iterations, 2D convergence trajectories, tail/cycle length histograms
(557 tests)

**Step 7: CLI integration** — Added `stats` and `dynamics` command groups to existing CLI:
- `bfl-asic stats run [--samples N] [--duration S] [--report-interval M] [-o file.json] [--plot]`
- `bfl-asic stats report <snapshot.json>`
- `bfl-asic dynamics run [--seeds N] [--max-iterations M] [-o results.json]`
- `bfl-asic dynamics plot <results.json>`
- `_MutuallyExclusive` Click option class for `--samples`/`--duration`
- Lazy imports throughout (no numpy/scipy/matplotlib on basic CLI startup)
- JSON serialization for dynamics results (bytes → hex, numpy types handled)
(587 tests)

**Code review findings fixed:**
- Matplotlib figures not closed after saving — added `plt.close(fig)` in CLI commands
- No error handling for corrupt JSON — added try/except with `click.ClickException`

---

## 2026-03-01 — Hardware Testing: First Contact

### Device arrives

Connected the Butterfly Labs BF0005G Jalapeno through an isolating USB hub.

**Discovery:** Device found on COM3, FTDI VID `0x0403`, PID `0x6014`.

**Identify:** `BitForce SHA256 SC 1.0` — confirmed Single Chip variant.

### Protocol corrections

**Temperature command was wrong.** The device returned `3436,1008,11360` for ZTX, which our parser couldn't handle. Initial fix: treated as raw ADC values divided by 100.

**Deeper investigation via cgminer/bfgminer source analysis** revealed the real issue:

| Command | What we assumed | What it actually is |
|---------|-----------------|---------------------|
| ZLX | (not implemented) | **Temperature** — `Temp1: 30, Temp2: 30` (°C) |
| ZTX | Temperature | **Voltages** — `3564,1011,11420` (millivolts) |

The SC firmware uses ZLX for temperature and ZTX for voltage readings. The three ZTX values are VCC1, VCC2, and VMAIN in millivolts, confirmed by cgminer's `driver-bflsc.c` which divides each by 1000.0.

**Changes made:**
- `CMD_TEMP` changed from `ZTX` to `ZLX`
- Added `CMD_VOLTAGE = b"ZTX"`
- New `VoltageReading` dataclass and `parse_voltage()` parser
- `parse_temperature()` updated for SC format (`Temp1: 30, Temp2: 30`)
- `BFLDevice.get_voltage()` added
- CLI `probe` and `temperature` commands show both temp and voltage
- Simulator updated to match real device response formats

### Device readings at 21.4°C ambient (idle)

| Measurement | Value | Notes |
|-------------|-------|-------|
| Chip 1 temp | 30°C | ~9°C above ambient, idle |
| Chip 2 temp | 30°C | Second sensor or same die |
| VCC1 | 3.564V | Core logic (nominal 3.3V, ~8% high) |
| VCC2 | 1.011V | PLL/IO voltage (nominal 1.0V) |
| VMAIN | 11.420V | Main supply rail |

### Functional verification

| Command | Result |
|---------|--------|
| `discover` | Found on COM3 |
| `identify` | BitForce SHA256 SC 1.0 |
| `temperature` | Chip 1: 30°C, Chip 2: 30°C |
| `probe` | All commands respond |
| `hash "hello world"` | Work accepted, 0 nonces (expected) |
| `benchmark --duration 5` | 5 work units, ~1.0 units/sec (USB-limited) |

All device interaction works. USB serial round-trip latency limits throughput to ~1 work unit/sec regardless of the ASIC's 5 GH/s internal rate.

Final state: **597 tests passing**, repo at https://github.com/bshepp/bfl-asic

---

## Project Metrics

| Metric | Value |
|--------|-------|
| Source lines | 4,285 |
| Test lines | 5,127 |
| Test count | 597 |
| Source files | 27 |
| Test files | 22 |
| Test:source ratio | 1.20x |

## Roadmap

Remaining applications from the seed document not yet implemented:

- **App 1:** Entropy harvesting / hardware RNG (API exists, needs NIST test suite)
- **App 3:** Proof-of-work token minting
- **App 4:** Hash-based data authentication
- **App 5:** Brute-force preimage search
- **App 6:** Educational SHA-256 explorer
- **App 7:** Commitment schemes
- **App 9:** Research test harness

Next priorities to consider:
- ASIC-accelerated hash source (swap `SoftwareHashEngine` for device-backed `HashSource`)
- Direct ASIC bus tapping for full hash throughput (bypasses USB bottleneck)
- Thermal stress testing under sustained load
- VCC1 voltage investigation (3.564V vs 3.3V nominal)
