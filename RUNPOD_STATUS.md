# RunPod Training Status

Live tracker for GPU training runs. Update after each run.

---

## Session 2026-06-25 — Phase 23 Stratified CE Training — 🟡 RUNNING

| Field | Value |
|-------|-------|
| **Status** | 🟡 RUNNING (training started ~16:13 UTC, ~5hr est.) |
| **Pod name** | phase-23 |
| **GPU** | L4 (24GB VRAM) |
| **IP / Port** | 213.173.105.25 : 10087 |
| **SSH key** | `~/.ssh/id_runpod` |
| **Cost** | ~$0.39/hr compute + $0.003/hr storage |
| **Network vol** | Weave (40GB) @ `/workspace` — ~31GB used (Qwen3-8B 16GB + Qwen2.5-Coder 15GB) |
| **Model** | Local snapshot: `/workspace/hf_cache/hub/models--Qwen--Qwen3-8B/snapshots/b968826d9c46dd6066d109eabc6255188de91218` |
| **Why local path** | Network vol only has ~7GB free; Unsloth auto-redirects HF ID to download `unsloth/Qwen3-8B-unsloth-bnb-4bit` (~4GB) which hits quota. Local path bypasses redirect. |
| **Train data** | `train_point_dups_balanced.jsonl` (2,004 ex — balanced 200/class) |
| **Val data** | `val_point_dups.jsonl` (1,287 ex, 103 GoKer) |
| **Adapter saved to** | `/workspace/lora_adapter_phase23` (persists on network vol) |
| **Train log** | `/root/train_phase23.log` |

**Goal:** Balanced oversampling (GoSched 4→200 ex, GoEnd 22→200 ex) to validate Class 1 taxonomy claim.

**Monitor:**
```bash
RUNPOD_IP=213.173.105.25 RUNPOD_PORT=10087 python3 scripts/monitor_pods.py
# or raw tail:
ssh root@213.173.105.25 -p 10087 -i ~/.ssh/id_runpod 'tail -f /root/train_phase23.log'
```

**When training done — run eval:**
```bash
RUNPOD_IP=213.173.105.25 RUNPOD_PORT=10087 bash scripts/runpod_eval_phase23.sh
```

**Download results:**
```bash
scp -P 10087 -i ~/.ssh/id_runpod root@213.173.105.25:/root/eval_results_phase23.json eval/results/eval_results_phase23.json
scp -P 10087 -i ~/.ssh/id_runpod -r root@213.173.105.25:/workspace/lora_adapter_phase23 lora_adapter_phase23/
```

---

## Session 2026-06-25 — Phase 22 Expanded Eval — COMPLETE

| Field | Value |
|-------|-------|
| **Status** | DONE — pod terminated 2026-06-25 |
| **GPU** | RTX 2000 Ada (16GB) |
| **Result** | **25.3%** (326/1287), **3.6% GoUnblock** (2/55) on 103 GoKer |
| **Local file** | `eval/results/eval_results_phase22.json` |

---

## Session 2026-06-25 — Phase 22 Dataset Expansion & Inference — PLANNED

### Expanded Evaluation on 103 GoKer Bugs

* **Goal:** Run evaluation (inference) using the existing Phase 21 Qwen3-8B adapter and Phase 16 Qwen2.5-7B adapter on the newly expanded test set of 103 GoKer bugs (including the 37 newly imported ones).
* **Dataset:** 103 real-world GoKer bugs (in `programs/` directory).
* **Status:** Ready to run. Scripts `scripts/eval_unsloth.py` and `scripts/run_eval.py` can be used to execute inference on the expanded dataset on RunPod.

---

## Session 2026-06-24 — Phase 21 Gap Evals (3 pods) — ALL COMPLETE

### Rollout Pod — Phase 21 autoregressive rollout — DONE

| Field | Value |
|-------|-------|
| **Status** | DONE — pod terminated 2026-06-24 |
| **Pod name** | rollout-p21 |
| **GPU** | RTX A4500 |
| **IP / Port** | 213.173.99.29 : 19909 |
| **SSH key** | `~/.ssh/id_runpod` |
| **Result** | **19.64 mean steps** (55/56 programs hit 20-step max) |
| **Local file** | `eval/results/rollout_results_phase21.json` |

---

### Gap 1 Pod — Phase 21 Qwen3-8B on 798 GoKer — DONE

| Field | Value |
|-------|-------|
| **Status** | DONE — pod terminated 2026-06-24 |
| **Pod name** | gap 1 phase 21 |
| **GPU** | RTX A4500 |
| **IP / Port** | 213.173.108.219 : 17053 |
| **Adapter** | `lora_adapter_phase21` (Qwen3-8B traj) |
| **Val file** | `val_point_dups.jsonl` (798 GoKer) |
| **Result** | **30.3%** overall, **4.2% GoUnblock** (2/48) — confirms 0%→4.2% recovery |
| **Local file** | `eval/results/eval_results_phase21_798.json` |

---

