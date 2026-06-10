# Weave — Project Status

> Read this first when picking up on a new machine. Then read CLAUDE.md for the full plan.

## Current State

**Phase 12 complete.** Training run + zero-shot baseline both done (RunPod A40, 2026-06-10/11).
**Active branch:** `phase-12-modal-train` — awaiting PR merge to main.

Qwen zero-shot result: **0.0%** (0/366). Fine-tuned result: **40.2%** (147/366). Fine-tuning adds 40+ percentage points over the base model on this task.

---

## Results Summary

| Model | Accuracy | Notes |
|-------|----------|-------|
| Gemini (zero-shot, Phase 4) | 56.0% | Large model, no fine-tuning, different base |
| Qwen2.5-Coder-1.5B (zero-shot) | **0.0%** | 0/366 — base model cannot parse task format |
| Qwen2.5-Coder-1.5B (fine-tuned, Phase 12) | **40.2%** | After truncation bug fix; 147/366 correct |
| Qwen2.5-Coder-1.5B (Phase 10, had truncation bug) | 91.7% val token acc* | Misleading metric |

*Phase 10 val token accuracy was inflated — SFTTrainer right-truncated 87% of examples
at 2048 tokens, cutting the JSON target. The model learned trace continuation, not prediction.
Phase 12 fixes this with dataset pre-truncation (`max_seq_length` raised to 4096).

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

- [x] Phase 1 — Go Trace Collector (`tracer/`) — merged to main
- [x] Phase 2 — Program Suite (26 hand-crafted programs) — merged to main
- [x] Phase 3 — Dataset Builder (`dataset/builder.go`) — merged to main
- [x] Phase 4 — Gemini Zero-Shot Eval — merged to main; 56% accuracy, 0% bug detection
- [x] Phase 5 — Results Analysis — merged to main
- [x] Phase 6 — Distribution Aggregation (`dataset/aggregate.py`) — merged to main
- [x] Phase 7 — Distribution Zero-Shot Eval (ECE 0.169 with thinking) — merged to main
- [x] Phase 8 — Dirichlet Analysis (leak signature confirmed) — merged to main
- [x] Phase 9 — Dataset Expansion (+10 leak programs, 26 total) — merged to main
- [x] Phase 9b — Select-block boundary test (multi-case confirmed) — merged to main
- [x] Phase 10 — QLoRA Fine-tuning (had truncation bug) — merged to main
- [x] Phase 11 — Dataset Expansion II (+38 gen + 66 GoKer = 130 programs total) — on branch
- [x] Phase 12 — Truncation fix + retrain on A40 (40.2% accuracy) — on branch, pending merge

---

## Immediate Next Steps

### 1. Merge phase-12-modal-train → main
Open PR, merge. All phases will be on main.

### 3. Rebuild dataset with GoKer as held-out test set (Phase 13)
The current train/val split is random across all programs — not a clean research eval.
For a publishable result:
- **Train set**: hand-crafted programs (`01_`–`26_`) + generated (`gen_*`)
- **Test set**: GoKer real-world bugs (`goker_*`, held out entirely from training)
- Rebuild `dataset/builder.go` split logic, regenerate JSONL, retrain

This gives the headline claim: *"trained on synthetic programs, evaluated on real
concurrency bugs from CockroachDB, Kubernetes, etcd, gRPC — never seen during training."*

### 4. Diagnose 40.2% underperformance
The `concurrency_pattern` and `nondeterminism` fields show as "unknown" in eval output,
suggesting JSONL metadata is missing. Check `dataset/prepare_finetuning.py` output schema.
Also compare to Qwen zero-shot baseline once that result lands.

### 5. Distribution-loss training (Phase 14)
Retrain with KL divergence against empirical distributions (Phase 6 aggregated.json)
instead of cross-entropy on a single run. This is the core research contribution.

---

## Artifacts

| Artifact | Location |
|----------|----------|
| LoRA adapter (Phase 12) | `dataset/output/lora_adapter_v2/lora_adapter/checkpoint-516/` |
| Eval results (fine-tuned) | `eval/results/eval_results_runpod.json` |
| Eval results (zero-shot) | `eval/results/eval_results_zeroshot.json` — 0.0% (0/366) |
| HF model | https://huggingface.co/kavirubc/weave-ccwm-qwen2.5-coder-1.5b-lora |
| HF dataset | https://huggingface.co/datasets/kavirubc/weave-bench |

---

## Compute

**RunPod** is the primary GPU compute. See `RUNPOD_STATUS.md` for pod details.
Deploy a new run: `RUNPOD_IP=<ip> RUNPOD_PORT=<port> bash scripts/runpod_deploy.sh`

**Current pod** (terminate after zero-shot eval finishes):
- IP: 69.30.85.12 | Port: 22013 | Key: `~/.ssh/id_runpod`
- GPU: A40 48GB | Status: running zero-shot eval
