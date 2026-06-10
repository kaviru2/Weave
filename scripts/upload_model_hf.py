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

REPO_ID_DEFAULT  = "kavirubc/weave-ccwm-qwen2.5-coder-1.5b-lora"
ADAPTER_DEFAULT  = "dataset/output/lora_adapter_v2/lora_adapter/checkpoint-516"

MODEL_CARD = """---
language: en
license: apache-2.0
base_model: Qwen/Qwen2.5-Coder-1.5B-Instruct
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

# Weave-CCWM — Qwen2.5-Coder-1.5B LoRA (Phase 12 POC)

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
| Base model | `Qwen/Qwen2.5-Coder-1.5B-Instruct` |
| Method | QLoRA (4-bit NF4 + LoRA r=8) |
| Dataset | [kavirubc/weave-bench](https://huggingface.co/datasets/kavirubc/weave-bench) — 1,377 train / 366 val |
| Epochs | 3 |
| Hardware | NVIDIA A40 48GB |
| train_loss | 0.094 |
| eval_loss | 0.326 |

## Results (Phase 12)

| Model | Accuracy | Notes |
|-------|----------|-------|
| Qwen2.5-Coder-1.5B fine-tuned (this model) | **40.2%** | Phase 12 — 147/366 correct |
| Qwen2.5-Coder-1.5B zero-shot | 0.0% | 0/366 — base model cannot parse task format |
| Gemini zero-shot (Phase 4 baseline) | 56.0% | Different, much larger model — not a direct comparison |

Fine-tuning adds **+40 percentage points** over the same base model zero-shot.
The Gemini 56% is provided for reference only — it used a different, much larger model.

This is an **experimental research checkpoint** published for reproducibility. See the
[GitHub repo](https://github.com/kaviru2/Weave) and
[dataset](https://huggingface.co/datasets/kavirubc/weave-bench) for full context.

## Usage

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch

base = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-Coder-1.5B-Instruct",
    torch_dtype=torch.bfloat16,
    device_map="auto",
)
model = PeftModel.from_pretrained(base, "kavirubc/weave-ccwm-qwen2.5-coder-1.5b-lora")
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-1.5B-Instruct")
```

Or use the eval script from the repo:
```bash
uv run python scripts/run_eval.py \\
    --adapter kavirubc/weave-ccwm-qwen2.5-coder-1.5b-lora \\
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
