---
license: mit
task_categories:
  - tabular-classification
tags:
  - cryptography
  - sha-256
  - hash-functions
  - round-reduced
  - learnability
  - distinguisher
  - neural-network
  - negative-result
  - reproducibility
  - bounded-null
  - statistical-validation
  - controls
  - sgd-dynamics
  - butterfly-labs
  - asic
language:
  - en
pretty_name: "Round-Reduced SHA-256 Learnability: A Controls-Gated Negative Result"
size_categories:
  - n<1K
configs:
  - config_name: learnability_sweep
    data_files: learnability_sweep.parquet
  - config_name: bounded_null
    data_files: bounded_null.parquet
  - config_name: dynamics_validated
    data_files: dynamics_validated.parquet
  - config_name: feature_probe
    data_files: feature_probe.parquet
---

# Round-Reduced SHA-256 Learnability: A Controls-Gated Negative Result

## TL;DR

A small CNN learns to distinguish **round-reduced** SHA-256 outputs from
random with ~100% accuracy through **3 rounds**, then **collapses to
chance at round 4 and stays there through the full 64 rounds** — a sharp
learnability cliff, replicated across 5 seeds and 2 dataset sizes. Full
SHA-256 is statistically indistinguishable from random to these probes
**at this budget** (a bounded null, not a proof). An apparent
iterated-hash "orbit" signal turned out to be a label-prior **artifact**
— and the experiment's own permuted-label control caught it.

This is a **negative result reported honestly**. It is a personal
AI/ML-capability and reproducibility exploration, **not** new
cryptographic science: a competent distinguisher failing on a hash
function it should fail on is the *expected* outcome. The value here is
the methodology — every claim is gated on positive/negative controls,
and one of those controls is shown in the act of converting a false
positive into a correct negative.

## Dataset Description

This dataset is the distilled, **verified evidence** from a learnability
instrument built on top of the [`bfl-asic`](https://github.com/bshepp/bfl-asic) toolkit (a
codebase for a Butterfly Labs BF0005G "Jalapeno" SHA-256 mining ASIC,
which also contains a numpy-vectorized, `hashlib`-anchored round-reduced
SHA-256 and a controls-gated train/eval harness).

It contains **only the results** — accuracy points, confidence
intervals, control outcomes, verdicts. The synthetic training data is
**deliberately not hosted**: it is exactly regenerable from a seed,
which is cheaper and more reproducible than a multi-gigabyte download.
What you cannot regenerate for free — the curated, controls-verified
conclusions of ~16 CPU-hours of Hugging Face compute — is what lives
here.

Four small Parquet tables, **83 rows total**:

| Config | Rows | What it answers |
|---|---|---|
| `learnability_sweep` | 70 | At how many SHA-256 rounds does a CNN stop being able to tell real from reduced? |
| `bounded_null` | 7 | Is full 64-round SHA-256 distinguishable from random to these probes, at this budget? |
| `dynamics_validated` | 4 | Is iterated-hash orbit-tail length predictable from the seed? (and: is the apparent signal real?) |
| `feature_probe` | 2 | Is the round-4 cliff an artifact of the input feature? |

### Headline findings

1. **A sharp learnability cliff at round 4.** Per-hash TinyCNN
   distinguisher accuracy: rounds 1–3 ≈ **1.000**; round 4 onward ≈
   **0.500**, flat through round 64. The cliff lands at the *same*
   boundary for all 5 seeds (Tier A n=200k ×3, Tier B n=500k ×2) and on
   a finer round grid. Of the **55** post-cliff points, exactly **one**
   has a 95% CI lower bound clearing chance (Tier A seed 1, round 6:
   acc 0.5057, +1.1%, ci_lo 0.5007) — *fewer* than the ≈ 2.7 spurious
   one-sided 95% exceedances expected from 55 points, isolated (rounds
   4/5/8 of that seed are at chance), and below the rounds-1–3 signal
   by ~50×. It is reported, not hidden: `learnable` is a per-point
   `ci_lo > 0.5` flag precisely so this is queryable.

