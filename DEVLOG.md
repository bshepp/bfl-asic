# Development Log

## 2026-08-28 — device #3 (Antminer U1): real Icarus transport + first live clock control

An **Antminer U1** arrived (device #3, on the isolated USB 2.0 hub). In one
evening it went from unplugged to the first device in this whole project whose
mining clock we can actually **move** — the frequency control the Jalapeño
firmware denied us.

- **First contact.** Enumerated as a **Silicon Labs CP210x** USB-UART bridge
  (VID `0x10C4` / PID `0xEA60`, on `COM4`, healthy). The Icarus golden-work
  self-test returned `GOLDEN_NONCE` (`0x000187A2`, big-endian) — alive, speaking
  Icarus, and the **first hardware validation of `protocol/icarus.py`** (pure +
  simulator only until now).

- **Real Icarus transport (TDD, committed).** Built
  `bfl_asic/transport/icarus_serial.py` `IcarusSerialTransport` — the live-port
  counterpart to `SimulatedIcarusTransport` (pyserial, 8N1, long Icarus read
  timeout, `serial_factory` DI seam for headless tests). 9 behavioral tests
  (`tests/test_icarus_transport.py`) incl. a golden-nonce contract through
  `IcarusNonceSource`; full fast suite 897 pass, 0 regressions. The device-neutral
  `characterize_source` now drives the U1 unchanged — one rig, two protocols.

- **Fingerprint = Antminer U1.** A sustained run measured **~1.52 GH/s**
  (linear-scan hashrate) — squarely U1 (BM1380, ~1.6 GH/s @ 200 MHz), not U2 or a
  Block Erupter. Healthy; nonces spread clean across 2^32; ~1/e of random works
  yield no nonce (textbook diff-1 Poisson).

- **The ANU frequency lever WORKS — verified on hardware.** `build_anu_set_freq`
  (shipped flagged *UNVERIFIED, no U1 in hand*) drives a real clock change. A
  **safe underclock sweep** (200 → 150 → 100 MHz, all at/below stock, restore-on-
  exit) scaled hashrate linearly: 1580 / 1185 / 798 MH/s = **7.90 / 7.90 / 7.98
  MH/s per MHz**. A 2.00× frequency change gave a 1.98× hashrate change — the clock
  physically moves, proven by direct measurement (no compile-time-constant trap
  like the Jalapeño census `FREQUENCY`). **Double-confirmed:** the read-reg echoed
  the exact PLL multiplier written (`rdreg 8007/8005/8003` = m 7/5/3 = 200/150/100).

- **Next frontier — overclock.** Going *above* stock needs a thermal watch, but
  the U1 has **no serial temperature readout**, so it needs an **external** probe
  — a natural convergence with milieu's ambient×unit study (a Govee beside the
  unit as the thermal watch). A deliberate, guarded session for another day.

## 2026-08-22 — second unit, cross-validation, firmware source truth, broader scope

The project's second physical Jalapeno arrived, the frequency-override mystery
got a source-level correction, and the toolkit formally broadened past the
Jalapeno.

- **Second unit (board `005794`, the sacrificial one) — first contact.** Alive,
  deterministic (24/24 and 32/32 identical-work reps, zero compute errors), and
  by its own census a *healthier bin* than the reference unit (29 engines @
  ~214 MHz / ~6.17 GH/s vs 27 @ ~200 MHz / ~5.3). It arrived physically opened
  (feared a repair job); first contact refutes that. **Cross-unit ground
  truth:** its determinism nonce set `[143194809, 743894015, 2919571808]` is
  bit-for-bit identical to the reference unit's for the same work — two
  independent units agree exactly. Matched 30-min and 4-hour characterizations
  run; NVRAM signed and power-cycle persistence confirmed.

- **CORRECTION — the frequency override was mis-explained.** Reading the open
  firmware (`luke-jr/BitForce_SC`) overturns the earlier "thermal-hover loop"
  story (see the 2026-08-15 Phase 3 entry below). A `ZVX` write looked inert
  for three real reasons: (1) the census `FREQUENCY:` field is a **compile-time
  constant** — it can never show a live change, so "stayed 189 MHz" was no
  evidence at all; (2) the `ZVX` "all chips" broadcast (`0xFF`) masks to the
  3-bit chip-address field → reaches **chip 7 only, never chip 3**; (3) a bare
  `0x60` write omits the reg-`0x61` clock-enable relatch. There is event-driven
  re-assert (low engine count / thermal recovery), but no continuous hover.
  **So the sweep is not closed — it needs custom firmware,** and the patch
  points are now known (freq table `std_defs.c:15`, kill the boot auto-OC ramp,
  fix the broadcast, add the relatch). Route: JTAG dump + reflash on 005794
  (MCU confirmed **AT32UC3A1256**, JTAG-only, no security fuse set in source).

