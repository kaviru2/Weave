#!/usr/bin/env python3
from huggingface_hub import HfApi, create_repo
from pathlib import Path

repo_id = "kavirubc/weave-ccwm-qwen3-8b-traj-lora"
adapter_path = Path("dataset/output/lora_adapter_qwen3_traj")

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
  - trajectory-training
datasets:
  - kavirubc/weave-bench
---

# Weave-CCWM — Qwen3-8B Trajectory LoRA (Phase 20)

A LoRA adapter fine-tuned on **Weave-Bench** using trajectory-level training for
next-scheduler-event prediction in concurrent Go programs. Part of the
[Weave](https://github.com/kaviru2/Weave) project on Concurrent Code World Models (CCWM).

Unlike the CE baseline, this model is trained on multi-step rolled-out trajectories
(3–5 steps concatenated), teaching it sequence coherence rather than single-step prediction.

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
| Method | Unsloth + QLoRA, trajectory-level |
| Dataset | [kavirubc/weave-bench](https://huggingface.co/datasets/kavirubc/weave-bench) (`data/train_trajectory.jsonl`) |
| Train examples | 680 (multi-step trajectory sequences, 18 with Phase 20 enriched channel/mutex state) |
| Epochs | 3 |

## Results (Phase 20)

| Model | Val set | Accuracy | Notes |
|-------|---------|----------|-------|
| Qwen3-8B base zero-shot | 545 traj val | 37.4% | — |
| Qwen3-8B CE fine-tuned | 798 GoKer | 36.0% | — |
| Qwen2.5-7B traj fine-tuned (Phase 16) | 798 GoKer | 40.1% | 10.48 mean survival steps |
| **Qwen3-8B traj fine-tuned (this model)** | **545 traj val** | **47.2%** | 525 GoKer + 20 Phase 20 instrumented |

**Note on comparability:** The 47.2% is evaluated on `val_trajectory.jsonl` (545 examples: 525 GoKer subset + 20 Phase 20 instrumented with channel/mutex state), while Phase 16's 40.1% used the full 798 GoKer set. Direct comparison requires re-eval on the 798-example set.

**GoUnblock recovery (Phase 20 key finding):** GoUnblock accuracy improved from 0% (Phase 16) to 9% (3/34 correct) on GoKer examples — driven by 18 training examples with enriched channel/mutex state in the prompt. The 3 correct GoUnblock predictions are all on standard GoKer programs (not the instrumented p20val_ examples), confirming the observability signal generalises.

## Usage

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch

base = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen3-8B", torch_dtype=torch.float16, device_map="auto"
)
model = PeftModel.from_pretrained(base, "kavirubc/weave-ccwm-qwen3-8b-traj-lora")
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