2. **Full SHA-256 is indistinguishable from random — bounded.** Across
   3 seeds at n=800k, best-of-{TinyCNN, linear probe} accuracy is
   0.499–0.501; the 95% CI brackets 0.5 in every seed; `controls_ok`.
   A dedicated indistinguishability probe then **tightens the bound at
   n=4,000,000**: accuracy 0.50006, 95% CI [0.4990, 0.5012] (brackets
   0.5), controls passed — pushing the CI-resolution floor down from
   ≈ 0.49% to **≈ 0.22%**. Verdict: *no structure above ≈ 0.22%*.
   This is a **bounded null at this budget**, explicitly **not** a
   claim that SHA-256 is random.

3. **The dynamics "signal" was an artifact — and the control caught
   it.** Predicting a binned iterated-SHA-256 orbit-tail length from
   the seed gave width-1 accuracy 0.354 (chance 0.25), CI [0.339,
   0.369] — apparently above chance. But the **permuted-label
   negative control scored identically** (0.354, same CI):
   `negative_ok = false`. The model learns nothing from the seed and
   collapses to the most-frequent quantile bin; the "+10%" is the
   non-uniform label prior. **Verified conclusion: no learnable
   seed→orbit-tail structure at any truncation width.** A first,
   under-validated harness reported this as a positive; the fixed
   harness (real Clopper–Pearson CI + permuted-label control)
   converted it into a correct, controlled negative — which is the
   entire point of the control.

4. **The cliff is not feature-bottlenecked.** A per-batch
   deviation-map feature reproduces the same round-4 cliff as the
   per-hash feature (qualitative, coarse floor — see provenance).

## Quick Start

```python
from datasets import load_dataset

# 1. The learnability cliff (the spine)
sweep = load_dataset("bshepp/round-reduced-sha256-learnability",
                      "learnability_sweep")["train"].to_pandas()
print(sweep[sweep.seed == 0][["tier", "rounds", "accuracy",
                              "ci_lo", "ci_hi", "learnable"]])
# rounds 1-3 -> learnable=True (~1.0); rounds >=4 -> learnable=False (~0.5)

# 2. The bounded null on full SHA-256
bn = load_dataset("bshepp/round-reduced-sha256-learnability",
                   "bounded_null")["train"].to_pandas()
print(bn[bn.is_best_model][["seed", "model", "accuracy",
                            "ci_resolution_floor", "conclusion"]])

# 3. The verified dynamics negative: real signal vs the control
dyn = load_dataset("bshepp/round-reduced-sha256-learnability",
                   "dynamics_validated")["train"].to_pandas()
lead = dyn.iloc[0]
print(f"width-1 acc={lead.accuracy:.4f}  "
      f"permuted-label control={lead.permuted_label_accuracy:.4f}  "
      f"negative_ok={lead.negative_ok}")
# identical -> the apparent signal is a label-prior artifact
```

## Methodology (read this before using the numbers)

This dataset is opinionated about honest measurement. Three conventions
matter:

- **Controls gate every verdict.** A "no structure" null is only
  trustworthy if a *positive control* (a low-round model that **must**
  be learnable) did learn, and a *negative control* (random-vs-random,
  or shuffled labels) did **not** beat chance. `controls_ok` /
  `positive_ok` / `negative_ok` are carried on the rows. When a control
  fails, the row's conclusion says so instead of emitting a null.

- **`ci_resolution_floor` is a CI-resolution floor, NOT a power-based
  MDE.** It is the smallest above-chance gain whose 95% accuracy CI
  excludes chance at that eval-set size. For the distinguisher configs
  (`learnability_sweep`, `bounded_null`) the harness reports it in
  *advantage* units (`2·acc−1`): `floor = 2z·√(0.25/n_val)`. "No
  structure" means *none above this floor at this budget* — it is
  **not** a statement that the effect is zero, and **not** a power
  calculation. The `ci_resolution_floor` value is taken **verbatim
  from the run**; every "no structure above X" claim rests on it
  directly.

- **`n_val` is the literal eval-set size.** It is the exact inversion
  of the advantage-unit floor above, `n_val = (z/floor)²`, so e.g. the
  n=4,000,000 indistinguishability probe resolves to `n_val = 800k`.
  Included for transparency alongside `n_train` (the run's dataset
  size).

