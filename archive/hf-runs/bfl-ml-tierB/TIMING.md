# Tier B sweep — per-unit wall-clock timing

Source: `job_6a086568.log` (HF job `6a086568e48bea4538b9fba5`, cpu-xl,
`run_ml_tier.py --tier B`). Snapshot taken while the job was still on
`full_structure_seed0` (the 5 sweep units had completed).

**The 5 sweep units are a computationally identical workload** — same
round list `[1,2,3,4,5,6,8,10,12,16,20,24,32,40,48,56,64]`, `n=500_000`,
`epochs=30`, `tiny_cnn`. Only the RNG seed differs, and the seed changes
*which* data/weights are drawn, **not the amount of compute**. So every
second of spread below is HF infrastructure variance, not algorithmic.

| unit         | seconds  | hours | vs fastest |
|--------------|----------|-------|------------|
| sweep_seed4  | 10,323.6 | 2.87  | — fastest  |
| sweep_seed1  | 10,581.5 | 2.94  | +2.5%      |
| sweep_seed0  | 10,855.7 | 3.02  | +5.2%      |
| sweep_seed3  | 11,583.6 | 3.22  | +12.2%     |
| sweep_seed2  | 15,088.3 | 4.19  | +46.2%     |

- sum 58,432.7 s; **mean 11,686.5 s (3.25 h)**, **median 10,855.7 s
  (3.02 h)** — mean > median, right-skewed by one outlier.
- **sample σ ≈ 1,959 s, CV ≈ 16.8%** over all five.
- Excluding `sweep_seed2`: the other four span **10,323.6–11,583.6 s**
  (±~7%, **CV ≈ 5%**). `sweep_seed2` alone is **+39%** over that
  4-unit mean.

## Interpretation

Four of five runs cluster tightly; `sweep_seed2` is a single +39–46%
spike, after which the host returned to the tight band. That signature —
identical workload, one isolated slow window, fast before and after — is
**noisy-neighbor contention on shared `cpu-xl`** (CPU time-slice /
memory-bandwidth contention, possibly turbo or thermal throttling),
*not* a property of seed 2's data.

Practical consequence: extrapolating the remaining (redundant)
`full_structure`×5 / `indistinguishability` / `dynamics` tail must use a
worst-case per-unit cost, not the mean — `full_structure` runs at
`n=800_000` (larger than the sweep's `n=500_000`), and a single
seed2-style contention window adds ~40% on top. Estimates beyond a few
units out are low-confidence by nature on shared infra.
