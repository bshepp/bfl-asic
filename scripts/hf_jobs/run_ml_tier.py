#!/usr/bin/env python3
"""
ML tier driver for HF Jobs — bfl-asic ML subsystem.

Run as the target from bootstrap.py:
  python scripts/hf_jobs/bootstrap.py run_ml_tier [--tier A|B] [--smoke]

Or directly (bfl_asic must be importable):
  python scripts/hf_jobs/run_ml_tier.py --smoke
  python scripts/hf_jobs/run_ml_tier.py --tier A
  python scripts/hf_jobs/run_ml_tier.py --tier B

Features:
  - Atomic writes (tmp + os.replace)
  - SIGTERM handler flushes progress.json + any in-flight *.partial.json, exits 143
  - Resumability via RESULTS_DIR/progress.json (already-completed units are skipped)
  - Per-unit error isolation (one failure records status:error, run continues)
  - Final summary.json with per-unit elapsed, status, curve data, torch/numpy versions
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths / env
# ---------------------------------------------------------------------------

RESULTS_DIR = Path(os.environ.get("HF_BFL_MNT", "/mnt")) / "results"
PROGRESS_PATH = RESULTS_DIR / "progress.json"
SUMMARY_PATH = RESULTS_DIR / "summary.json"

# ---------------------------------------------------------------------------
# In-flight state (SIGTERM handler updates this)
# ---------------------------------------------------------------------------

_inflight: dict = {}          # populated while a unit is running
_unit_results: dict = {}      # key -> {"status", "elapsed_s", ...}
_tier_label: str = "?"
_t_total_start: float = 0.0


# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------

def _atomic_write(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Progress (completed unit keys)
# ---------------------------------------------------------------------------

def _load_progress() -> set[str]:
    if PROGRESS_PATH.exists():
        try:
            data = json.loads(PROGRESS_PATH.read_text())
            return set(data.get("completed", []))
        except Exception:
            pass
    return set()


def _save_progress(completed: set[str]) -> None:
    _atomic_write(PROGRESS_PATH, {"completed": sorted(completed)})


# ---------------------------------------------------------------------------
# SIGTERM handler
# ---------------------------------------------------------------------------

def _sigterm_handler(signum, frame):
    print(f"[tier] caught signal {signum}; flushing partial state", flush=True)
    # Flush any in-flight partial state
    if _inflight:
        partial_path = RESULTS_DIR / f"{_inflight.get('key', 'unknown')}.partial.json"
        try:
            _atomic_write(partial_path, {
                **_inflight,
                "status": "partial:sigterm",
                "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            })
            print(f"[tier] partial flushed -> {partial_path}", flush=True)
        except Exception as e:
            print(f"[tier] partial flush failed: {e}", file=sys.stderr, flush=True)
    # Flush summary with what we have so far
    try:
        _write_summary(status="partial:sigterm")
    except Exception as e:
        print(f"[tier] summary flush failed: {e}", file=sys.stderr, flush=True)
    sys.exit(143)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _write_summary(status: str = "complete") -> None:
    try:
        import numpy
        numpy_ver = numpy.__version__
    except ImportError:
        numpy_ver = "unavailable"
    try:
        import torch
        torch_ver = torch.__version__
        cuda = torch.cuda.is_available()
    except ImportError:
        torch_ver = "unavailable"
        cuda = False

    summary = {
        "status": status,
        "tier": _tier_label,
        "total_elapsed_s": round(time.time() - _t_total_start, 2),
        "numpy_version": numpy_ver,
        "torch_version": torch_ver,
        "cuda": cuda,
        "units": _unit_results,
    }
    _atomic_write(SUMMARY_PATH, summary)


# ---------------------------------------------------------------------------
# Tier configs
# ---------------------------------------------------------------------------

def _tier_a_units() -> list[dict]:
    units = []
    for s in range(3):
        units.append({
            "key": f"sweep_seed{s}",
            "kind": "sweep",
            "kwargs": {
                "rounds": [1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64],
                "seed": s, "n": 200_000, "epochs": 25,
                "model": "tiny_cnn", "feature": "per-hash",
            },
            "save_plot": True,
        })
    for s in range(3):
        units.append({
            "key": f"full_structure_seed{s}",
            "kind": "full_structure",
            "kwargs": {"seed": s, "n": 800_000, "epochs": 25},
            "save_plot": False,
        })
    units.append({
        "key": "indistinguishability",
        "kind": "sweep",
        "kwargs": {
            "rounds": [64], "seed": 0, "n": 800_000, "epochs": 25,
            "model": "tiny_cnn",
        },
        "save_plot": False,
    })
    units.append({
        "key": "dynamics",
        "kind": "dynamics",
        "kwargs": {
            "seed": 0, "n": 20_000, "epochs": 25,
            "trunc_widths": [1, 2, 3, 4], "n_bins": 4,
        },
        "save_plot": True,
    })
    return units


def _tier_b_units() -> list[dict]:
    # Trimmed to the 5-seed sweep only (user decision, 2026-05-16):
    # the first two completed Tier B seeds replicated Tier A's
    # learnability cliff exactly, and the original full_structure x5 /
    # indistinguishability / dynamics tail (~25 h at n=4M) is redundant
    # with Tier A's already-valid bounded null. With this list the job
    # self-terminates cleanly after sweep_seed4 on resume (progress.json
    # skips already-completed seeds) -- no manual cancel/race needed.
    units = []
    for s in range(5):
        units.append({
            "key": f"sweep_seed{s}",
            "kind": "sweep",
            "kwargs": {
                "rounds": [1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 32, 40, 48, 56, 64],
                "seed": s, "n": 500_000, "epochs": 30,
                "model": "tiny_cnn",
            },
            "save_plot": True,
        })
    return units


def _smoke_units() -> list[dict]:
    return [{
        "key": "smoke",
        "kind": "sweep",
        "kwargs": {
            "rounds": [2, 64], "seed": 0, "n": 512, "epochs": 1,
            "model": "linear_probe",
        },
        "save_plot": False,
    }]


# ---------------------------------------------------------------------------
# Unit runners
# ---------------------------------------------------------------------------

def _run_unit(unit: dict) -> dict:
    """Run one experiment unit; return result dict (never raises)."""
    from bfl_asic.ml.experiments import (
        run_sweep, run_full_structure, run_dynamics_sweep,
    )
    from bfl_asic.ml.snapshot import MLSnapshot
    from bfl_asic.ml.visualization import plot_learnability_curve
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    key = unit["key"]
    kind = unit["kind"]
    kwargs = unit["kwargs"]
    save_plot = unit.get("save_plot", False)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    try:
        if kind == "sweep":
            rounds = kwargs.pop("rounds")
            points, controls = run_sweep(rounds, **kwargs)
            snapshot = MLSnapshot.from_runs(
                experiment=key,
                feature=kwargs.get("feature", "per-hash"),
                model=kwargs.get("model", "tiny_cnn"),
                points=points,
                controls=controls,
            )
            snapshot.save(RESULTS_DIR / f"{key}.json")
            curve = {str(p["rounds"]): p["accuracy"] for p in points}
            result_data = {
                "status": "complete",
                "elapsed_s": round(time.time() - t0, 2),
                "curve": curve,
                "controls": controls,
            }
            if save_plot:
                fig = plot_learnability_curve(snapshot,
                                             save_path=RESULTS_DIR / f"{key}.png")
                plt.close(fig)

        elif kind == "full_structure":
            points, controls, bounded_null = run_full_structure(**kwargs)
            snapshot = MLSnapshot.from_runs(
                experiment=key,
                feature="per-hash",
                model="multi",
                points=points,
                controls=controls,
                bounded_null=bounded_null,
            )
            snapshot.save(RESULTS_DIR / f"{key}.json")
            result_data = {
                "status": "complete",
                "elapsed_s": round(time.time() - t0, 2),
                "bounded_null": bounded_null,
                "controls": controls,
            }

        elif kind == "dynamics":
            points, controls = run_dynamics_sweep(**kwargs)
            snapshot = MLSnapshot.from_runs(
                experiment="dynamics",
                feature="orbit",
                model="tiny_cnn",
                points=points,
                controls=controls,
            )
            snapshot.save(RESULTS_DIR / "dynamics.json")
            curve = {str(p["rounds"]): p["accuracy"] for p in points}
            result_data = {
                "status": "complete",
                "elapsed_s": round(time.time() - t0, 2),
                "curve": curve,
                "controls": controls,
            }
            if save_plot:
                fig = plot_learnability_curve(snapshot,
                                             save_path=RESULTS_DIR / "dynamics.png")
                plt.close(fig)

        else:
            raise ValueError(f"unknown unit kind: {kind!r}")

    except Exception:
        tb = traceback.format_exc()
        print(f"[tier] ERROR in unit {key!r}:\n{tb}", flush=True)
        result_data = {
            "status": "error",
            "elapsed_s": round(time.time() - t0, 2),
            "traceback": tb,
        }

    return result_data


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    global _tier_label, _t_total_start

    parser = argparse.ArgumentParser(description="bfl-asic ML tier driver")
    parser.add_argument("--tier", choices=["A", "B"], default="A",
                        help="Which tier config to run (default: A)")
    parser.add_argument("--smoke", action="store_true",
                        help="Run tiny smoke config regardless of --tier")
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, _sigterm_handler)

    _t_total_start = time.time()

    if args.smoke:
        _tier_label = "smoke"
        units = _smoke_units()
    elif args.tier == "A":
        _tier_label = "A"
        units = _tier_a_units()
    else:
        _tier_label = "B"
        units = _tier_b_units()

    print(f"[tier] starting tier={_tier_label} units={len(units)}", flush=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    completed = _load_progress()
    print(f"[tier] progress: {len(completed)} units already complete: "
          f"{sorted(completed)}", flush=True)

    # Restore already-completed units into _unit_results so they appear in summary
    for key in completed:
        _unit_results[key] = {"status": "skip (already complete)"}

    for unit in units:
        key = unit["key"]
        if key in completed:
            print(f"[tier] skip (already complete): {key}", flush=True)
            continue

        print(f"[tier] running unit: {key}", flush=True)
        _inflight.clear()
        _inflight.update({"key": key, "started_at": time.strftime("%Y-%m-%dT%H:%M:%S")})

        result = _run_unit(unit)
        _unit_results[key] = result
        _inflight.clear()

        if result["status"] == "complete":
            completed.add(key)
            _save_progress(completed)
            print(f"[tier] unit {key!r} done in {result['elapsed_s']:.1f}s",
                  flush=True)
        else:
            print(f"[tier] unit {key!r} failed — continuing", flush=True)

    _write_summary(status="complete")

    # Concise text summary
    total = time.time() - _t_total_start
    print(f"\n[tier] ===== SUMMARY tier={_tier_label} =====", flush=True)
    for key, res in _unit_results.items():
        st = res.get("status", "?")
        el = res.get("elapsed_s", "-")
        if st == "complete":
            if "curve" in res:
                pts_str = " ".join(f"r{r}={v:.3f}" for r, v in res["curve"].items())
                print(f"  {key}: {st} ({el}s) curve=[{pts_str}]", flush=True)
            elif "bounded_null" in res:
                bn = res["bounded_null"]
                print(f"  {key}: {st} ({el}s) "
                      f"acc={bn.get('accuracy', '?'):.3f} "
                      f"controls_ok={bn.get('controls_ok', '?')} "
                      f"conclusion={bn.get('conclusion', '?')!r}", flush=True)
            else:
                print(f"  {key}: {st} ({el}s)", flush=True)
        else:
            print(f"  {key}: {st}", flush=True)
    print(f"[tier] total elapsed: {total:.1f}s", flush=True)
    print(f"[tier] summary -> {SUMMARY_PATH}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