- **The permuted-label control is the dynamics analog of
  random-vs-random.** Train on shuffled labels; if the shuffled model
  still "beats chance", the apparent signal is a dataset/setup
  artifact. In `dynamics_validated` it fires: that is the headline.

CIs are Clopper–Pearson (exact binomial). Models are deliberately small
(a tiny CNN and a linear probe) on modest data on CPU — this measures
*easy, cheap learnability*, the appropriate first question, not the
limit of what any model could ever extract.

## Dataset Splits

### `learnability_sweep` (70 rows)

Round-reduced vs full SHA-256 distinguisher accuracy as a function of
the number of compression rounds. Real SHA-256 vs an `R`-round-reduced
variant, per-hash feature, TinyCNN. 5 seeds across 2 tiers.

| Column | Type | Description |
|---|---|---|
| `tier` | str | `A` (n_train=200k) or `B` (n_train=500k, finer round grid) |
| `n_train` | int | Training examples |
| `n_val` | int | Eval examples (exact inversion of the advantage-unit CI floor) |
| `seed` | int | RNG seed (0–2 for A, 0–1 for B) |
| `rounds` | int | SHA-256 compression rounds (1–64) |
| `accuracy` | float | Validation accuracy (chance = 0.5) |
| `advantage` | float | `2·accuracy − 1` |
| `ci_lo`, `ci_hi` | float | 95% Clopper–Pearson CI on accuracy |
| `ci_resolution_floor` | float | Smallest CI-resolvable gain at this `n_val` |
| `learnable` | bool | `ci_lo > 0.5` (above chance with 95% confidence) |

### `bounded_null` (7 rows)

Full 64-round SHA-256 vs random. Six rows: one per (seed, model) for
the n=800k full-structure sweep, plus the standalone n=4,000,000
indistinguishability probe that tightens the CI-resolution floor to
≈ 0.22%. `conclusion` is verbatim from the harness.

| Column | Type | Description |
|---|---|---|
| `experiment` | str | `full_structure` or `indistinguishability` |
| `seed` | int | RNG seed |
| `model` | str | `tiny_cnn` or `linear_probe` |
| `rounds` | int | 64 (full SHA-256) |
| `n_train`, `n_val` | int | Dataset size n / eval examples. full_structure: 800k / 160k. indistinguishability: 4,000,000 / 800k |
| `accuracy`, `advantage` | float | Validation accuracy and `2·acc−1` |
| `ci_lo`, `ci_hi` | float | 95% Clopper–Pearson CI |
| `ci_resolution_floor` | float | CI-resolution floor (full_structure ≈ 0.0049; indistinguishability ≈ 0.0022) |
| `is_best_model` | bool | Best-accuracy model for this seed |
| `controls_ok` | bool | Positive **and** negative control passed |
| `positive_ok`, `negative_ok` | bool | Individual control outcomes |
| `structure_detected` | bool | `ci_lo > 0.5` (always False here) |
| `conclusion` | str | Verbatim harness verdict |

### `dynamics_validated` (4 rows)

Predicting a binned iterated-SHA-256 orbit-tail length from the seed,
vs how many seed bytes the model sees (`trunc_width_bytes`). The
permuted-label control fields are **constant across rows on purpose** so
one table answers "is this signal real?".

| Column | Type | Description |
|---|---|---|
| `seed`, `n_train`, `epochs`, `n_bins` | int | Run config (0, 20000, 25, 4) |
| `trunc_width_bytes` | int | Seed bytes the model sees (1–4) |
| `accuracy` | float | Validation accuracy (chance = 0.25) |
| `chance` | float | `1 / n_bins` |
| `advantage` | float | `accuracy − chance` |
| `ci_lo`, `ci_hi` | float | 95% Clopper–Pearson CI |
| `ci_resolution_floor` | float | CI-resolution floor at this `n_val` |
| `permuted_label_accuracy` | float | Shuffled-label control accuracy |
| `permuted_label_ci_lo/hi` | float | Control 95% CI |
| `negative_ok` | bool | False ⇒ the apparent signal is an artifact |
| `verdict` | str | Plain-language conclusion |

