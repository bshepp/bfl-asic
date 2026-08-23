---
license: mit
language:
  - en
pretty_name: "BFL Jalapeño: Two-Unit Characterization & a Serial-Number Production Census"
tags:
  - butterfly-labs
  - jalapeno
  - sha-256
  - asic
  - bitcoin-mining
  - hardware-characterization
  - reverse-engineering
  - serial-numbers
  - german-tank-problem
  - dead-core-detection
  - retrocomputing
  - ftc
size_categories:
  - n<1K
configs:
  - config_name: units
    data_files: units.parquet
  - config_name: characterization
    data_files: characterization.parquet
  - config_name: cross_unit_determinism
    data_files: cross_unit_determinism.parquet
  - config_name: production_census
    data_files: production_census.parquet
---

# BFL Jalapeño: Two-Unit Characterization & a Serial-Number Production Census

## TL;DR

Two **Butterfly Labs BF0005G "Jalapeño"** SHA-256 mining ASICs from 2013,
measured model-free in 2026. Fed identical work, both units return the
**bit-for-bit identical winning-nonce set** `[143194809, 743894015,
2919571808]` — ground-truth proof both still compute SHA-256d correctly, 13
years on — yet they **bin differently** (27 engines @ ~200 MHz vs 29 @ ~214).
Both are error-free and fully deterministic over hours of sustained work.

Separately, a **serial-number production census**: from nine confirmed serials
(highest = `025327`), the German-tank estimator puts total production at
**~28,000 units built ± ~3,000** (floor ≥ 25,327). Serials count units
*manufactured* — so the gap between that and what Butterfly Labs actually
shipped is the FTC fraud case, quantified.

This is **honest measurement and hardware archaeology**, not a security or
cryptographic claim. It exists because this data exists nowhere else.

## Dataset description

Distilled, verified evidence from the [`bfl-asic`](https://github.com/bshepp/bfl-asic)
toolkit (MIT). Four small tables:

| Config | Rows | What it holds |
|---|---|---|
| `units` | 2 | Per-unit `ZCX` census + identity (engines, per-processor topology, clock, firmware) |
| `characterization` | 3–4 | Per sustained-work run: throughput, determinism, thermal plateau, dead-core verdict |
| `cross_unit_determinism` | 2 | The identical fixed work → identical winning nonces on both units |
| `production_census` | 9 | The confirmed serial numbers behind the German-tank estimate |

The raw characterization runs live in the toolkit repo
(`docs/characterization/`) and are regenerable via
`scripts/hw/characterize.py`; the serials are confirmed from photographs. What
this dataset adds is the *curated, cross-checked* distillation.

> **Note:** `characterization` is 3 rows at first publish (both units' 30-min
> runs + the reference unit's 4-hour run); the sacrificial unit's matched
> 4-hour run is added on completion, making it 4.

## Headline findings

1. **Cross-unit ground truth.** Identical fixed work → the identical
   winning-nonce set on both physical units (32/32 reps each, zero divergence).
   Because which nonces win is a property of the *work*, two independent units
   agreeing bit-for-bit is direct evidence both compute SHA-256d correctly and
   scan the full 2³² space. The extra engines just get there faster.
2. **Real binning variation.** `002659` self-reports 27 engines at ~200 MHz
   (~5.3 GH/s); `005794` reports 29 at ~214 MHz (~6.17 GH/s) — same architecture,
   different factory bin (the sparse processor indices 3 and 7 are constant:
   fused-off cores at the same positions).
3. **Exceptional reliability.** Zero compute errors across every run (30-min,
   4-hour, and a supervised temperature sweep); per-job winner count Poisson(~1)
   throughout; thermally over-built (won't error even fan-off on a desk). Both
   units read HEALTHY on dead-core detection.
4. **~28,000 units built.** German-tank estimate over 9 confirmed serials
   (min 2,659, max 25,327): `25,327 + (25,327−2,659)/8 ≈ 28,160` (MVUE
   cross-check ≈ 28,140), floor ≥ 25,327, standard error ≈ ±3,000. Serials count
   units manufactured, not shipped.

## Quick start

```python
from datasets import load_dataset

# Two units agree bit-for-bit on the winning nonces
xu = load_dataset("bshepp/bfl-jalapeno-characterization",
                  "cross_unit_determinism")["train"].to_pandas()
print(xu[["board_serial", "reps", "nonce_set"]])
# both rows: nonce_set == "[143194809, 743894015, 2919571808]"

# The production census (recompute the estimate from the serials)
pc = load_dataset("bshepp/bfl-jalapeno-characterization",
                  "production_census")["train"].to_pandas()
s = sorted(int(x) for x in pc["serial"])
k, lo, hi = len(s), s[0], s[-1]
print(f"k={k} min={lo} max={hi}  est ~ {round(hi + (hi-lo)/(k-1))}")
```

## Method notes

- **Model-free.** Every metric needs no assumption about the device's exact
  hashing — only counts, timing, repetition, and sensor reads. Determinism =
  identical work resubmitted N times and compared; a divergence would be a
  hardware compute error. Dead-core health = a per-bin Poisson test flagging
  cold bands in the winning-nonce histogram.
- **The German-tank estimate is a point estimate with wide error bars.** Nine
  serials is a small sample (SE ≈ N/k ≈ ±3k). It assumes serials are roughly
  contiguous and uniformly sampled; real production may involve batches, gaps,
  or numbering shared with other BFL products. A confirmed serial above 25,327
  (raises the ceiling) or below 2,659 (pins the start) would tighten it most.
- **Serials count units built, not shipped or surviving.** The FTC's case was
  that Butterfly Labs manufactured machines and largely did not deliver them
  (allegedly self-mining with customers' hardware; ~$50M in orders; $38.6M
  settlement, 2016). BFL's public "50,000+ across five generations" claim was
  found undocumented. So a serial-indexed count is a *manufactured* figure.

## Reproduction

```bash
git clone https://github.com/bshepp/bfl-asic && cd bfl-asic
pip install pandas pyarrow
python dataset-jalapeno/build_dataset.py    # rebuilds the four Parquet tables

# Regenerate a characterization run on real hardware (opt-in; needs a device):
python scripts/hw/characterize.py --port COM5 --duration 1800 --out run.json
```

The four Parquet rebuild from the bundled `source/` JSON with no external data.

## Limitations

- **Descriptive measurement, not a claim.** This characterizes specific
  hardware; it is not cryptographic science and makes no security claim.
- **n = 2 units.** Binning "variation" is two data points, not a distribution.
- **The census is an estimate.** See Method notes — bounded by a small sample
  and a contiguity assumption.

## Citation

```bibtex
@dataset{sheppard2026jalapeno,
  title  = {BFL Jalapeño: Two-Unit Characterization and a
            Serial-Number Production Census},
  author = {Sheppard, B.},
  year   = {2026},
  publisher = {Hugging Face},
  url = {https://huggingface.co/datasets/bshepp/bfl-jalapeno-characterization},
  note = {Code: https://github.com/bshepp/bfl-asic}
}
```

## License

MIT — see the [`bfl-asic` repository](https://github.com/bshepp/bfl-asic/blob/master/LICENSE).
