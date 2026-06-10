# RunPod Training Status

Live tracker for GPU training runs. Update after each run.

---

## Current Run — Phase 12 (Qwen2.5-Coder-1.5B POC)

| Field | Value |
|-------|-------|
| **Status** | 🟡 RUNNING |
| **Pod name** | weave-2 |
| **GPU** | NVIDIA A40 48GB |
| **IP / Port** | 69.30.85.12 : 22013 |
| **SSH key** | `~/.ssh/id_runpod` |
| **Started** | 2026-06-10 ~16:17 UTC |
| **ETA** | ~18:00 UTC (~80 min from start) |
| **Cost** | ~$1.28/hr A40 → ~$1.70 total |

**Training config:**
- Model: `Qwen/Qwen2.5-Coder-1.5B-Instruct`
- Dataset: `train_point_dups.jsonl` (1,377 examples, pre-truncated to 3,972 tokens max)
- Epochs: 3 | Batch: 4 | Grad accum: 2 | Seq len: 4096
- Steps: 516 total | Step time: ~8.9s on A40
- Fix applied: dataset pre-truncation (Copilot Phase 12) — JSON targets no longer cut off

**Monitor:**
```bash
ssh root@69.30.85.12 -p 22013 -i ~/.ssh/id_runpod "tail -5 /root/train.log"
# or attach to live session:
ssh root@69.30.85.12 -p 22013 -i ~/.ssh/id_runpod
tmux attach -t train
```

**Download results when done:**
```bash
scp -P 22013 -i ~/.ssh/id_runpod root@69.30.85.12:/root/eval_results.json eval/results/eval_results_runpod.json
scp -P 22013 -i ~/.ssh/id_runpod -r root@69.30.85.12:/root/lora_adapter dataset/output/lora_adapter_v2
```

---

## How to Start a New Run (Next Time)

```bash
# Set pod details from RunPod dashboard, then:
RUNPOD_IP=<ip> RUNPOD_PORT=<port> bash scripts/runpod_deploy.sh
```

Script handles everything: file upload, dep install, tmux launch, progress monitoring commands.

---

## Run History

| Date | Model | GPU | Steps/time | Accuracy | Notes |
|------|-------|-----|-----------|----------|-------|
| 2026-06-10 | Qwen2.5-Coder-1.5B | A40 48GB | 516 / ~80min | TBD | Phase 12 POC, fixed truncation bug |
| 2026-06-09 | Qwen2.5-Coder-1.5B | Kaggle T4 | ~1035 / 2hr | 91.7% val token acc* | Phase 10, **had truncation bug** |

*Phase 10 val token accuracy was misleading — SFTTrainer was right-truncating 87% of examples
at 2048 tokens, cutting the JSON target. Model learned trace continuation, not next-event prediction.

---

## Pinned Dep Versions (RunPod PyTorch 2.4.x template)

```
transformers==4.46.3
peft==0.13.2
trl==0.11.4
bitsandbytes==0.44.1
accelerate==0.34.2
datasets==3.0.1
```

If RunPod updates to PyTorch 2.5+, remove version pins — latest packages work fine.
