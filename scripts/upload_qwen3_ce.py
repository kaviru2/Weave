#!/usr/bin/env python3
from huggingface_hub import HfApi, create_repo
from pathlib import Path

repo_id = "kavirubc/weave-ccwm-qwen3-8b-ce-lora"
adapter_path = Path("dataset/output/lora_adapter_qwen3_ce")

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
datasets:
  - kavirubc/weave-bench
---

# Weave-CCWM — Qwen3-8B LoRA (Phase 20 CE)

A LoRA adapter fine-tuned on **Weave-Bench** for next-scheduler-event prediction in
concurrent Go programs. Part of the [Weave](https://github.com/kaviru2/Weave) project
on Concurrent Code World Models (CCWM).

## What this model does

Given a concurrent Go program and a partial execution trace (goroutine scheduler events),
predict the next scheduler event:

```
Input:  Go source + partial trace (GoStart, GoBlock, GoUnblock, GoCreate, GoEnd, GoSched)
Output: {"event_type": "GoBlock", "goroutine_id": 3, "reasoning": "...", "confidence": "high"}
```

## Training

| Setting | Value |
|---------|-------|
| Base model | `Qwen/Qwen3-8B` |
| Method | Unsloth + QLoRA |
| Dataset | [kavirubc/weave-bench](https://huggingface.co/datasets/kavirubc/weave-bench) |
| Train examples | 680 (point prediction) |
| Epochs | 3 |
| train_loss | 0.0707 |

## Results (Phase 20, GoKer held-out, 798 examples)

| Model | Accuracy |
|-------|----------|
| Qwen3-8B base zero-shot | 24.9% |
| **Qwen3-8B CE fine-tuned (this model)** | **36.0%** |
| Qwen2.5-7B CE fine-tuned (Phase 13) | 36.2% |
| Qwen2.5-7B traj fine-tuned (Phase 16) | 40.1% |

## Usage

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch

base = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen3-8B", torch_dtype=torch.float16, device_map="auto"
)
model = PeftModel.from_pretrained(base, "kavirubc/weave-ccwm-qwen3-8b-ce-lora")
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

(adapter_path / "README.md").write_text(MODEL_CARD)

api = HfApi()
create_repo(repo_id, repo_type="model", exist_ok=True)
print(f"Uploading to {repo_id}...")
api.upload_folder(folder_path=str(adapter_path), repo_id=repo_id, repo_type="model")
print(f"Done: https://huggingface.co/{repo_id}")
