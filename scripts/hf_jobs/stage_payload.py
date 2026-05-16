#!/usr/bin/env python3
"""
Payload stager for HF Jobs — bfl-asic ML subsystem.

Assembles a self-contained payload directory suitable for
`hf buckets sync` to a Hugging Face bucket.

Usage:
  python scripts/hf_jobs/stage_payload.py --campaign bfl-ml-smoke --dest ./hf_payload
  python scripts/hf_jobs/stage_payload.py --campaign bfl-ml-tier-a --dest ./hf_payload

The payload dir layout mirrors the reference n5_probe structure:
  <dest>/<campaign>/
    bfl_asic/          -- the installed package tree
    run_ml_tier.py
    run_smoke.py
    results/           -- empty; populated by the HF job
    results/.gitkeep
"""
from __future__ import annotations

import argparse
import shutil
import os
from pathlib import Path


def _ignore_pycache(src, names):
    return [n for n in names if n == "__pycache__" or n.endswith(".pyc")]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stage bfl-asic HF Jobs payload"
    )
    parser.add_argument("--campaign", required=True,
                        help="Campaign name (e.g. bfl-ml-smoke)")
    parser.add_argument("--dest", default="./hf_payload",
                        help="Destination root (default: ./hf_payload)")
    args = parser.parse_args()

    # Resolve repo root: this script lives at scripts/hf_jobs/stage_payload.py
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent

    dest_root = Path(args.dest).resolve()
    campaign_dir = dest_root / args.campaign

    print(f"[stage] campaign={args.campaign!r}", flush=True)
    print(f"[stage] repo_root={repo_root}", flush=True)
    print(f"[stage] dest={campaign_dir}", flush=True)

    # --- Copy bfl_asic package ---
    src_pkg = repo_root / "bfl_asic"
    dst_pkg = campaign_dir / "bfl_asic"
    if dst_pkg.exists():
        shutil.rmtree(dst_pkg)
    shutil.copytree(src_pkg, dst_pkg, ignore=_ignore_pycache)
    print(f"[stage] copied bfl_asic/ -> {dst_pkg}", flush=True)

    # --- Copy target scripts ---
    hf_jobs_dir = script_dir
    for script_name in ("run_ml_tier.py", "run_smoke.py"):
        src = hf_jobs_dir / script_name
        dst = campaign_dir / script_name
        shutil.copy2(src, dst)
        print(f"[stage] copied {script_name} -> {dst}", flush=True)

    # --- Create empty results/ dir ---
    results_dir = campaign_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    gitkeep = results_dir / ".gitkeep"
    gitkeep.touch()
    print(f"[stage] created {results_dir}/", flush=True)

    # --- Print tree ---
    print(f"\n[stage] payload tree ({campaign_dir}):", flush=True)
    for root, dirs, files in os.walk(campaign_dir):
        dirs[:] = [d for d in sorted(dirs) if d != "__pycache__"]
        rel = Path(root).relative_to(campaign_dir)
        indent = "  " * len(rel.parts)
        if str(rel) != ".":
            print(f"{indent}{rel.name}/", flush=True)
        for fname in sorted(files):
            if not fname.endswith(".pyc"):
                fpath = Path(root) / fname
                size = fpath.stat().st_size
                print(f"{indent}  {fname}  ({size} B)", flush=True)

    # --- Print commands ---
    bucket = f"bshepp/{args.campaign}"
    print(f"\n[stage] sync command:", flush=True)
    print(f"  hf buckets sync {campaign_dir} hf://buckets/{bucket}", flush=True)
    print(f"\n[stage] smoke job command:", flush=True)
    print(
        f"  hf jobs uv run --flavor cpu-xl"
        f" -v hf://buckets/{bucket}:/mnt"
        f" --timeout 6h --detach"
        f" scripts/hf_jobs/bootstrap.py run_smoke",
        flush=True,
    )
    print(f"\n[stage] tier-A job command:", flush=True)
    print(
        f"  hf jobs uv run --flavor cpu-xl"
        f" -v hf://buckets/{bucket}:/mnt"
        f" --timeout 6h --detach"
        f" scripts/hf_jobs/bootstrap.py run_ml_tier --tier A",
        flush=True,
    )
    print(f"\n[stage] tier-B job command:", flush=True)
    print(
        f"  hf jobs uv run --flavor cpu-xl"
        f" -v hf://buckets/{bucket}:/mnt"
        f" --timeout 6h --detach"
        f" scripts/hf_jobs/bootstrap.py run_ml_tier --tier B",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
