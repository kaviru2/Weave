#!/usr/bin/env python3
from huggingface_hub import HfApi, create_repo
from pathlib import Path

repo_id = "kavirubc/weave-ccwm-qwen25coder-7b-traj-lora"
adapter_path = Path("lora_adapter_phase24")

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
  - trajectory-training
datasets:
  - kavirubc/weave-bench
---

# Weave-CCWM — Qwen2.5-Coder-7B Trajectory LoRA (Phase 24)

A LoRA adapter fine-tuned on **Weave-Bench** using trajectory-level training for next-scheduler-event prediction in concurrent Go programs. Part of the [Weave](https://github.com/kaviru2/Weave) project on Concurrent Code World Models (CCWM).

This model is trained on WeaveChan/WeaveMutex-instrumented programs (Phase 21+ dataset), enabling GoUnblock event prediction beyond the 0% information-theoretic floor of uninstrumented traces.

## Results (Phase 24, in-distribution 545-example traj val set)

| Event | Correct | Total | Accuracy |
|-------|---------|-------|----------|
| GoStart | 140 | 211 | 66.4% |
| GoBlock | 144 | 176 | 81.8% |
| GoCreate | 11 | 56 | 19.6% |
| **GoUnblock** | **9** | **35** | **25.7%** |
| GoEnd | 0 | 25 | 0% |
| GoSched | 0 | 42 | 0% |
| **Overall** | **304** | **545** | **55.8%** |

## What this model does

Given a concurrent Go program and a partial execution trace (goroutine scheduler events), predict the next scheduler event:

```
Input:  Go source + partial trace (GoStart, GoBlock, GoUnblock, GoCreate, GoEnd, GoSched)
Output: {"event_type": "GoBlock", "goroutine_id": 3}
```

## Training

| Setting | Value |
|---------|-------|
| Base model | `Qwen/Qwen2.5-Coder-7B-Instruct` |
| Method | Unsloth + QLoRA, trajectory-level |
| Dataset | [kavirubc/weave-bench](https://huggingface.co/datasets/kavirubc/weave-bench) (`data/train_trajectory.jsonl`) |
| Epochs | 3 |
| train_loss | 0.02501 |
| GPU | RTX 4000 Ada (20GB) |

## Usage

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch

base = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-Coder-7B-Instruct", torch_dtype=torch.float16, device_map="auto"
)
model = PeftModel.from_pretrained(base, "kavirubc/weave-ccwm-qwen25coder-7b-traj-lora")
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-7B-Instruct")
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
