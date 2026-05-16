#!/usr/bin/env python3
"""
Tiny smoke target for HF Jobs bootstrap — bfl-asic ML subsystem.

Runs a minimal sweep([2,64], n=512, epochs=1, model="linear_probe") and
writes results/smoke.json.  Must finish in seconds.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


def main() -> int:
    from bfl_asic.ml.experiments import run_sweep

    t0 = time.time()
    print("[smoke] bfl-asic smoke target starting", flush=True)

    try:
        import numpy
        import torch
        torch_ver = torch.__version__
        cuda = torch.cuda.is_available()
    except ImportError:
        torch_ver = "unavailable"
        cuda = False

    try:
        numpy_ver = numpy.__version__
    except Exception:
        numpy_ver = "unavailable"

    print(f"[smoke] numpy={numpy_ver} torch={torch_ver} cuda={cuda}", flush=True)

    points, controls = run_sweep(
        [2, 64], seed=0, n=512, epochs=1, model="linear_probe"
    )

    elapsed = time.time() - t0
    acc_by_rounds = {str(p["rounds"]): p["accuracy"] for p in points}
    out = {
        "status": "complete",
        "config": {
            "rounds": [2, 64],
            "seed": 0,
            "n": 512,
            "epochs": 1,
            "model": "linear_probe",
        },
        "accuracies": acc_by_rounds,
        "controls": controls,
        "elapsed_s": round(elapsed, 3),
        "numpy_version": numpy_ver,
        "torch_version": torch_ver,
        "cuda": cuda,
    }

    mnt = Path(os.environ.get("HF_BFL_MNT", "/mnt"))
    rdir = mnt / "results"
    rdir.mkdir(parents=True, exist_ok=True)

    out_path = rdir / "smoke.json"
    tmp = out_path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    os.replace(tmp, out_path)

    print(f"[smoke] done in {elapsed:.2f}s  accuracies={acc_by_rounds}", flush=True)
    print(f"[smoke] results -> {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
