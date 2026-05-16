#!/usr/bin/env python3
"""HF Jobs target: standalone 'indistinguishability' at n=4M.

Full SHA-256 (64 rounds) vs random, tiny_cnn, n=4_000_000, epochs=30
(n_val = 800k -> CI-resolution floor ~0.22%). Writes an MLSnapshot +
summary.json to /mnt/results/ atomically, with a SIGTERM partial flush
and an idempotent progress.json (a resubmit after completion is a
no-op). Designed to finish in a single ~4h cpu-xl cycle.

Run on HF:
  hf jobs uv run --flavor cpu-xl -v hf://buckets/bshepp/bfl-ml-indist:/mnt \\
      --timeout 6h --detach scripts/hf_jobs/bootstrap.py run_indist
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time
from pathlib import Path

RESULTS = Path(os.environ.get("HF_BFL_MNT", "/mnt")) / "results"
SNAP = RESULTS / "indistinguishability.json"
SUMMARY = RESULTS / "summary.json"
PROGRESS = RESULTS / "progress.json"

_state: dict = {
    "status": "running",
    "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
}


def _atomic(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2))
    os.replace(tmp, path)


def _flush_partial(reason: str) -> None:
    _state["status"] = f"partial:{reason}"
    _state["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        _atomic(SUMMARY, _state)
        print(f"[indist] partial flushed ({reason})", flush=True)
    except Exception as e:  # pragma: no cover - best effort
        print(f"[indist] partial flush failed: {e}", file=sys.stderr,
              flush=True)


def _sigterm(signum, frame) -> None:
    print(f"[indist] caught signal {signum}; flushing partial", flush=True)
    _flush_partial("sigterm")
    sys.exit(143)


def main() -> int:
    signal.signal(signal.SIGTERM, _sigterm)

    if PROGRESS.exists():
        try:
            done = json.loads(PROGRESS.read_text()).get("completed", [])
        except Exception:
            done = []
        if "indistinguishability" in done:
            print("[indist] already complete; nothing to do", flush=True)
            return 0

    import numpy
    import torch

    print(f"[indist] numpy={numpy.__version__} torch={torch.__version__} "
          f"cuda={torch.cuda.is_available()}", flush=True)

    from bfl_asic.ml.experiments import run_sweep
    from bfl_asic.ml.snapshot import MLSnapshot

    t0 = time.time()
    points, controls = run_sweep(
        [64], seed=0, n=4_000_000, epochs=30, model="tiny_cnn",
    )
    elapsed = time.time() - t0

    snap = MLSnapshot.from_runs(
        experiment="indistinguishability", feature="per-hash",
        model="tiny_cnn", points=points, controls=controls,
    )
    _atomic(SNAP, json.loads(snap.to_json()))

    p = points[0]
    _state.update(
        status="complete",
        finished=time.strftime("%Y-%m-%dT%H:%M:%S"),
        elapsed_s=round(elapsed, 1),
        accuracy=p["accuracy"],
        accuracy_ci=p["accuracy_ci"],
        advantage=p["advantage"],
        # NOTE: a CI-resolution floor (the 95% CI on accuracy still
        # includes chance below it), NOT a power-based MDE.
        ci_resolution_floor=p["min_detectable_advantage"],
        controls=controls,
        numpy_version=numpy.__version__,
        torch_version=torch.__version__,
        cuda=torch.cuda.is_available(),
    )
    _atomic(SUMMARY, _state)
    _atomic(PROGRESS, {"completed": ["indistinguishability"]})

    print(f"[indist] DONE acc={p['accuracy']:.5f} CI={p['accuracy_ci']} "
          f"floor(CI-resolution)={p['min_detectable_advantage']:.5f} "
          f"controls positive_ok={controls.get('positive_ok')} "
          f"negative_ok={controls.get('negative_ok')} "
          f"in {elapsed:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