### `feature_probe` (2 rows)

Is the round-4 cliff an artifact of the input feature? `per-hash` is
exact (HF Tier B seed0); `per-batch` is a local n=2M probe whose CI
floor is coarse (~0.10, few per-batch examples), recorded qualitatively
and labelled with its provenance.

| Column | Type | Description |
|---|---|---|
| `feature` | str | `per-hash` or `per-batch` |
| `n_train` | int | Training examples |
| `rounds_learnable` | str | JSON list of rounds with `ci_lo > 0.5` |
| `rounds_at_chance` | str | JSON list of probed rounds at chance |
| `ci_resolution_floor` | float | CI-resolution floor (coarse for per-batch) |
| `conclusion` | str | Plain-language finding |
| `provenance` | str | Exact-vs-qualitative source and caveats |

## Reproduction

The data is regenerable from a seed — that is why none of the *inputs*
are hosted. The results above were produced by the `bfl-asic` toolkit's
`ml` subsystem (numpy round-reduced SHA-256 anchored to `hashlib`,
TinyCNN/linear-probe distinguishers, a controls-gated harness), run on
Hugging Face Jobs (`cpu-xl`, ~16 CPU-hours total).

**Source code:** [github.com/bshepp/bfl-asic](https://github.com/bshepp/bfl-asic) (MIT) — the `bfl_asic/ml/` subsystem and `dataset/build_dataset.py`.

```bash
git clone https://github.com/bshepp/bfl-asic
cd bfl-asic
pip install -e ".[ml]"              # PyTorch is isolated behind [ml]

# Regenerate the spine (one seed, scaled down for a laptop):
bfl-asic ml run sweep --seed 0 --n 20000 --epochs 10
bfl-asic ml report runs/ml/<timestamp>/sweep_seed0.json

# Rebuild these exact Parquet tables from the shipped source JSON
# (dataset/source/ travels with the repo — no external data needed):
python dataset/build_dataset.py     # deps: pandas, pyarrow
```

This HF dataset repo is itself self-contained: `git clone` it, `pip
install pandas pyarrow`, run `python build_dataset.py`, and the four
Parquet rebuild from the bundled `source/` JSON — no external data, no
GitHub checkout required.

The harness is deterministic: the same seed reproduces the same curve.
The `dynamics_validated` table is the output of the *fixed* harness
(real Clopper–Pearson CI + permuted-label control); the earlier
under-validated harness is preserved in the toolkit's history as the
honest record of the false positive that the control corrected.

## Limitations

- **Negative results, by design.** A small/cheap distinguisher failing
  on full SHA-256 is expected; absence of evidence here is **not**
  evidence that SHA-256 has no structure. The bounded null is bounded.
- **Budget-bounded.** Small models, modest `n`, CPU. This measures
  easy, cheap learnability — the right *first* question, not a ceiling.
- **`ci_resolution_floor` is not a power calculation.** See
  Methodology. Do not read it as a minimum detectable effect.
- **Multiple comparisons are not corrected.** Per-point 95% CIs are
  reported raw; across ~80 rows a small number of one-sided
  exceedances are expected by chance (and observed — see Finding 1).
  Treat `learnable` / `structure_detected` as per-point flags, not
  family-wise significance.
- **Not novel cryptographic research.** This is a personal AI/ML
  capability and reproducibility exploration; its contribution is
  methodological transparency, not a new attack or a security claim.

## Citation

```bibtex
@dataset{sheppard2026sha256learnability,
  title  = {Round-Reduced SHA-256 Learnability: A Controls-Gated
            Negative Result},
  author = {Sheppard, B.},
  year   = {2026},
  publisher = {Hugging Face},
  url = {https://huggingface.co/datasets/bshepp/round-reduced-sha256-learnability},
  note = {Code: https://github.com/bshepp/bfl-asic}
}
```

## License

MIT — see the [`bfl-asic` repository](https://github.com/bshepp/bfl-asic/blob/master/LICENSE).
