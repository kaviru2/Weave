#!/usr/bin/env python3
from huggingface_hub import HfApi, create_repo
from pathlib import Path

repo_id = "kavirubc/weave-ccwm-qwen3-8b-stratified-lora"
adapter_path = Path("lora_adapter_phase23")

MODEL_CARD = """---
language: en
license: apache-2.0
base_model: Qwen/Qwen3-8B
tags:
  - lora
  - qlora
  - concurrent-programming
  - program-analysis
  - go
  - world-model
  - peft
  - stratified-training
datasets:
  - kavirubc/weave-bench
---

# Weave-CCWM — Qwen3-8B Stratified Trajectory LoRA (Phase 23)

A LoRA adapter fine-tuned on **Weave-Bench** using stratified trajectory-level training for next-scheduler-event prediction in concurrent Go programs. Part of the [Weave](https://github.com/kaviru2/Weave) project on Concurrent Code World Models (CCWM).

This model addresses the Class 1 distributional gaps (e.g., `GoSched` and `GoEnd` events) by using a balanced training mix (200 examples per event type, 2,004 train / 1,287 val).

## What this model does

Given a concurrent Go program and a partial execution trace (goroutine scheduler events), predict the next scheduler event:

```
Input:  Go source + partial trace (GoStart, GoBlock, GoUnblock, GoCreate, GoEnd, GoSched)
Output: {"event_type": "GoBlock", "goroutine_id": 3, "reasoning": "...", "confidence": "high"}
```

## Training

| Setting | Value |
|---------|-------|
| Base model | `Qwen/Qwen3-8B` |
| Method | Unsloth + QLoRA, stratified trajectory-level |
| Dataset | [kavirubc/weave-bench](https://huggingface.co/datasets/kavirubc/weave-bench) (`data/train_point_dups_balanced.jsonl`) |
| Train examples | 2,004 (stratified/balanced across event classes) |
| Epochs | 3 |
| train_loss | 0.0255 |

## Usage

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch

base = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen3-8B", torch_dtype=torch.float16, device_map="auto"
)
model = PeftModel.from_pretrained(base, "kavirubc/weave-ccwm-qwen3-8b-stratified-lora")
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3-8B")
```

## Citation

```bibtex
@misc{weave2026,
  author = {Hapuarachchi, Kaviru},
  title  = {Weave: Concurrent Code World Models},
  year   = {2026},
  url    = {https://arxiv.org/abs/2606.17508}
}
```
"""

if not adapter_path.exists():
    print(f"ERROR: adapter path not found: {adapter_path}")
    exit(1)

(adapter_path / "README.md").write_text(MODEL_CARD)

api = HfApi()
create_repo(repo_id, repo_type="model", exist_ok=True)
print(f"Uploading to {repo_id}...")
api.upload_folder(
    folder_path=str(adapter_path),
    repo_id=repo_id,
    repo_type="model",
    ignore_patterns=["checkpoint-*"]
)
print(f"Done: https://huggingface.co/{repo_id}")
