#!/usr/bin/env python3
"""
scripts/upload_dataset_hf.py

Upload the Weave-Bench dataset to Hugging Face Hub.
Run this after `go run dataset/builder.go dataset/schema.go` to keep the
HF dataset in sync with the local build.

Prerequisites:
    hf auth login   # one-time, saves token to ~/.cache/huggingface/token

Usage:
    uv run python scripts/upload_dataset_hf.py
    uv run python scripts/upload_dataset_hf.py --repo kavirubc/weave-bench
    uv run python scripts/upload_dataset_hf.py --dry-run   # just prints what would be uploaded
"""

import argparse
import json
import os
import glob
from pathlib import Path

REPO_ID_DEFAULT = "kavirubc/weave-bench"
OUTPUT_DIR = Path("dataset/output")
KAGGLE_DIR = OUTPUT_DIR / "kaggle_upload"

FILES_TO_UPLOAD = [
    # (local_path, repo_path)
    (KAGGLE_DIR / "train_point_dups.jsonl",  "data/train.jsonl"),
    (KAGGLE_DIR / "val_point_dups.jsonl",    "data/validation.jsonl"),
    (OUTPUT_DIR / "aggregated.json",         "data/aggregated.json"),
]


def upload(repo_id: str, dry_run: bool):
    from huggingface_hub import HfApi, create_repo
    api = HfApi()

    # Create repo if it doesn't exist
    if not dry_run:
        create_repo(repo_id, repo_type="dataset", exist_ok=True)
        print(f"Repo: https://huggingface.co/datasets/{repo_id}")

    # Upload fixed files
    for local_path, repo_path in FILES_TO_UPLOAD:
        if not local_path.exists():
            print(f"  SKIP  {local_path} (not found — run builder.go first)")
            continue
        size_kb = local_path.stat().st_size // 1024
        if dry_run:
            print(f"  DRY   {local_path} → {repo_path}  ({size_kb}KB)")
        else:
            print(f"  UP    {local_path} → {repo_path}  ({size_kb}KB)")
            api.upload_file(
                path_or_fileobj=str(local_path),
                path_in_repo=repo_path,
                repo_id=repo_id,
                repo_type="dataset",
            )

    # Upload individual per-run trace examples — only flat *.json files, no subdirs
    trace_files = sorted(
        f for f in OUTPUT_DIR.glob("*.json")
        if f.is_file() and f.name != "aggregated.json"
    )
    print(f"\n  Uploading {len(trace_files)} trace JSON files to traces/...")

    if not dry_run and trace_files:
        import tempfile, shutil
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for f in trace_files:
                shutil.copy2(f, tmp_path / f.name)
            api.upload_folder(
                folder_path=tmp,
                path_in_repo="traces",
                repo_id=repo_id,
                repo_type="dataset",
            )
        print(f"  UP    {len(trace_files)} trace files → traces/")
    elif dry_run:
        for f in list(trace_files)[:3]:
            print(f"  DRY   {f.name} → traces/{f.name}")
        if len(trace_files) > 3:
            print(f"  DRY   ... and {len(trace_files) - 3} more")

    if not dry_run:
        print(f"\nDone. View at: https://huggingface.co/datasets/{repo_id}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo",    default=REPO_ID_DEFAULT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        print(f"DRY RUN — would upload to {args.repo}:\n")
    else:
        print(f"Uploading to {args.repo}...\n")

    upload(args.repo, args.dry_run)


if __name__ == "__main__":
    main()
