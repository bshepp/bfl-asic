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

## Not run (deferred to a supervised session)

The deliberate error-rate-vs-temperature sweep (reducing cooling via a
fixed fan level to push temperature up) was **not** run — it takes the
device out of its self-protecting envelope and should only run with a
human watching. See the hardware-safety notes in `CLAUDE.md`.
