#!/usr/bin/env python3
"""
scripts/upload_model_hf.py

Upload the Weave LoRA adapter to Hugging Face Hub.

Usage:
    uv run python scripts/upload_model_hf.py
    uv run python scripts/upload_model_hf.py --adapter dataset/output/lora_adapter_v2/lora_adapter/checkpoint-516
    uv run python scripts/upload_model_hf.py --dry-run
"""
import argparse
from pathlib import Path

REPO_ID_DEFAULT  = "kavirubc/weave-ccwm-qwen2.5-coder-7b-lora"
ADAPTER_DEFAULT  = "dataset/output/lora_adapter_v3"

MODEL_CARD = """---
language: en
license: apache-2.0
base_model: Qwen/Qwen2.5-Coder-7B-Instruct
tags:
  - lora
  - qlora
  - concurrent-programming
  - program-analysis
  - go
  - world-model
  - peft
datasets:
  - kavirubc/weave-bench
---

# Weave-CCWM — Qwen2.5-Coder-7B LoRA (Phase 13)

A LoRA adapter fine-tuned on **Weave-Bench** for next-scheduler-event prediction in
concurrent Go programs. Part of the [Weave](https://github.com/kaviru2/Weave) project
on Concurrent Code World Models (CCWM).

## What this model does

Given a concurrent Go program and a partial execution trace (goroutine scheduler events),
predict the next scheduler event:

```
Input:  Go program source + partial trace (GoStart, GoBlock, GoUnblock, GoCreate, GoEnd, GoSched events)
Output: {"event_type": "GoBlock", "goroutine_id": 3, "reasoning": "...", "confidence": "high"}
```

## Training

| Setting | Value |
|---------|-------|
| Base model | `Qwen/Qwen2.5-Coder-7B-Instruct` |
| Method | Unsloth + QLoRA |
| Dataset | [kavirubc/weave-bench](https://huggingface.co/datasets/kavirubc/weave-bench) |

## Results (Phase 13)

| Model | Accuracy | Notes |
|-------|----------|-------|
| Qwen2.5-Coder-7B fine-tuned (this model) | **36.2%** | Phase 13 on GoKer held-out set |
| Qwen2.5-Coder-1.5B fine-tuned | 40.2% | Phase 12 (in-distribution evaluation) |

## Usage

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch

base = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-Coder-7B-Instruct",
    torch_dtype=torch.bfloat16,
    device_map="auto",
)
model = PeftModel.from_pretrained(base, "kavirubc/weave-ccwm-qwen2.5-coder-7b-lora")
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-7B-Instruct")
```

Or use the eval script from the repo:
```bash
uv run python scripts/run_eval_unsloth.py \\
    --adapter kavirubc/weave-ccwm-qwen2.5-coder-7b-lora \\
    --val_file dataset/output/kaggle_upload/val_point_dups.jsonl
```

## Citation

```bibtex
@misc{weave2026,
  author = {Hapuarachchi, Kaviru},
  title  = {Weave: Concurrent Code World Models},
  year   = {2026},
  url    = {https://github.com/kaviru2/Weave}
}
```
"""


def upload(repo_id: str, adapter_path: Path, dry_run: bool):
    from huggingface_hub import HfApi, create_repo

    if not adapter_path.exists():
        print(f"ERROR: adapter path not found: {adapter_path}")
        return

    files = list(adapter_path.iterdir())
    total_mb = sum(f.stat().st_size for f in files if f.is_file()) / 1e6

    if dry_run:
        print(f"DRY RUN — would create: {repo_id}")
        print(f"Adapter: {adapter_path}  ({total_mb:.1f} MB)")
        for f in sorted(files):
            print(f"  {f.name}")
        return

    api = HfApi()
    create_repo(repo_id, repo_type="model", exist_ok=True)
    print(f"Repo: https://huggingface.co/models/{repo_id}")

    # Write model card
    card_path = adapter_path / "README.md"
    card_path.write_text(MODEL_CARD)

    print(f"Uploading {total_mb:.1f} MB from {adapter_path}...")
    api.upload_folder(
        folder_path=str(adapter_path),
        repo_id=repo_id,
        repo_type="model",
    )
    print(f"\nDone: https://huggingface.co/{repo_id}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo",    default=REPO_ID_DEFAULT)
    parser.add_argument("--adapter", default=ADAPTER_DEFAULT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    upload(args.repo, Path(args.adapter), args.dry_run)


if __name__ == "__main__":
    main()
