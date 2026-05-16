# Development Log

## 2026-05-16 — Dynamics validation + per-batch probe (external-review follow-up)

Acting on a third-party review of the Tier A artifacts:

- **Dynamics path validated to the project standard.** `run_dynamics_sweep`
  now computes a real Clopper-Pearson `accuracy_ci` and a CI-resolution
  floor per point (was `[0,1]` / `0.0` placeholders), gates `positive_ok`
  on the CI lower bound exceeding chance (was a bare point estimate with
  an arbitrary +0.05 margin), and runs a **permuted-label negative
  control** on the lead width (was a hardcoded `negative_ok=True`). The
  shuffled-label model must not beat chance, or the signal is a
  dataset/setup artifact, not orbit structure.
- **Tier A dynamics number is superseded.** The recorded Tier A
  `dynamics` figure (width-1 ≈ 0.354 vs 0.25 chance) was produced by the
  *pre-fix* harness with no permuted-label control. It is **exploratory,
  not a verified positive** — do not cite it as a result. A re-run with
  the corrected harness is required to make any dynamics claim.
- **Per-batch feature probe (local, n=2M, rounds 3,4,5,6,8).** Per-batch
  reproduces the *same* round-4 learnability cliff as per-hash (r3=1.00;
  r4–8 CI brackets 0.5). The cliff is **not feature-bottlenecked**.
  Caveat: per-batch's CI-floor here is coarse (~0.10) because the
  deviation-map feature yields few examples — decisive for the Tier C
  *decision* (feature variation, C.1, is low-value), not a tight null.
- **Tier C status.** C.1 (feature variation) deprioritized by the above
  evidence. C.2 (architecture variation — does the cliff move with model
  capacity / inductive bias?) is the only open question and is future
  work (new model classes). C.3 (overlay published reduced-round
  algebraic-distinguisher counts vs the ML cliff) is a cheap honest
  framing addition for a future methodology note — verify citations
  before asserting round numbers.

This is a personal AI/ML capability exploration, not novel research; the
honesty bar (controls gate the verdict; no overclaim) is what matters.

---

## 2026-05-15 — Optional ML learnability subsystem

