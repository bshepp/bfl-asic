#!/usr/bin/env python3
"""Build the BFL Jalapeño characterization + production-census dataset tables.

Mirrors the sibling dataset (``bshepp/round-reduced-sha256-learnability``): a
deterministic, **pandas-only** script that reads curated JSON in ``source/``
and emits one Parquet table per config next to the card (README.md). This is
distilled, *verified* measurement -- the raw characterization runs live in the
``bfl-asic`` repo (``docs/characterization/``) and are regenerable via
``scripts/hw/characterize.py``; the serials are confirmed from photographs.

Rows flagged ``pending: true`` in ``source/characterization.json`` (e.g. a run
still in progress) are skipped and reported, so the build is always
self-consistent.

Run:  python dataset-jalapeno/build_dataset.py
Deps: pandas, pyarrow  (pip install pandas pyarrow)
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd

DIR = Path(__file__).resolve().parent
SRC = DIR / "source"


def _load(name: str) -> dict:
    # utf-8-sig: tolerate a Windows BOM on synced artifacts.
    with io.open(SRC / name, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def build_units() -> pd.DataFrame:
    """Per-unit ZCX census + identity for both physical Jalapeños."""
    return pd.DataFrame(_load("units.json")["units"])


def build_characterization() -> pd.DataFrame:
    """One row per (unit, sustained-work run): throughput, determinism,
    thermal plateau, and the dead-core health verdict. Pending runs skipped."""
    runs = _load("characterization.json")["runs"]
    kept, pending = [], []
    for r in runs:
        (pending if r.get("pending") else kept).append(r)
    for r in pending:
        print(f"  (skipping pending run: {r['board_serial']} {r['run']} "
              f"-- {r.get('provenance', '')})")
    for r in kept:
        r.pop("pending", None)
    return pd.DataFrame(kept)


def build_cross_unit_determinism() -> pd.DataFrame:
    """The identical fixed work submitted to both units -> identical winners.

    ``nonce_set`` is a JSON string so the list survives Parquet round-trips.
    """
    doc = _load("cross_unit.json")
    rows = [
        {
            "board_serial": o["board_serial"],
            "reps": o["reps"],
            "distinct_nonce_sets": o["distinct_nonce_sets"],
            "nonce_set": json.dumps(o["nonce_set"]),
            "deterministic": o["deterministic"],
            "provenance": o.get("provenance", ""),
        }
        for o in doc["observations"]
    ]
    return pd.DataFrame(rows)


def build_production_census() -> pd.DataFrame:
    """The confirmed serials (the data behind the German-tank estimate).

    The scalar estimate lives in the card + ``source/production_census.json``
    and is recomputable from these serials -- the serials are the evidence.
    """
    return pd.DataFrame(_load("production_census.json")["confirmed_serials"])


def main() -> None:
    tables = {
        "units": build_units(),
        "characterization": build_characterization(),
        "cross_unit_determinism": build_cross_unit_determinism(),
        "production_census": build_production_census(),
    }
    total = 0
    for name, df in tables.items():
        out = DIR / f"{name}.parquet"
        df.to_parquet(out, index=False, engine="pyarrow")
        total += len(df)
        print(f"  {name:24s} {len(df):3d} rows  -> {out.name}")
    print(f"Total: {total} rows across {len(tables)} Parquet tables.")


if __name__ == "__main__":
    main()