### Gap 2 Pod — Phase 16 Qwen2.5-7B on 545 traj val — DONE

| Field | Value |
|-------|-------|
| **Status** | DONE — pod terminated 2026-06-24 |
| **Pod name** | Gap 2 — Phase 16 Qwen2.5-7B |
| **GPU** | RTX A4500 |
| **IP / Port** | 213.173.108.75 : 13488 |
| **Adapter** | `lora_adapter_p16` (Qwen2.5-Coder-7B traj) |
| **Val file** | `val_trajectory.jsonl` (545 traj val, enriched format) |
| **Result** | **58.0%** overall, 20% GoUnblock (near-random on 35 examples — not the clean proof) |
| **Local file** | `eval/results/eval_results_phase16_545.json` |

---

## Phase 21 Training Pod — Qwen3-8B Trajectory — COMPLETE

| Field | Value |
|-------|-------|
| **Status** | DONE — pod terminated 2026-06-24 |
| **Model** | `Qwen/Qwen3-8B` |
| **Dataset** | 970 train trajectories (308 enriched), 545 val |
| **Result (in-dist)** | **49.7%** (271/545) raw, **50.6%** regex-corrected; GoUnblock **11.4%** (4/35) |
| **Adapter (HF)** | `kavirubc/weave-ccwm-qwen3-8b-traj-lora` |
| **Adapter (local)** | `lora_adapter_phase21/` |

---

## Last Run — Phase 16 (Trajectory Training, Qwen2.5-Coder-7B) — COMPLETE

| Field | Value |
|-------|-------|
| **Status** | DONE — pod terminated |
| **Pod name** | Weave 16 |
| **GPU** | NVIDIA A40 48GB |
| **IP / Port** | 69.30.85.16 : 22043 |
| **SSH key** | `~/.ssh/id_runpod` |
| **Started** | 2026-06-18 ~11:15 UTC |
| **Finished** | 2026-06-18 ~17:51 UTC |
| **Cost** | ~$0.44/hr A40 → ~$2.90 total (~6.6 hr: train + rollout) |

**Training config:**
- Model: `Qwen/Qwen2.5-Coder-7B-Instruct`
- Dataset: `train_trajectory.jsonl` (630 multi-turn trajectory examples, 3–5 steps each)
- Epochs: 3 | Batch: 1 | Grad accum: 8 | Seq len: 6144
- Steps: 237 total | Step time: ~32s on A40
- Mode: Trajectory training (multi-turn, ground-truth chaining from split files)

**Results:**
- Mean survival steps: **10.48** (baseline ~1.0, target ≥3) — **10x improvement**
- All 54 GoKer programs survived ≥5 steps
- Leak programs: 10.8 mean survival | Race programs: 9.76 mean survival
- Adapter: `dataset/output/lora_adapter_traj` + HF: `kavirubc/weave-ccwm-qwen2.5-coder-7b-traj-lora`

---

## Previous Run — Phase 12 (Qwen2.5-Coder-1.5B POC) — COMPLETE

| Field | Value |
|-------|-------|
| **Status** | DONE — terminate pod |
| **Pod name** | weave-2 |
| **GPU** | NVIDIA A40 48GB |
| **IP / Port** | 69.30.85.12 : 22013 |
| **SSH key** | `~/.ssh/id_runpod` |
| **Started** | 2026-06-10 ~16:17 UTC |
| **Finished** | 2026-06-11 ~00:05 UTC |
| **Cost** | ~$1.28/hr A40 → ~$9.90 total (7.7 hr: train + zero-shot eval) |

**Training config:**
- Model: `Qwen/Qwen2.5-Coder-1.5B-Instruct`
- Dataset: `train_point_dups.jsonl` (1,377 examples, pre-truncated to 3,972 tokens max)
- Epochs: 3 | Batch: 4 | Grad accum: 2 | Seq len: 4096
- Steps: 516 total | Step time: ~8.9s on A40
- Fix applied: dataset pre-truncation (Copilot Phase 12) — JSON targets no longer cut off

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
| 2026-06-24 | Qwen3-8B traj (Phase 21) | RTX A4500 | 366 / ~3hr | **49.7%** in-dist, GoUnblock **11.4%** | Full instrumentation; 970 train, 308 enriched |
| 2026-06-23 | Qwen3-8B traj (Phase 20) | RTX 4000 Ada | ~200 / ~2hr | **47.2%** traj val | 18 enriched examples; GoUnblock 0%→9% |
| 2026-06-18 | Qwen2.5-Coder-7B traj-trained | A40 48GB | 237 / ~2.5hr | **10.48 survival steps** | Phase 16, trajectory training, 10x coherence improvement |
| 2026-06-10/11 | Qwen2.5-Coder-1.5B fine-tuned | A40 48GB | 516 / ~80min | **40.2%** | Phase 12, fixed truncation bug |
| 2026-06-11 | Qwen2.5-Coder-1.5B zero-shot | A40 48GB | N/A / ~8min | **0.0%** | Base model baseline, 366 examples |
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
