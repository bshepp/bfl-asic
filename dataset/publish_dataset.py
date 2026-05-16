#!/usr/bin/env python3
"""Publish this directory as a public Hugging Face *dataset* repo.

Mirrors `bfl_asic/ml/publish.py` (HfApi.create_repo + upload_folder) but
with `repo_type="dataset"` and public-by-default, matching the author's
existing HF dataset convention (`bshepp/pairwise-poisson-algebras`).

Uploads only the curated card + Parquet + the two build/publish scripts
(no synced run JSON, no payloads). Auth comes from the already-configured
`hf` CLI token (HF_TOKEN env var or `~/.cache/huggingface/token`).

Usage:
    python dataset/publish_dataset.py                       # default repo, public
    python dataset/publish_dataset.py --repo-id bshepp/...  # override
    python dataset/publish_dataset.py --private             # private first
    python dataset/publish_dataset.py --dry-run             # show, do not push
"""
from __future__ import annotations

import argparse
from pathlib import Path

DEFAULT_REPO = "bshepp/round-reduced-sha256-learnability"
ALLOW = ["README.md", "*.parquet", "build_dataset.py", "publish_dataset.py"]


def publish(repo_id: str, *, private: bool, dry_run: bool) -> str:
    folder = Path(__file__).resolve().parent
    url = f"https://huggingface.co/datasets/{repo_id}"
    files = sorted(
        p.name
        for p in folder.iterdir()
        if p.suffix in (".parquet", ".md", ".py")
    )
    if dry_run:
        print(f"[dry-run] would create dataset repo {repo_id} "
              f"(private={private}) and upload from {folder}:")
        for f in files:
            print(f"  + {f}")
        print(f"[dry-run] -> {url}")
        return url

    from huggingface_hub import HfApi  # lazy: only needed to actually push

    api = HfApi()
    api.create_repo(
        repo_id, repo_type="dataset", exist_ok=True, private=private
    )
    api.upload_folder(
        repo_id=repo_id,
        repo_type="dataset",
        folder_path=str(folder),
        allow_patterns=ALLOW,
        commit_message="Publish curated, controls-verified results",
    )
    return url


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-id", default=DEFAULT_REPO)
    ap.add_argument("--private", action="store_true",
                    help="create private (default: public)")
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be pushed; do not push")
    args = ap.parse_args()
    url = publish(args.repo_id, private=args.private, dry_run=args.dry_run)
    print(url)


if __name__ == "__main__":
    main()
