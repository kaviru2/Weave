# Weave — Project Status

> Read this first when picking up on a new machine. Then read CLAUDE.md for the full plan.

## Current State

**Phase 13 complete. All pending baselines complete.** Qwen2.5-Coder-7B fine-tuned (36.2%
GoKer OOD), zero-shot baseline measured (0.0%), Gemini GoKer eval running locally.
7B adapter uploaded to HuggingFace. **Next:** Phase 14 distribution-loss training (KL vs
empirical distributions).

---

## Results Summary

| Model | Dataset | Accuracy | Notes |
|-------|---------|----------|-------|
| Gemini (zero-shot, Phase 4) | in-distribution | 56.0% | Large model, no fine-tuning |
| Qwen2.5-Coder-1.5B (zero-shot) | in-distribution | **29.8%** | Corrected — was 0.0% due to markdown-fence parsing bug |
| Qwen2.5-Coder-1.5B (fine-tuned, Phase 12) | in-distribution | 40.2% | After truncation bug fix (+10.4pp over zero-shot) |
| **Qwen2.5-Coder-7B (fine-tuned, Phase 13)** | **GoKer held-out** | **36.2%** | **First clean OOD result (+7.6pp over zero-shot)** |
| Qwen2.5-Coder-7B (zero-shot) | GoKer held-out | **28.6%** | Corrected — was 0.0% due to markdown-fence parsing bug |
| Gemini 3.5 Flash (zero-shot, thinking) | GoKer held-out | pending | Running locally |
| Gemini 3.1 Pro (zero-shot, thinking) | GoKer held-out | pending | Running locally after Flash |

**Distribution learning results (Phase 7–8):**

| Metric | Value |
|--------|-------|
| Point-prediction ECE (Phase 4 baseline) | 0.2050 |
| Distribution zero-shot ECE, no thinking | 0.1833 |
| Distribution zero-shot ECE, thinking=1024 | **0.1689** |
| Entropy–nondeterminism Spearman ρ | 0.412, p=0.007 |
| Select-block leak signature P(GoUnblock)=0 | confirmed for 3/3 programs |

---

## Phase Checklist

- [x] Phase 1 — Go Trace Collector (`tracer/`)
- [x] Phase 2 — Program Suite (26 hand-crafted programs)
- [x] Phase 3 — Dataset Builder (`dataset/builder.go`)
- [x] Phase 4 — Gemini Zero-Shot Eval — 56% accuracy, 0% bug detection
- [x] Phase 5 — Results Analysis
- [x] Phase 6 — Distribution Aggregation (`dataset/aggregate.py`)
- [x] Phase 7 — Distribution Zero-Shot Eval (ECE 0.169 with thinking)
- [x] Phase 8 — Dirichlet Analysis (leak signature confirmed)
- [x] Phase 9 — Dataset Expansion (+10 leak programs, 26 total)
- [x] Phase 9b — Select-block boundary test (multi-case confirmed)
- [x] Phase 10 — QLoRA Fine-tuning (had truncation bug)
- [x] Phase 11 — Dataset Expansion II (+38 gen + 66 GoKer = 130 programs total)
- [x] Phase 12 — Truncation fix + retrain on A40 (40.2% in-dist accuracy)
- [x] Phase 13 — GoKer held-out split + Unsloth 7B training (36.2% GoKer accuracy)
- [ ] Phase 14 — Distribution-loss training (KL vs empirical distributions)
- [ ] Phase 15 — Autoregressive rollout (`eval/simulation_rollout.py`)

---

## Immediate Next Steps

### 1. Finish Gemini GoKer eval (in progress)
- Gemini 3.5 Flash + 3.1 Pro running locally via `eval/gemini_zeroshot_goker.py`
- Results save to `eval/results/gemini_goker_*.json` automatically
- Update STATUS.md + README.md with final numbers once complete

### 2. Upload dataset to HuggingFace
- GoKer-split JSONL in `dataset/output/kaggle_upload/` → `kavirubc/weave-bench`
- Script: `uv run python scripts/upload_dataset_hf.py`

### 3. Phase 14 — Distribution-loss training
- Train the 7B model using KL divergence against empirical distributions in `aggregated.json`
- Implement custom trainer with KL loss in `dataset/train_lora_kl.py`
- This is the core research contribution distinguishing Weave from standard fine-tuning

### 4. Phase 15 — Autoregressive rollout
- Multi-step trajectory simulation on GoKer programs
- Measure trajectory divergence from ground truth

---

## Artifacts

| Artifact | Location |
|----------|----------|
| LoRA adapter (Phase 12, 1.5B) | `dataset/output/lora_adapter_v2/` |
| **LoRA adapter (Phase 13, 7B)** | `dataset/output/lora_adapter_v3/` (154MB) |
| Eval results (1.5B fine-tuned) | `eval/results/eval_results_runpod.json` (40.2%) |
| **Eval results (7B fine-tuned, GoKer)** | `eval/results/eval_results_runpod_7b.json` (36.2%) |
| Eval results (1.5B zero-shot) | `eval/results/eval_results_zeroshot.json` (0.0%) |
| **Eval results (7B zero-shot, GoKer)** | `eval/results/eval_zeroshot_7b_goker.json` (0.0%) |
| HF model (1.5B) | https://huggingface.co/kavirubc/weave-ccwm-qwen2.5-coder-1.5b-lora |
| **HF model (7B)** | https://huggingface.co/kavirubc/weave-ccwm-qwen2.5-coder-7b-lora |
| HF dataset | https://huggingface.co/datasets/kavirubc/weave-bench |

---

## Compute

**RunPod** is the primary GPU compute. Deploy: `RUNPOD_IP=<ip> RUNPOD_PORT=<port> bash scripts/runpod_deploy.sh`

**GPU guidance:**
- RTX 4000 Ada (20GB, ~$0.76/hr) — 7B QLoRA via Unsloth (Phase 13 used this)
- A40 (48GB, ~$1.28/hr) — used for Phase 12 (1.5B)
- SSH key: `~/.ssh/id_runpod`
