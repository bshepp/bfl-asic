#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "numpy",
#   "scipy",
#   "matplotlib",
#   "click",
#   "torch",
# ]
# [tool.uv.sources]
# torch = [{ index = "pytorch-cpu" }]
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""
HF Jobs UV bootstrap for the bfl-asic ML subsystem.

Mounts the project payload (bfl_asic package + target script + results/)
from a bucket at /mnt, sets sys.path so `import bfl_asic` resolves,
then runs the named target script as __main__.

Usage (locally for smoke, pointing at staged payload):
  HF_BFL_MNT=./hf_payload/bfl-ml-smoke python scripts/hf_jobs/bootstrap.py run_smoke

Usage on HF Jobs:
  hf jobs uv run --flavor cpu-xl \
      -v hf://buckets/bshepp/<bucket>:/mnt \
      --timeout 6h --detach \
      scripts/hf_jobs/bootstrap.py <target> [args...]

The target name resolves to /mnt/<target>.py.
Remaining argv after <target> are forwarded to the target script.
"""
from __future__ import annotations

import os
import sys
import time
import platform


def main() -> int:
    if len(sys.argv) < 2:
        print("ERROR: missing target name. Usage: bootstrap.py <target> [args...]",
              file=sys.stderr)
        return 2
    target = sys.argv[1]
    extra_args = sys.argv[2:]

    mnt = os.environ.get("HF_BFL_MNT", "/mnt")
    print(f"[bootstrap] target={target!r} mnt={mnt!r}", flush=True)
    print(f"[bootstrap] python={sys.version.split()[0]} "
          f"platform={platform.platform()}", flush=True)
    print(f"[bootstrap] cwd={os.getcwd()}", flush=True)

    if not os.path.isdir(mnt):
        print(f"ERROR: mount {mnt!r} not found", file=sys.stderr)
        return 3

    # Make /mnt importable so `import bfl_asic` resolves the bundled tree.
    if mnt not in sys.path:
        sys.path.insert(0, mnt)

    # Versions
    import numpy
    print(f"[bootstrap] numpy={numpy.__version__}", flush=True)
    try:
        import torch
        print(f"[bootstrap] torch={torch.__version__} "
              f"cuda={torch.cuda.is_available()}", flush=True)
    except ImportError:
        print("[bootstrap] torch not available", flush=True)

    target_path = os.path.join(mnt, f"{target}.py")
    if not os.path.isfile(target_path):
        print(f"ERROR: target script not found: {target_path}",
              file=sys.stderr)
        return 4

    print(f"[bootstrap] running {target_path} {extra_args}", flush=True)
    t0 = time.time()
    # Execute the target as __main__ so it can use argparse/sys.argv.
    sys.argv = [target_path] + extra_args
    namespace = {"__name__": "__main__", "__file__": target_path}
    with open(target_path, "rb") as f:
        code = compile(f.read(), target_path, "exec")
    try:
        exec(code, namespace)
        rc = 0
    except SystemExit as e:
        rc = e.code if isinstance(e.code, int) else 0
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 1
    elapsed = time.time() - t0
    print(f"[bootstrap] target exit rc={rc}  elapsed={elapsed:.1f}s",
          flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
