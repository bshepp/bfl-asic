#!/usr/bin/env python3
"""Build the curated, verified HF dataset tables from the synced run JSON.

Mirrors the convention of the author's other HF dataset
(`bshepp/pairwise-poisson-algebras`): a deterministic script that reads
the curated result JSON shipped in `source/` and emits one Parquet
table per config, sitting next to the dataset card (README.md) in this
directory. The `source/` JSON is the exact, verified output of the HF
runs that produced the published numbers — it travels with the repo so
this script runs on a fresh clone with no external data.

Only *verified* results go in (controls passed, or — for the dynamics
negative — the permuted-label control actively fired). The synthetic
training data itself is NOT hosted: it is regenerable from a seed, which
is cheaper and more reproducible than a download. This dataset is the
distilled *evidence*, not the inputs.

Run:  python dataset/build_dataset.py
Deps: pandas, pyarrow  (pip install pandas pyarrow)
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
HF = SCRIPT_DIR / "source"  # curated run JSON shipped with the repo
_Z = 1.959963984540054  # 97.5th pct of N(0,1); matches the harness


def _load(path: Path) -> dict:
    # utf-8-sig: tolerate a Windows BOM on synced artifacts.
    with io.open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def _n_val(floor: float) -> int:
    """Invert the distinguisher CI-resolution floor to the eval-set size.

    The harness reports the distinguisher floor in *advantage* units
    (2*acc-1), i.e. ``floor = 2 * Z * sqrt(0.25 / n_val)`` (harness.py),
    so the exact inversion is ``n_val = (Z / floor)**2``. This is the
    literal eval-set size for every distinguisher config
    (``learnability_sweep``, ``bounded_null``); the dynamics config
    reports its floor directly and does not use this.
    """
    return round((_Z / floor) ** 2)


def build_learnability_sweep() -> pd.DataFrame:
    """#1 the spine: round-reduced SHA-256 distinguisher accuracy vs rounds.

    Real vs round-reduced (compress-function-reduced) SHA-256, per-hash
    feature, TinyCNN. Five independent seeds across two compute tiers.
    """
    rows = []
    sources = [
        ("A", 200_000, HF / "bfl-ml-tierA" / "sweep_seed0.json", 0),
        ("A", 200_000, HF / "bfl-ml-tierA" / "sweep_seed1.json", 1),
        ("A", 200_000, HF / "bfl-ml-tierA" / "sweep_seed2.json", 2),
        ("B", 500_000, HF / "bfl-ml-tierB" / "sweep_seed0.json", 0),
        ("B", 500_000, HF / "bfl-ml-tierB" / "sweep_seed1.json", 1),
    ]
    for tier, n_train, path, seed in sources:
        doc = _load(path)
        for p in doc["points"]:
            lo, hi = p["accuracy_ci"]
            floor = p["min_detectable_advantage"]
            rows.append(
                {
                    "tier": tier,
                    "n_train": n_train,
                    "n_val": _n_val(floor),
                    "seed": seed,
                    "rounds": p["rounds"],
                    "accuracy": p["accuracy"],
                    "advantage": p["advantage"],  # 2*acc - 1
                    "ci_lo": lo,
                    "ci_hi": hi,
                    "ci_resolution_floor": floor,
                    # Above chance iff the 95% CI lower bound clears 0.5.
                    "learnable": bool(lo > 0.5),
                }
            )
    return pd.DataFrame(rows)


def build_bounded_null() -> pd.DataFrame:
    """#4/#2 full SHA-256 (64-round) vs random: a controls-gated null.

    `conclusion` is verbatim from the harness. NOTE: ci_resolution_floor
    is a CI-RESOLUTION floor (smallest gain whose 95% CI clears chance at
    this n), NOT a power-based minimum detectable effect. "no structure"
    means "none above this floor at this budget", not "SHA-256 is random".
    """
    rows = []
    for seed in (0, 1, 2):
        doc = _load(HF / "bfl-ml-tierA" / f"full_structure_seed{seed}.json")
        ctl = doc["controls"]
        bn = doc["bounded_null"]
        for p in doc["points"]:
            lo, hi = p["accuracy_ci"]
            floor = p["min_detectable_advantage"]
            rows.append(
                {
                    "experiment": "full_structure",
                    "seed": seed,
                    "model": p["model"],
                    "rounds": 64,
                    "n_train": 800_000,
                    "n_val": _n_val(floor),
                    "accuracy": p["accuracy"],
                    "advantage": p["advantage"],
                    "ci_lo": lo,
                    "ci_hi": hi,
                    "ci_resolution_floor": floor,
                    "is_best_model": p["model"] == bn["best_model"],
                    "controls_ok": bool(bn["controls_ok"]),
                    "positive_ok": bool(ctl["positive_ok"]),
                    "negative_ok": bool(ctl["negative_ok"]),
                    "structure_detected": bool(lo > 0.5),
                    "conclusion": bn["conclusion"],
                }
            )
    ind = _load(HF / "bfl-ml-tierA" / "indistinguishability.json")
    p = ind["points"][0]
    lo, hi = p["accuracy_ci"]
    floor = p["min_detectable_advantage"]
    rows.append(
        {
            "experiment": "indistinguishability",
            "seed": 0,
            # Dedicated tightening probe: run_sweep([64], seed=0,
            # n=4_000_000, epochs=30, tiny_cnn) on HF cpu-xl. Drives the
            # CI-resolution floor down to ~0.22% (from ~0.49% at the
            # full_structure n=800k budget).
            "model": ind["model"],
            "rounds": 64,
            "n_train": 4_000_000,
            "n_val": _n_val(floor),
            "accuracy": p["accuracy"],
            "advantage": p["advantage"],
            "ci_lo": lo,
            "ci_hi": hi,
            "ci_resolution_floor": floor,
            "is_best_model": True,
            "controls_ok": bool(ind["controls"]["positive_ok"]
                                and ind["controls"]["negative_ok"]),
            "positive_ok": bool(ind["controls"]["positive_ok"]),
            "negative_ok": bool(ind["controls"]["negative_ok"]),
            "structure_detected": bool(lo > 0.5),
            "conclusion": "no structure detected above the detection floor",
        }
    )
    return pd.DataFrame(rows)


def build_dynamics_validated() -> pd.DataFrame:
    """#3 iterated-hash orbit learnability — the VERIFIED negative.

    Predict a binned iterated-SHA-256 orbit-tail length from the seed,
    vs how many seed bytes the model sees. The width-1 point sits above
    chance, but the permuted-label control scores IDENTICALLY: the
    apparent signal is the non-uniform label prior, not orbit structure.
    Those control fields are constant across rows on purpose so a single
    table answers "is this signal real?".
    """
    doc = _load(HF / "dynamics_validated_seed0.json")
    cfg = doc["config"]
    ctl = doc["controls"]
    pl_lo, pl_hi = ctl["permuted_label_ci"]
    rows = []
    for p in doc["points"]:
        lo, hi = p["accuracy_ci"]
        rows.append(
            {
                "seed": cfg["seed"],
                "n_train": cfg["n"],
                "epochs": cfg["epochs"],
                "n_bins": cfg["n_bins"],
                "trunc_width_bytes": p["rounds"],  # generic knob axis
                "accuracy": p["accuracy"],
                "chance": p["chance"],
                "advantage": p["advantage"],  # accuracy - chance
                "ci_lo": lo,
                "ci_hi": hi,
                "ci_resolution_floor": p["min_detectable_advantage"],
                "permuted_label_accuracy": ctl["permuted_label_accuracy"],
                "permuted_label_ci_lo": pl_lo,
                "permuted_label_ci_hi": pl_hi,
                "negative_ok": bool(ctl["negative_ok"]),
                "verdict": (
                    "ARTIFACT: width-1 gain == permuted-label control "
                    "(label-prior, not orbit structure); no learnable "
                    "seed->orbit-tail structure at any width"
                ),
            }
        )
    return pd.DataFrame(rows)


def build_feature_probe() -> pd.DataFrame:
    """Robustness check: is the round-4 cliff an artifact of the feature?

    per-hash row is exact (Tier B seed0, n=500k). per-batch is the local
    DEVLOG 2026-05-16 n=2M probe — its CI floor is coarse (~0.10) because
    the per-batch deviation map yields few examples, so it is recorded
    qualitatively and labelled with its provenance. Same cliff either
    way: the boundary is not feature-bottlenecked.
    """
    tb0 = _load(HF / "bfl-ml-tierB" / "sweep_seed0.json")
    by_round = {p["rounds"]: p for p in tb0["points"]}
    ph_learn = sorted(r for r, p in by_round.items()
                      if p["accuracy_ci"][0] > 0.5)
    ph_chance = sorted(r for r in (4, 5, 6, 8) if r in by_round)
    rows = [
        {
            "feature": "per-hash",
            "n_train": 500_000,
            "rounds_learnable": json.dumps(ph_learn),
            "rounds_at_chance": json.dumps(ph_chance),
            "ci_resolution_floor": tb0["points"][0]["min_detectable_advantage"],
            "conclusion": "sharp learnability cliff after round 3",
            "provenance": "HF Tier B seed0 (exact)",
        },
        {
            "feature": "per-batch",
            "n_train": 2_000_000,
            "rounds_learnable": json.dumps([3]),
            "rounds_at_chance": json.dumps([4, 5, 6, 8]),
            "ci_resolution_floor": 0.10,  # coarse: few per-batch examples
            "conclusion": (
                "same round-4 cliff reproduced; not feature-bottlenecked"
            ),
            "provenance": (
                "DEVLOG 2026-05-16 local n=2M probe; coarse floor; "
                "qualitative (r3=1.00; r4-8 CI brackets 0.5)"
            ),
        },
    ]
    return pd.DataFrame(rows)


def main() -> None:
    tables = {
        "learnability_sweep": build_learnability_sweep(),
        "bounded_null": build_bounded_null(),
        "dynamics_validated": build_dynamics_validated(),
        "feature_probe": build_feature_probe(),
    }
    total = 0
    for name, df in tables.items():
        out = SCRIPT_DIR / f"{name}.parquet"
        df.to_parquet(out, index=False, engine="pyarrow")
        total += len(df)
        print(f"  {name:22s} {len(df):4d} rows  -> {out.name}")
    print(f"Total: {total} rows across {len(tables)} Parquet tables.")


if __name__ == "__main__":
    main()
