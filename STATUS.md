# Weave — Project Status

> Read this first when picking up on a new machine. Then read CLAUDE.md for the full plan.

### Recent Updates & Changelog
- **2026-06-18**: **Phase 16 complete.** Trajectory-trained model achieves **10.48 mean survival steps** (baseline ~1.0, target ≥3) — 10x improvement. All 54 GoKer programs survive ≥5 steps. Adapter: `kavirubc/weave-ccwm-qwen2.5-coder-7b-traj-lora`.
- **2026-06-18**: arXiv preprint live at https://arxiv.org/abs/2606.17508 (cs.PL primary, cs.SE cross-list). Retargeted Weave to **ICSE 2027 NIER** (New Ideas and Emerging Results). Given the modest scale of our corpus (130 programs) and the openly-reported 35-36% accuracy ceiling, the NIER track's framing of "honest limitations + concrete future work" is a much better fit than the main Research Track. Will focus next on **Phase 16** (Trajectory-level training) to strengthen multi-step coherence evidence before writing.

## Current State

**Paper published.** Preprint live on Zenodo (DOI: 10.5281/zenodo.20682004) and arXiv (arXiv:2606.17508).
Paper source and PDF in `LaTexPackage-1/`.

**Phases 14 + 15 complete.** KL model: 35.8% on GoKer held-out. Multi-step coherence
probe: mean survival ~1 step, entropy 0.945 bits (leak) vs 0.773 bits (race). All results
in paper and preprint.

---

## Results Summary

| Model | Dataset | Accuracy | Notes |
|-------|---------|----------|-------|
| Gemini (zero-shot, Phase 4) | in-distribution | 56.0% | Large model, no fine-tuning |
| Qwen2.5-Coder-1.5B (zero-shot) | in-distribution | 29.8% | Corrected from 0.0% (markdown-fence bug) |
| Qwen2.5-Coder-1.5B (fine-tuned, Phase 12) | in-distribution | 40.2% | After truncation bug fix |
| **Qwen2.5-Coder-7B (zero-shot)** | GoKer held-out | **28.6%** | Corrected from 0.0% (markdown-fence bug) |
| **Gemini 3.5 Flash (zero-shot, thinking=auto)** | **GoKer held-out** | **34.8%** | Beats 7B zero-shot, below fine-tuned |
| **Qwen2.5-Coder-7B (fine-tuned, Phase 13)** | **GoKer held-out** | **36.2%** | Fine-tuning beats Gemini Flash |
| Gemini 3.5 Flash, no thinking | GoKer held-out | 35.2% | Slightly above thinking variant |
| **Qwen2.5-Coder-7B KL-trained (Phase 14)** | GoKer held-out | **35.8%** | Matches CE, better calibration |
| **Qwen2.5-Coder-7B traj-trained (Phase 16)** | **GoKer held-out** | **40.1%** | **Best OOD result — trajectory training beats all prior models** |

**Key comparison:** Fine-tuned 7B (36.2%) > Gemini Flash zero-shot (34.8%) > 7B zero-shot (28.6%).
Training on 945 hand-crafted trace examples generalises better to real-world bugs than a large
general model zero-shot.

**Phase 16 — Trajectory training results (coherence + accuracy):**

| Model | Single-step Accuracy | Mean Survival Steps | Notes |
|-------|---------------------|---------------------|-------|
| Qwen2.5-Coder-7B KL-trained (Phase 14/15) | 35.8% | ~1.0 | Single-step training |
| **Qwen2.5-Coder-7B traj-trained (Phase 16)** | **40.1%** | **10.48** | 3–5 step trajectory training |

Trajectory training is a **strict improvement**: better single-step accuracy (+3.9pp over Phase 13) AND dramatically better coherence (10x survival steps). No tradeoff.

Breakdown by pattern: channel 34.3%, mutex 40.7%, select 41.8%
Leak programs: 10.8 mean survival | Race programs: 9.76 mean survival | Entropy ~1.49 bits

---

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
- [x] **Phase 14 — KL distribution-loss training (35.8% GoKer, ECE 0.169)**
- [x] Phase 15 — Autoregressive rollout (coherence probe: ~1 step survival)
- [x] **Phase 16 — Trajectory-Level Training: mean survival 10.48 steps (10x over baseline ~1.0, target was ≥3)**

---

## Immediate Next Steps

### 1. Write and Format the NIER Submission
- Port the paper content from the Springer `svproc` format (`LaTexPackage-1/weave.tex`) to the new IEEEtran 10pt conference format (`LaTexPackage-1/IEEEtran/IEEE-conference-template-062824.tex`).
- Strict limit: **4 pages main text + 1 page references**.
- Add the required **"Future Plans"** section outlining how Weave scales to a full paper (e.g., extending to Ballerina, capturing mutex/channel buffer state, etc.).
- Ensure strict adherence to double-anonymous guidelines (no author names, third-person self-citation, etc.).

### 3. Submission Details (ICSE 2027 NIER)
- **Venue**: ICSE 2027 NIER (New Ideas and Emerging Results)
- **Deadline**: Fri 23 Oct 2026 (AoE)
- **Format**: Strictly 4 pages main text + 1 page references (IEEEtran 10pt conference template, no compsoc options)
- **Anonymization**: Double-anonymous review guidelines apply. No mention of "submitted to ICSE 2027" on public preprints.

---

## Artifacts

| Artifact | Location |
|----------|----------|
| **LoRA adapter (Phase 16, 7B traj)** | `dataset/output/lora_adapter_traj/` |
| **Rollout results (Phase 16)** | `eval/results/rollout_results_traj.json` (10.48 mean survival) |
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
| **HF model (7B traj, Phase 16)** | https://huggingface.co/kavirubc/weave-ccwm-qwen2.5-coder-7b-traj-lora |
| HF dataset | https://huggingface.co/datasets/kavirubc/weave-bench |
| Preprint (Zenodo) | https://doi.org/10.5281/zenodo.20682004 |

---

## Compute

**RunPod** is the primary GPU compute. SSH key: always `~/.ssh/id_runpod` (ignore what the pod UI shows).
Template: `runpod-torch-v240`. Set `HF_HOME=/workspace/hf_cache` on pod before downloading models.
tmux not pre-installed — use `nohup ... &` or install it first.

**Deploy training:** `RUNPOD_IP=<ip> RUNPOD_PORT=<port> RUNPOD_KEY=~/.ssh/id_runpod bash scripts/runpod_deploy.sh`
**Deploy eval:** `RUNPOD_IP=<ip> RUNPOD_PORT=<port> RUNPOD_KEY=~/.ssh/id_runpod bash scripts/runpod_eval_traj.sh`

**GPU guidance (current pricing):**
- RTX 4000 Ada (20GB, ~$0.26/hr) — first choice; Phases 13, 16
- A40 (48GB, ~$0.44/hr) — fallback if RTX 4000 Ada unavailable; Phase 12
- SSH key: `~/.ssh/id_runpod`
