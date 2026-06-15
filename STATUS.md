# Weave — Project Status

> Read this first when picking up on a new machine. Then read CLAUDE.md for the full plan.

## Current State

**Paper submitted as preprint** to Zenodo (DOI: 10.5281/zenodo.20682004) and pending
arXiv endorsement (cs.PL primary, cs.SE cross-list). Paper source in `LaTexPackage-1/`.

**Phase 14 KL training IN PROGRESS** on RTX 4000 Ada (pod `weave p14515`,
`157.157.221.29:22206`, key `~/.ssh/id_runpod`). Estimated ~4h 50min total, ~$1.30.
Phase 15 rollout script written and will auto-run on the same pod after training.

**Gemini GoKer baselines:** Flash done (34.8%). Pro running locally with `--no-thinking`.

---

## Results Summary

| Model | Dataset | Accuracy | Notes |
|-------|---------|----------|-------|
| Gemini (zero-shot, Phase 4) | in-distribution | 56.0% | Large model, no fine-tuning |
| Qwen2.5-Coder-1.5B (zero-shot) | in-distribution | 29.8% | Corrected from 0.0% (markdown-fence bug) |
| Qwen2.5-Coder-1.5B (fine-tuned, Phase 12) | in-distribution | 40.2% | After truncation bug fix |
| **Qwen2.5-Coder-7B (zero-shot)** | GoKer held-out | **28.6%** | Corrected from 0.0% (markdown-fence bug) |
| **Gemini 3.5 Flash (zero-shot, thinking=auto)** | **GoKer held-out** | **34.8%** | Beats 7B zero-shot, below fine-tuned |
| **Qwen2.5-Coder-7B (fine-tuned, Phase 13)** | **GoKer held-out** | **36.2%** | **Best OOD result — fine-tuning beats Gemini Flash** |
| Gemini 3.1 Pro (zero-shot, no thinking) | GoKer held-out | pending | Running locally |
| **Qwen2.5-Coder-7B KL-trained (Phase 14)** | GoKer held-out | pending | Training now |

**Key comparison:** Fine-tuned 7B (36.2%) > Gemini Flash zero-shot (34.8%) > 7B zero-shot (28.6%).
Training on 945 hand-crafted trace examples generalises better to real-world bugs than a large
general model zero-shot.

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
- [x] Phase 13 — GoKer held-out split + Unsloth 7B training (36.2% GoKer OOD)
- [ ] **Phase 14 — KL distribution-loss training (RUNNING on RunPod)**
- [ ] Phase 15 — Autoregressive rollout (script ready, runs after Phase 14)

---

## Immediate Next Steps

### 1. Wait for Phase 14 + 15 to finish (~4h 50min from start)

Monitor:
```bash
ssh root@157.157.221.29 -p 22206 -i ~/.ssh/id_runpod 'tail -5 /root/train.log'
```

Download when done:
```bash
scp -P 22206 -i ~/.ssh/id_runpod root@157.157.221.29:/root/eval_results.json eval/results/eval_p14_goker.json
scp -P 22206 -i ~/.ssh/id_runpod root@157.157.221.29:/root/rollout_results.json eval/results/rollout_p15_goker.json
scp -P 22206 -i ~/.ssh/id_runpod -r root@157.157.221.29:/root/lora_adapter_kl dataset/output/lora_adapter_kl
```

### 2. Collect Gemini Pro results
- `eval/gemini_zeroshot_goker.py --models gemini-3.1-pro-preview --no-thinking` running locally
- Update STATUS.md + README.md with final numbers

### 3. Upload Phase 14 adapter to HuggingFace
- `dataset/output/lora_adapter_kl/` → `kavirubc/weave-ccwm-qwen2.5-coder-7b-kl-lora`
- Script: `uv run python scripts/upload_model_hf.py`

### 4. Upload updated dataset to HuggingFace
- GoKer-split JSONL with `program_id`/`split_percent` fields → `kavirubc/weave-bench`
- Script: `uv run python scripts/upload_dataset_hf.py`

### 5. Merge PR #13 and open Phase 14 PR
- PR #13 covers Phases 13–15 (branch `phase-13-unsloth-7b`)
- Merge after training results are confirmed

---

## Artifacts

| Artifact | Location |
|----------|----------|
| LoRA adapter (Phase 12, 1.5B) | `dataset/output/lora_adapter_v2/` |
| LoRA adapter (Phase 13, 7B CE) | `dataset/output/lora_adapter_v3/` (154MB) |
| **LoRA adapter (Phase 14, 7B KL)** | `dataset/output/lora_adapter_kl/` (pending download) |
| Eval results (7B fine-tuned CE, GoKer) | `eval/results/eval_results_runpod_7b.json` (36.2%) |
| **Eval results (Gemini Flash, GoKer)** | `eval/results/gemini_goker_gemini-3_5-flash_thinking-1.json` (34.8%) |
| Eval results (7B zero-shot, GoKer) | `eval/results/eval_zeroshot_7b_goker.json` (28.6%) |
| Eval results (1.5B fine-tuned, in-dist) | `eval/results/eval_results_runpod.json` (40.2%) |
| HF model (1.5B CE) | https://huggingface.co/kavirubc/weave-ccwm-qwen2.5-coder-1.5b-lora |
| HF model (7B CE, Phase 13) | https://huggingface.co/kavirubc/weave-ccwm-qwen2.5-coder-7b-lora |
| HF model (7B KL, Phase 14) | https://huggingface.co/kavirubc/weave-ccwm-qwen2.5-coder-7b-kl-lora |
| HF dataset | https://huggingface.co/datasets/kavirubc/weave-bench |
| Preprint (Zenodo) | https://doi.org/10.5281/zenodo.20682004 |

---

## Compute

**RunPod** is the primary GPU compute.

**Phase 14 (current):** `USE_KL=1 RUNPOD_IP=<ip> RUNPOD_PORT=<port> RUNPOD_KEY=~/.ssh/id_runpod bash scripts/runpod_deploy.sh`

**GPU guidance (current pricing):**
- RTX 4000 Ada (20GB, ~$0.27/hr) — 7B QLoRA via Unsloth, proven for Phase 13/14
- A40 (48GB, ~$0.44/hr) — used for Phase 12; good fallback if RTX 4000 Ada unavailable
- SSH key: `~/.ssh/id_runpod`
