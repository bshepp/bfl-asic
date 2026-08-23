#!/usr/bin/env python3
"""Publish this directory as a public Hugging Face *dataset* repo.

Mirrors ``dataset/publish_dataset.py`` (HfApi.create_repo + upload_folder,
``repo_type="dataset"``, public-by-default). Uploads a self-contained dataset:
the curated card + Parquet + the build/publish scripts + the ``source/`` JSON,
so the HF repo rebuilds via ``python build_dataset.py`` with no external data.
The card's ``configs:`` pin the .parquet, so the source JSON is inert to the
Dataset Viewer. Auth comes from the configured ``hf`` CLI token.

Usage:
    python dataset-jalapeno/publish_dataset.py                # default, public
    python dataset-jalapeno/publish_dataset.py --repo-id ...  # override
    python dataset-jalapeno/publish_dataset.py --private      # private first
    python dataset-jalapeno/publish_dataset.py --dry-run      # show, don't push
"""
from __future__ import annotations

import argparse
import fnmatch
from pathlib import Path

DEFAULT_REPO = "bshepp/bfl-jalapeno-characterization"
ALLOW = [
    "README.md",
    "*.parquet",
    "build_dataset.py",
    "publish_dataset.py",
    "source/*",  # fnmatch '*' spans '/', so this is recursive under source/
]


def publish(repo_id: str, *, private: bool, dry_run: bool) -> str:
    folder = Path(__file__).resolve().parent
    url = f"https://huggingface.co/datasets/{repo_id}"
    files = sorted(
        rel
        for p in folder.rglob("*")
        if p.is_file()
        and any(fnmatch.fnmatch(rel := p.relative_to(folder).as_posix(), pat)
                for pat in ALLOW)
    )
    if dry_run:
        print(f"[dry-run] would create dataset repo {repo_id} "
              f"(private={private}) and upload {len(files)} files "
              f"from {folder}:")
        for f in files:
            print(f"  + {f}")
        print(f"[dry-run] -> {url}")
        return url

    from huggingface_hub import HfApi  # lazy: only needed to actually push

    api = HfApi()
    api.create_repo(repo_id, repo_type="dataset", exist_ok=True,
                    private=private)
    api.upload_folder(
        repo_id=repo_id,
        repo_type="dataset",
        folder_path=str(folder),
        allow_patterns=ALLOW,
        commit_message="Publish BFL Jalapeño characterization + production census",
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
    print(publish(args.repo_id, private=args.private, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