Added `bfl_asic/ml/`: a numpy-vectorized round-reduced SHA-256 (bit-exact
with hashlib SHA-256d at 64 rounds — the regression anchor), deterministic
distinguisher/orbit datasets, TinyCNN + LinearProbe, and a controls-gated
train/eval harness. Four experiments: the round-reduced learnability sweep
(#1), the full-SHA indistinguishability demo (#2), the bounded-null
"any structure" search (#4), and dynamics-orbit learnability vs truncation
(#3). PyTorch is isolated behind the `[ml]` extra and lazy-imported by the
CLI, so the core install and the default fast test suite remain torch-free.
A "no structure" conclusion is only emitted when the positive control
learns and the negative control fails; `min_detectable_advantage` is a
CI-resolution floor (not a power-based MDE) and is labelled as such.
Snapshots are strict-RFC-8259 JSON. Built TDD across 10 reviewed tasks.

---

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

## 2026-03-02 — Hardware Characterization

### Overview

Ran a structured characterization suite (`scripts/characterize.py`) against the real device on COM3 through an isolating USB hub. Six test levels with increasing intensity, repeated 4 times for consistency.

### Test Levels

| Level | Name | Work Units | Spacing | Purpose |
|-------|------|-----------|---------|---------|
| 0 | Idle baseline | 0 | — | 5 temp/voltage readings at 1s intervals |
| 1 | Single work | 1 | — | Measure baseline round-trip time |
| 2 | Light burst | 5 | back-to-back | Short burst behavior |
| 3 | Medium burst | 15 | back-to-back | Medium load with mid-test temp reads |
| 4 | Extended run | 30 | 100ms gaps | Extended load — hits firmware limit |
| 5 | Sustained paced | 20 | 2s gaps | Steady state — post-limit behavior |

### Key Findings

#### 1. Thermal Profile — Zero Stress at USB Throughput

| Condition | Chip 1 | Chip 2 | Ambient |
|-----------|--------|--------|---------|
| Idle baseline | 31°C | 30°C | ~21°C |
| After 1 work unit | 31°C | 30°C | — |
| After 5 work units | 31°C | 30°C | — |
| After 15 work units | 31°C | 30°C | — |
| After 21 work units | 29°C | 31°C | — |

The device shows zero thermal response to USB-submitted work. At ~1 work unit/sec throughput (USB-limited), the ASIC generates negligible heat. The ±2°C fluctuation is within normal sensor noise. Real thermal stress would require direct bus access at the ASIC's native 5 GH/s rate.

#### 2. Round-Trip Timing — Remarkably Consistent

| Level | Mean RT (ms) | Min-Max | Throughput |
|-------|-------------|---------|------------|
| 1 (single) | 1008-1024 | — | 0.98 wps |
| 2 (light burst) | 1014-1021 | 1008-1024 | 0.98 wps |
| 3 (medium) | 1013-1018 | 1008-1024 | 0.98 wps |
| 4 (extended) | 1015-1018 | 1007-1024 | 0.67 wps* |

*\*Includes error recovery time in denominator.*

Round-trip times are locked to 1008ms or 1024ms — exactly multiples of 16ms, which is the Windows timer resolution. The actual serial transaction takes ~1.0 seconds, dominated by the ASIC processing the full 2^32 nonce space at 5 GH/s (theoretical: 2^32 ÷ 5×10^9 = 0.86s, plus serial overhead).

#### 3. VCC1 Voltage Anomaly

| Reading Context | VCC1 Range | VCC2 | VMAIN |
|----------------|-----------|------|-------|
| Idle, standalone | 3.18-3.58V | 1.008-1.011V | 11.29-11.52V |
| Immediately after ZLX/ZTX | 2.18-2.57V | 1.004-1.014V | 11.26-11.52V |

VCC1 shows a consistent ~1.2V drop when read immediately after other ADC queries. VCC2 and VMAIN are stable. Possible explanations:
- **ADC multiplexer settling time**: The ZTX command samples three ADC channels in sequence; VCC1 may be read before the analog multiplexer settles
- **Shared ADC reference**: The 3.3V rail may be both the measured value and the ADC reference, creating circular measurement artifacts
- **Switching regulator ripple**: The VCC1 rail may have high ripple that the single-sample ADC captures at random phases

The high readings (3.4-3.6V, ~8% above 3.3V nominal) are more likely to be accurate, consistent with a slightly high-set voltage regulator. The low readings (~2.2V) are almost certainly measurement artifacts.

#### 4. Firmware Work Limit — 42 Submissions Per Session

**Critical discovery:** The SC firmware stops responding to ZDX (work submission) after exactly **42 cumulative work submissions** per session. This was reproduced identically across all 4 test runs:

| Cumulative Count | Level | Result |
|-----------------|-------|--------|
| 1-1 | Level 1 | OK |
| 2-6 | Level 2 | OK |
| 7-21 | Level 3 | OK |
| 22-42 | Level 4 | OK |
| 43 | Level 4 | **FAIL** (empty response) |
| 44+ | Level 5 | **FAIL** (persistent) |

The failure mode:
- The device returns an empty response (`b""`) — serial readline times out
- Retries fail identically (with 0.5s delay between retries)
- ZGX (identify) and ZLX/ZTX (temp/voltage) still work after the error
- Closing and reopening the serial port does not reset the counter
- Flushing serial buffers does not help
- Only a power cycle resets the work counter

This limit is firmware-level, not serial/FTDI-level. The device accepts non-work commands after hitting the limit but refuses all ZDX work submissions. This means the SC firmware maintains a persistent work counter that cannot be reset through the protocol.

**Implications for software design:** Applications submitting work must track the submission count and either power-cycle the device or implement a workaround (such as a USB power relay) for sustained operation.

##### 2026-05-16 correction — the "42 limit" is a naive-path artifact

The original conclusion ("firmware-level counter ... only a power cycle
resets it ... apps must power-cycle") is **over-stated**. Empirical
disproof: this device was run as a Bitcoin miner for days / thousands of
submissions with zero power cycles. cgminer/bfgminer drive the SC
*queued* protocol (`ZNX`/`ZWX` + continuous `ZOX` result-drain +
`ZCX` `JOBS IN QUEUE` backpressure) and never approach 42. The 42 wall
is an artifact of the naive `ZDX`/`ZFX` path never draining the queue --
not a hardware ceiling. Fixed additively by `QueuedWorkSession`
(`bfl_asic/device.py`); the naive path is intentionally left unchanged
as the honest demonstration of the wall. See
`docs/superpowers/specs/2026-05-16-sc-queued-work-design.md`.

#### 5. Work Result Status — IDLE vs NO-NONCE

All work units return `IDLE` status (not `NO-NONCE` or `NONCE-FOUND`). The SC firmware appears to:
1. Accept work (ZDX → `OK`)
2. Process the full nonce range at 5 GH/s in ~0.86s
3. Return `IDLE` on the next ZFX poll if no nonces met the difficulty target

This differs from the expected `NO-NONCE` response. The SC firmware may use IDLE as its equivalent of NO-NONCE, or there may be a timing window where the result expires before the poll arrives. Miners (cgminer/bfgminer) handle this by continuously submitting work and only caring about `NONCE-FOUND` responses.

### Characterization Data

Raw JSON logs saved in `scripts/`:
- `characterize_hardware.json` — Run 1 (no recovery)
- `characterize_hardware_2.json` — Run 2 (with retry logic)
- `characterize_hardware_3.json` — Run 3 (with recovery + 100ms spacing)
- `characterize_hardware_reset.json` — Run 4 (with serial port reset)

---

---

## 2026-05-13 — Randomness Battery, Convergence Animation, Output Organisation

### Phase 3: NIST SP 800-22 Randomness Battery (App 1, validation half)

Built `bfl_asic/randomness/` parallel to the stats and dynamics subsystems. The new module consumes any `HashSource` from `stats.engine`, so it slots in unchanged once an ASIC-backed source replaces `SoftwareHashEngine`.

Six tests implemented as pure numpy functions over `uint8` bit arrays:

- **Frequency (monobit)** — SP 800-22 §2.1
- **Block frequency** — §2.2
- **Runs** — §2.3 (conditional on monobit, returns skipped result if π too far from 0.5)
- **Longest run of ones in block** — §2.4 (parameter table selects block size by *n*)
- **DFT spectral** — §2.6 (FFT magnitude vs 95% threshold)
- **Cumulative sums** — §2.13, both forward and reverse modes

Reference p-values from the worked examples in SP 800-22 Rev 1a Section 2 are exercised as regression anchors (`p ≈ 0.527089` for the §2.1.8 monobit case, `p ≈ 0.801252` for the §2.2.8 block-frequency case, `p ≈ 0.147232` for §2.3.8 runs).

Plus a `RandomnessBattery` orchestrator that harvests *N* hashes from any engine and runs every enabled test, a `RandomnessSnapshot` for JSON serialisation, and `bfl-asic randomness run/report` CLI commands mirroring the stats group. **57 new tests, 654 total.**

### Phase 4: Bit-Frequency Convergence Animation (learning aid)

Added `animate_bit_frequency_convergence()` in `stats/visualization.py`. Runs a hash engine to a chosen sample count, capturing the 256-bit deviation vector `count/N - 0.5` at log-spaced checkpoints. Produces a two-panel GIF:

- **Top** — 16×16 heatmap of the current bias with a fixed colour scale (so shrinkage is visible).
- **Bottom** — log-log plot of `max|bias|` and `mean|bias|` against the theoretical `0.5/√N` envelope, with a cursor tracking the current frame.

Demonstrates the law of large numbers in action: SHA-256 output is *never* exactly uniform at finite *N*, but the residual deviation tracks `1/√N` exactly. If the red line ever flattened out instead of falling, you'd have found a flaw in SHA-256.

Exposed via `bfl-asic stats animate-convergence --samples N --frames F`. **5 new tests, 659 total.**

### Phase 5: Output Organisation

CLI outputs were dumping into the working directory and could overwrite previous runs. Added two mechanisms in `bfl_asic/cli.py`:

1. **`unique_output_path()`** — every write path checks for collisions; existing files get a `_YYYYMMDD-HHMMSS` suffix on the new write. Same-second collisions get an additional incrementing counter. Parent directories are auto-created.
2. **Default folder layout** — when `-o` is omitted, commands that auto-generate artefacts land under:
   - `runs/stats/<ts>/{snapshot.json,dashboard.png}` (`stats run --plot`)
   - `runs/animations/convergence-<ts>.gif` (`stats animate-convergence`)
   - Explicit `-o` is honoured verbatim with collision-avoidance.

Configurable via `$BFL_ASIC_OUTPUT_DIR`. Added `runs/` to `.gitignore`. **12 new tests, 671 total.**

### Working Tree State

`scripts/diagnose_work.py` (previously untracked) committed as a documented diagnostic tool — uses the Bitcoin genesis block (known winning nonce 2083236893) plus synthetic trivial work to exercise the work-acceptance path with aggressive polling. Complements `characterize.py`.

---

## Project Metrics

_Point-in-time snapshot; live test/source totals are tracked in README.md and CLAUDE.md._

| Metric | Value |
|--------|-------|
| Source lines | 5,142 |
| Test lines | 5,919 |
| Test count | 783 |
| Source files | 31 |
| Test files | 26 |
| Test:source ratio | 1.15x |

## Roadmap

Remaining applications from the seed document not yet implemented:

- ~~**App 1:** Entropy harvesting / hardware RNG~~ — **partial:** software-source validation now in place via `bfl_asic/randomness/`. ASIC-backed source still needed for true hardware RNG.
- **App 3:** Proof-of-work token minting
- **App 4:** Hash-based data authentication
- **App 5:** Brute-force preimage search
- **App 6:** Educational SHA-256 explorer (the convergence animation is a small step toward this)
- **App 7:** Commitment schemes
- **App 9:** Research test harness

Next priorities to consider:
- ASIC-accelerated hash source (swap `SoftwareHashEngine` for device-backed `HashSource` — the randomness battery is already wired to accept it)
- Direct ASIC bus tapping for full hash throughput (bypasses USB bottleneck)
- Firmware work limit workaround (USB power relay for automated power cycling, or direct FPGA/ASIC reset via GPIO)
- VCC1 ADC settling time investigation (add configurable delay between ADC reads)
- Work result polling strategy (test faster polling to catch BUSY→NO-NONCE transition)
- Avalanche side-by-side visualiser — show two near-identical inputs producing wildly different outputs (paired pedagogy with the convergence animation)
- Round-by-round SHA-256 internals viewer — instrument the pure-Python compression in `protocol/work.py` to expose the 8 working variables across all 64 rounds
