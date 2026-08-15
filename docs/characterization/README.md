# Jalapeno silicon characterization — 2026-08-15

Model-free characterization of the physical BF0005G Jalapeno (firmware
`1.0.0`) captured with `scripts/hw/characterize.py`, fan on firmware
**AUTO** management the whole run. Raw data: [`run-2026-08-15.json`](run-2026-08-15.json).

"Model-free" means every metric below needs no assumption about the
device's exact hashing or difficulty target — only counts, timing,
repetition, and sensor reads. 30-minute run, 2199 jobs submitted.

## Baseline

| Field | Value |
|-------|-------|
| Device | BitForce SHA256 SC 1.0 |
| Firmware | 1.0.0 |
| Engines | 27 |
| Frequency | 189 MHz |
| Processors | #3: 13 engines @ 198 MHz, #7: 14 engines @ 200 MHz |
| Mining speed (firmware) | 5.34 GH/s |
| Critical temperature | 0 (unset) |

## Determinism — no hardware compute errors

The same work unit was submitted **32 times**; all 32 returned the
**identical** nonce set `[143194809, 743894015, 2919571808]`
(`deterministic: true`, 1 distinct set). Identical input yielding
identical output across every repetition means no silicon compute errors
were observed at nominal (auto-fan) cooling. This needs no hash model —
it is pure repetition.

## Throughput

| Metric | Value |
|--------|-------|
| Elapsed | 1800 s |
| Jobs submitted / completed | 2199 / 2194 |
| Submit errors | 0 |
| Nonces found | 2218 |
| Submits per second | 1.22 |
| Nonces per second | 1.23 |

Throughput is **USB/protocol-bound, not hash-bound**: each job is one
submit + drain round-trip, and a full 2³² scan finishes well inside that
window. This is the known USB bottleneck, quantified.

## Winner count is Poisson(≈1) — full-range diff-1 scanning

Nonces returned per job, versus a Poisson distribution with the observed
mean λ = 2218/2194 = **1.011**:

| Nonces/job | Observed | Poisson(1.011) expected |
|-----------:|---------:|------------------------:|
| 0 | 775 | 798 |
| 1 | 814 | 807 |
| 2 | 447 | 408 |
| 3 | 127 | 138 |
| 4 | 26 | 35 |
| 5 | 5 | 7 |

The close match confirms the device scans the **entire** 2³² nonce space
per job and returns every winner (mean ~1 winner per scan is exactly the
diff-1 expectation), rather than stopping at the first hit.

## Nonce-value distribution

2218 winning nonce values across the 32-bit space, 64 equal bins: broadly
**uniform** (bin counts 21–63, mean ~35), with two mild excess bins
(~+4σ) that could hint at scan-order structure. No clear 27-engine or
2-processor partition is resolvable at this sample size — engine mapping
(Phase 2) will need a longer collection.

## Thermal / electrical (32 samples over 30 min)

- **Temperature**: 36 °C at start → plateau at **45 °C** by ~20 min.
  Comfortably cool under auto fan; the device never approached any
  thermal limit.
- **Reported mining speed** drifts down slightly with temperature
  (5.33 → 5.29 GH/s) — a small, real thermal effect.
- **Frequency** and **engine count** stayed constant (189 MHz, 27
  engines) throughout this continuous run. The 26↔27 / 12↔13 wobble seen
  elsewhere occurs across separate connections, not within a run.
- **VCC1 anomaly captured**: 3.03 V on the first (idle) read, then
  ~3.66–3.74 V for the rest of the run. Consistent with an ADC
  settling/first-read effect rather than a real rail drop. VCC2 steady
  ~1.00 V; VMAIN ~11.0–11.6 V (12 V rail, noisy).

## Engine-mapping collection — 4 h (2026-08-15)

Ran `characterize.py --duration 14400 --bins 256` on auto fan to try to
resolve the 27-engine / 2-processor structure. Raw data:
[`engine-map.json`](engine-map.json).

Reliability at scale (this is the headline):

| Metric | Value |
|--------|-------|
| Duration | 4 h |
| Jobs completed | 17 668 |
| Submit errors | 0 |
| Nonces | 17 726 |
| Determinism (end of run) | TRUE (24/24 identical) |
| Engines / frequency | steady 27 / 189 MHz |
| Temperature | 38–47 °C (auto fan) |

Four hours of continuous hashing with **zero submit errors and zero
compute errors**, per-job winner count again **Poisson(≈1.0)** at 8× the
30-minute sample. This is a very healthy 2013 miner.

Engine mapping — **negative result, by construction.** The 256-bin nonce
histogram is essentially uniform (coarse 16-bin view flat within ±7 %;
CV 0.137 vs a Poisson-uniform 0.120). A few fine bins are hot outliers
(one at ~+9σ), most plausibly an artifact of the low-entropy synthetic
work submitted rather than engine structure.

The deeper point: an **aggregate value-histogram cannot resolve engine
partitions**. If the 27 engines each scan a different contiguous
sub-range, their winning nonces still sum to a uniform whole — the
partition is invisible in aggregate. A histogram can only expose a
*dead* region (an under-represented band), and there are none. So this
run confirms **all 27 engines are alive and collectively cover the nonce
space**, but Phase-2 engine mapping needs a different signal — per-nonce
timing (which engine reports when in the scan), selectively disabling
engines, or high-entropy work with a per-engine tag (the v2 result format
carries a CHIP field, but this SC 1.0 firmware is v1 and omits it).

## Temperature sweep (supervised, 2026-08-15)

Ran `scripts/hw/temp_sweep.py` with a 65 °C hard ceiling, fan stepped
3 → 2 → 1 → 0 under continuous load, human supervising. Raw data:
[`temp_sweep.json`](temp_sweep.json). Result — **inconclusive on
error-onset, but a clear thermal finding**:

| Fan level | Temp reached | Error rate |
|-----------|--------------|-----------:|
| 3 | 33–35 °C | 0.000 |
| 2 | 36–37 °C | 0.000 |
| 1 | 38–39 °C | 0.000 |
| 0 (off) | 39–41 °C | 0.000 |

- **Zero hardware errors at every step** (identical-work nonce sets never
  diverged); engines steady at 27, frequency steady at 189 MHz, mining
  speed drifting only 5.34 → 5.31 GH/s.
- **The device won't get hot.** Even with the fan fully **off** under
  continuous load it peaked at ~41 °C — cooler than the 45 °C plateau of
  the 30-min auto-fan run (which simply ran longer). The ceiling was
  never approached; it aborted nothing.
- So we cannot reach the error-onset temperature by removing cooling
  alone under normal desk conditions — this unit is thermally
  over-provisioned for its ~5.3 GH/s workload. Pushing it into an
  erroring regime would need blocked airflow, elevated ambient, or a much
  longer fan-off soak to find true equilibrium (the fan-0 phase here was
  only ~2 min). That is itself a useful result: **no thermal errors are
  reachable in ordinary operation.**