- **Scope broadened (name kept).** The device-agnostic core
  (`characterize_source`, `health`, `NonceSource`) now spans a fleet. Added the
  **Icarus protocol module** (Block Erupter = device #2;
  `build_work`/`parse_nonce`/`linear_scan_hashrate`), the **Antminer U ANU
  frequency command** (`build_anu_set_freq` + `crc5` + the PLL search,
  byte-exact from cgminer — the clock lever the Jalapeno denied us), and a
  **Govee H5075 ambient decoder** (independent room temperature for the thermal
  work). GekkoScience NewPac (BM1387, per-chip nonce attribution) protocol spec
  researched and ready to build for its arrival. README / CLAUDE / pyproject /
  GitHub framing updated to the broader "retro mining silicon characterization
  lab."

## 2026-08-15 (Phase 3) — frequency lever: ZVX handshake solved, firmware overrides the clock

Attempted the frequency-set lever (`ZVX`/`ZKX`, found in the open
firmware). Built the commands (`bfl_asic/protocol/freq.py`, guarded to
the firmware's 10 known-good words `ASIC_FREQUENCY_WORDS`) and hit, then
solved, a real host-side protocol bug.

- **`ZKX` (get) is unimplemented in firmware** — always returns `FREQ:0`.
  Observe frequency via the `ZCX` census `FREQUENCY` field instead.
- **`ZVX` (set) second stage is length-prefixed.** Early attempts got
  `ERR:INVALID DATA`. Root cause, found by reading the firmware's
  `USB_wait_stream` (USBProtocol_Module.c): the first payload byte is a
  **length indicator**, not data. A bare 4 bytes was read as "expect
  255", never reached end-of-stream -> `invalid_data`. Fixed: payload is
  `[0x04][4 LE bytes]`. Verified on hardware -> `ZVX` returns `OK`,
  `set_freq_factor` True.
- **But the firmware overrides the setting.** Even the slowest word
  (0x0000) left the census pinned at 189 MHz with zero compute errors.
  The firmware's own thermal-hover frequency management re-asserts its
  word (or the raw 0x60 register write needs a PLL-reinit trigger `ZVX`
  doesn't issue). So a frequency sweep is **not achievable via `ZVX` on
  this unit's firmware** — the chip keeps itself at 189 MHz regardless.

**Still planned:** the frequency / error-rate sweep on the **sacrificial
unit (05794, ~Aug 22)**. A different unit may run different firmware, and
it is the safe target for the more invasive approaches real clock control
would need (disabling the firmware frequency loop, or a reflash). No harm
to the original unit — it is unchanged at 189 MHz.

## 2026-08-15 (pm) — probe commands, a queued-protocol bug, first silicon characterization

Phase 1 increment 2 plus the first real characterization run.

- **Undocumented probe commands (`protocol/probe.py`).** `ZJX`/`ZUX`/
  `ZSX` are defined in cgminer's header but never sent by it. Added
  builders + lenient parsers, `BFLDevice.get_firmware/read_note/
  write_note` (the NVRAM write emits an `NVRAMWriteWarning` and the CLI
  gates it behind `--confirm-nvram-write`), and a read-only
  `scripts/hw/probe_commands.py`. On the real unit: `ZJX` returns a bare
  `1.0.0` (no framing/OK); `ZUX` returns the sentinel `MEMORY EMPTY` for
  a blank scratchpad. `ZSX` (write) was never fired. Simulator + parsers
  updated to match; `MEMORY EMPTY` maps to `""`.

- **Real queued-protocol bug fixed.** `QueuedWorkSession.submit()`
  rejected `INPROCESS:<n>`, but real firmware uses that as a valid ZNX
  accept ("n jobs in process") under load. cgminer's `isokerr()` treats
  any reply without `ERR:` as OK; `submit()` now does the same. Same
  family of artifact as the documented 42-limit. TDD'd with a stub
  transport.

- **Real-hardware protocol gotcha.** Driving the queued path needs an
  input-buffer flush before every command — the firmware is chatty
  (multi-line `ZCX`, `INPROCESS:0` result prefixes) and unflushed
  sequential reads desync, so a stale status line gets read as the next
  reply (surfaced as bogus `INPROCESS`/`QUEUE FULL`). `JOBS IN QUEUE`
  reads ~0 even mid-scan, so it can't drive backpressure; bound in-flight
  jobs by submitted-minus-drained instead. `characterize.py` drives the
  protocol directly for these reasons.

- **First silicon characterization** (fan AUTO, 30 min, model-free —
  `docs/characterization/`). Determinism: **32/32 identical reps ->
  identical nonces**, no compute errors at nominal cooling. Throughput:
  2199 jobs, 0 errors, 2218 nonces, ~1.22 job/s (USB/protocol-bound).
  Per-job winner count is **Poisson(λ≈1.01)** -> the device scans the
  full 2³² space per job (diff-1). Thermal: 36 °C -> 45 °C plateau under
  auto fan. VCC1 anomaly captured: 3.03 V idle first-read -> ~3.7 V under
  load (ADC settling). The deliberate under-cooling error-vs-temperature
  sweep was deferred to a supervised session.

## 2026-08-15 — ZCX device census + real-hardware topology discovery

Reframed the device from "hash source" (settled: it only ever returns
winning nonces, never digests) to two untapped angles — undocumented
protocol surface and silicon forensics — and started a 4-phase
extraction roadmap. This is Phase 1, increment 1.

- **`ZCX` device census, first-class.** `parse_details` now yields a
  `DeviceDetails` with typed, case-/dash-insensitive accessors
  (`firmware`, `engines`, `frequency`/`frequency_mhz`, `mining_speed`,
  `critical_temperature`, `xlink_*`, `processors` → `list[Processor]`,
  `jobs_in_queue`); unrecognised firmware fields are preserved in
  `.fields`. Added `BFLDevice.get_details()` (drains the multi-line
  reply through `OK`), a `device details` CLI backed by a pure
  `_render_census` helper, and a strictly read-only capture script
  `scripts/hw/read_details.py`. Simulator upgraded from the old
  `ENGINES: 1` stub to a realistic reply with a configurable engine
  count. All TDD (16 new tests).

- **cgminer never sends `ZJX`/`ZSX`/`ZUX`.** They're defined in
  `driver-bflsc.h` but dead code — so their wire format is genuinely
  unknown, and the firmware version everyone quotes actually comes from
  the `ZCX` `FIRMWARE:` field, not `ZJX`. That reshaped Phase 1: the
  census (grounded) subsumes the firmware query; the three unused
  commands become undocumented probes for increment 2.

- **The real unit reports more than any reference documents.** Captured
  from the physical Jalapeno (firmware 1.0.0): `ENGINES: 26`, a real
  `FREQUENCY: 189 MHz` (the cgminer reference build returns
  `[UNKNOWN]`), a per-processor breakdown `PROCESSOR 3: 12 engines @
  199 MHz` / `PROCESSOR 7: 14 engines @ 200 MHz` (sparse indices ⇒
  fused-off cores; 12+14 = 26), `MINIG SPEED: 5.15 GH/s` (firmware's own
  typo), and `CRITICAL TEMPERATURE: 0`. The per-processor topology is
  the Phase-2 engine map handed over directly; the populated frequency
  reopens Phase-3 clock characterization.

## 2026-05-16 — n=4M bound, n_val correctness fix, Tier B closeout

Second pass the same day, after the public dataset went live.

- **n=4M indistinguishability probe (HF cpu-xl) landed clean** — acc
  0.500065, 95% CI [0.49897, 0.50116] (brackets 0.5), controls
  positive_ok/negative_ok, 5.18 h, rc=0. Folded into `bounded_null`:
  the full-SHA-256 CI-resolution floor tightens from ≈ 0.49 % (n=800k)
  to ≈ 0.22 % (n=4M). Still a bounded null — just a tighter one.
  (`9210524`)
- **Fixed a pre-existing `n_val` inversion bug, globally.** The harness
  reports the distinguisher floor in *advantage* units (`2·acc−1`):
  `floor = 2z·√(0.25/n_val)`. `build_dataset.py:_n_val` inverted the
  *accuracy*-unit form, so the published `n_val` ran ≈ 4× low across
  `learnability_sweep` + `bounded_null`. Now `n_val = (Z/floor)²`
  exactly (the n=4M probe → n_val 800k as it should). Only the derived
  Parquet + card changed; the verified `dataset/source/*.json` evidence
  is untouched. HF dataset republished additively (head `f2256ae`,
  prior revisions retained). (`02223e4`)
- **Tier B closeout.** The long-running Tier B job had loaded the
  *pre-trim* 12-unit plan (the script was trimmed to the 5-seed sweep
  in-bucket *after* launch; the trim only takes on resubmit). The
  5-seed learnability sweep completed and replicates the round-4 cliff
  on the fine grid across all seeds (controls pass every seed). The
  redundant `full_structure×5 / indist / dynamics` tail — already
  deemed redundant on the 2026-05-16 trim, not worth ~20–28 h more
  cpu-xl — was cancelled. Clean SIGTERM: atomic partial flush,
  idempotent `progress.json`, `rc=143`, 16.62 h total. The safety
  design behaved exactly as promised; nothing lost.
- **Durable backup.** All HF state mirrored to gitignored
  `hf_results/`; the load-bearing Tier B sweep + job log + flushed
  `summary.json` + a timing analysis committed under
  `archive/hf-runs/bfl-ml-tierB/` (git-only, not republished). Per-unit
  timing variance is pure shared-`cpu-xl` jitter (4/5 within ~7 %, one
  +39 % noisy-neighbour spike). (`eefeaea`, `31fce3d`, `c21623b`)

## 2026-05-16 — Curated results published as a public HF dataset

Published the verified ML results as a public Hugging Face dataset:
`huggingface.co/datasets/bshepp/round-reduced-sha256-learnability`.

- **Mirrors the `bshepp/pairwise-poisson-algebras` convention** — a
  dataset card with HF frontmatter + Parquet configs + a deterministic
  build script — and adds the one piece that convention lacked: a
  reusable `dataset/publish_dataset.py` (`HfApi.create_repo(
  repo_type="dataset")` + `upload_folder`, public-by-default), the
  dataset analogue of `bfl_asic/ml/publish.py`.
- **`dataset/build_dataset.py`** reads the synced run JSON (BOM-safe)
  into 4 Parquet configs, 83 rows total: `learnability_sweep` (70, the
  round-4 cliff ×5 seeds ×2 tiers), `bounded_null` (7, full-SHA-256
  indistinguishable at n=800k, all `controls_ok`), `dynamics_validated`
  (4, the verified label-prior artifact with the permuted-label control
  carried on every row), `feature_probe` (2). The CI-resolution floor is
  inverted to an exact `n_val` column.
- **Training data deliberately not hosted** — regenerable from a seed,
  consistent with the original spec non-goal. The dataset is the
  curated, controls-verified *evidence*, not the inputs.
- **Honesty held to the project bar.** The card foregrounds the
  negative result, labels the CI floor as non-power, and *surfaces*
  rather than smooths the 1-of-55 marginal post-cliff exceedance (Tier
  A seed 1, round 6, +1.1%, ci_lo 0.5007 — fewer than the ≈2.7 spurious
  one-sided 95% exceedances expected; `learnable` is a queryable
  per-point flag so anyone can check). Framed as personal AI/ML
  exploration, not novel cryptographic research.

A future n=4M indistinguishability result can be folded into
`bounded_null` and re-published with the same two-command refresh.

---

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
- **Tier A dynamics number was an artifact — now VERIFIED.** Re-ran the
  Tier-A dynamics config (seed=0, n=20000, ep=25, widths 1–4) through the
  validated harness (2124 s). Width-1 acc=0.3535, CI [0.339, 0.369],
  above chance 0.25 — **but the permuted-label control scored
  identically (0.3535, same CI)**, so `negative_ok=False`. With the
  seed→tail mapping shuffled the model still gets 0.3535, i.e. it learns
  nothing from the seed and collapses to the most-frequent quantile bin;
  the "+10%" is the non-uniform label prior, not orbit structure. Widths
  2–4 sit at chance (adv ≈ 0). **Verified conclusion: no learnable
  seed→orbit-tail structure at any truncation width.** The prior 0.354
  was a dataset-construction artifact, exactly as the review's §1
  hypothesised — the fixed harness converted a false positive into a
  correct, controlled negative (which is the whole point of the control).
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
| Test count | 857 |
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
- **Frequency sweep / max-stable-clock (Phase 3):** the `ZVX` command works (length-prefixed second stage), but this unit's firmware overrides manual settings — the clock stays pinned at 189 MHz. **Still planned on the sacrificial unit (05794):** try there (different firmware may behave differently), and/or bypass the firmware frequency loop / reflash for real clock control. `ZKX` (get) is unimplemented in firmware (returns 0).
- ASIC-accelerated hash source (swap `SoftwareHashEngine` for device-backed `HashSource` — the randomness battery is already wired to accept it)
- Direct ASIC bus tapping for full hash throughput (bypasses USB bottleneck)
- Firmware work limit workaround (USB power relay for automated power cycling, or direct FPGA/ASIC reset via GPIO)
- VCC1 ADC settling time investigation (add configurable delay between ADC reads)
- Work result polling strategy (test faster polling to catch BUSY→NO-NONCE transition)
- Avalanche side-by-side visualiser — show two near-identical inputs producing wildly different outputs (paired pedagogy with the convergence animation)
- Round-by-round SHA-256 internals viewer — instrument the pure-Python compression in `protocol/work.py` to expose the 8 working variables across all 64 rounds

## Deeper reverse-engineering roadmap

Explicitly **for fun and learning** — no objective, no goals, no deliverables, no ROI test. Some of what follows is not "worth it" by any practical measure; it is here anyway, because the point is the doing and the knowing. (The owner has been called "bloody minded" more than once. This section leans into that.)

**The framing that orders everything:** the interesting limits live in the *firmware*, not the silicon. The BF0005G is a fixed-function SHA-256d engine — there is nothing hidden in the die to unlock. It only ever emits *winning* nonces (never full digests) and it overrides a manual clock, and both are firmware policy. So the deep work is not "find secret powers"; it is **"take total, documented control of a machine built to only ever tell you it won."** Because BFL open-sourced the AVR32 firmware (`luke-jr/BitForce_SC`), most of this is read-the-source-then-confirm, not blind guessing. All invasive steps run on the **sacrificial unit `05794`**; the signed/characterized original `002659` stays pristine.

### Tier 0 — non-invasive (no case opening)
- **FTDI EEPROM dump/analysis** — FT232H carries its own EEPROM (serial `FTWLK8HJ`, VID/PID, strings). Read over USB with `ftdi_eeprom` / FT_Prog. Low payoff (see what BFL programmed), zero risk.
- **The `ZBX` "Custom Command"** — firmware `PROTOCOL_REQ_TEST_COMMAND` (`"B"`, commented *Custom Command*), never exercised. Read the handler, then poke it. The last unexamined corner of the *serial* surface — everything else is fully documented by the firmware source, so there are no unknown serial commands.

### Tier 1 — open the case, read-only
- **Dump the real MCU firmware** — the unit runs an AVR32 (Atmel UC3) controller whose firmware reports fields absent from the 2012 spec, so a later/custom build than the public source. Pull via JTAG or bootloader and **diff against `luke-jr/BitForce_SC`**. Obstacle: the flash-readout fuse may be locked (hard stop — or an excuse to learn voltage glitching). Payoff: know exactly what this silicon runs.
- **Logic-analyzer the MCU↔ASIC SPI bus** — the goldmine. Sniff the SPI between the AVR32 and the ASIC (`0x60` = oscillator control is our one known landmark). Recover the real register / work-load / nonce-readback interface empirically, cross-checked against the source. This reveals *how to drive the clock directly* and how the firmware re-asserts its own word — the reconnaissance that unlocks Tier 2.

### Tier 2 — the payoff tier (sacrificial unit)
- **Custom firmware** — build a modified AVR32 image that (a) disables the thermal-hover frequency override → the max-stable-clock sweep we couldn't reach via `ZVX`, and (b) reports full hash output / exposes raw ASIC access → the actual **hardware hash source** the stats/randomness subsystems always wanted (the winner-only limit is firmware, not silicon). One move, both walls gone.
- **Replace the controller / direct ASIC drive** — bypass the controller entirely: drive the ASIC's SPI from a Pi or FPGA, supplying its power (~1.0 V core / 12 V VMAIN) and clock. Full throughput (no 115200-baud bottleneck), arbitrary difficulty, every hash out — the miner as a raw SHA-256d coprocessor. Serious embedded build; the open firmware provides the interface spec. ("Drop in a faster USB bridge" is the small version; replacing the whole controller is the real one.)

### Tier 3 — the bloody-minded floor
- **Decap and image the die** — by every practical measure, *not worth it*: you destroy the chip and learn nothing the firmware doesn't already tell you (it's a known SHA-256d core). Included precisely **because** it isn't worth it — rosin/acetone or fuming-nitric decap, then a microscope, then a die-shot for the sheer craft of it. If the sacrificial unit ends up truly dead, this is its dignified end: a photograph of the actual silicon that started all of this.

**North star (there isn't one, and that's the point):** no deliverable gates any of this. It runs on curiosity and the pleasure of understanding a machine all the way down — from the serial byte, through the firmware, down the SPI bus, into the register map, and (if the mood strikes) onto a microscope slide.
