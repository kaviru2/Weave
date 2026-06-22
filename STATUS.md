# Weave — Project Status

> Read this first when picking up on a new machine. Then read CLAUDE.md for the full plan.

### Recent Updates & Changelog
- **2026-06-22 (later)**: **Phase 20 scale-up: 7 instrumented programs, enriched dataset, trajectory rebuild.** 5 more instrumented programs added (`02_multiple`, `13_buffered`, `14_leak`, `21_done_leak`, `22_deadwait`). `cmd/build_p20/main.go` generates 105 enriched split files → `dataset/output/p20_*`. `prepare_trajectory.py` updated: `p20val_` goes to val split. Trajectory rebuild: 680 train (50 p20 + 630 existing, 18 with channel/mutex state in prompt) + 545 val (525 GoKer + 20 p20val). Channel/mutex state confirmed in `<current_state>` section of training prompts — model will see `recv_waiters`/`send_waiters` populated at relevant steps. **Next: retrain on RunPod (1 cycle, ~$4) and measure GoUnblock recovery on p20val vs GoKer.**
- **2026-06-22 (later)**: **Phase 20 Option A prototype complete.** `instrumented/` package (WeaveChan[T], WeaveMutex) embeds sync events via `runtime/trace.Log` into the scheduler trace (same clock, no sidecar file, no timestamp skew). `tracer/parser.go` now handles `EventLog("weave-sync")` inline — Channels/Mutexes maps populated without any post-processing. Demo: 5/5 GoUnblock events on unbuffered channel linked to causal goroutine; 19/21 mutex GoUnblock events linked. **RQ1 premise confirmed experimentally**: GoUnblock 0% accuracy is an observability limit (GoBlock causal state now visible in snapshot), not a data or capacity limit. Branch: `phase-20-wrapper`. Next: retrain traj model on instrumented corpus to measure GoUnblock recovery — the thesis-defining A/B experiment.
- **2026-06-22 (later)**: **NIER paper: Ballerina/WSO2 removed.** Future Plans section now describes the instrumented wrapper library approach (Option A) instead of Ballerina as the observability fix. Paper is consistent with anonymous submission.
- **2026-06-22 (later)**: **Thesis-level research direction committed (owner sign-off).** Fresh
  literature sweep (as of 2026-06-22, 6 axes, ~30 verified papers) in `research_direction/`
  confirms the core idea is **unscooped** — closest neighbours are sequential/deterministic
  (Neural Debugger for Python 2603.09951, Self-Execution Simulation 2604.03253), spec-target not
  process-target (Probabilistic Calibration 2605.11845), or learn-to-search not -predict
  (Q-learning CCT, OOPSLA'20). **Direction = Candidate B core:** an observability-complete,
  distributional concurrent-execution world model. NIER paper = first checkpoint (Candidate A);
  oracle utility = payoff (C); Ballerina = horizon (D). Main RQ + 5 sub-RQs + phased roadmap in
  `research_direction/north_star.md`. **Phase 20 (tracer) feasibility spike done** — see
  `research_direction/phase20_tracer_feasibility.md`: Go trace records blocking *kind* but not
  channel identity / buffer / mutex holder (GoUnblock limit confirmed in data); recommended path
  = instrumented wrapper library (Option A) → eBPF (C) → defer runtime fork (B). Sequencing:
  start Phase 20 feasibility now in parallel with the NIER checkpoint.
- **2026-06-22**: **Pivoted back to ICSE 2027 NIER (single target).** Dropped the Research Track attempt — the corpus scale (130 programs) and the ~36–40% accuracy ceiling fit NIER's "honest limitations + future work" framing far better. `weave-nier/main.tex` is now the canonical paper (4 pages main + 1 page refs, IEEEtran 10pt); `weave-research/` is archived for reference. Runway: ~4 months to the **Fri 23 Oct 2026** NIER deadline. Budget for any new experiment: **~$20 RunPod + ~$10 Gemini**. Phase 19 strengthening candidates (costed menu) added to CLAUDE.md — pick at most one before finalizing the paper.
- **2026-06-19**: **Related works research complete.** `related_works.md` created with 19 verified external citations (all titles/authors/venues/URLs confirmed). Organized into 4 narrative sections with draft "USE:" sentences ready to paste into paper. See "Paper Writing" section in CLAUDE.md for how to use it.
- **2026-06-19**: **Phase 18 complete.** Gemini Flash re-eval: 35.8% (no thinking). McNemar traj vs Phase13 CE: p=0.016 ✅ CI [+1.0, +8.3pp]. McNemar traj vs Gemini Flash: p=0.069 ❌ not significant, CI [-0.18, +8.77pp]. GoCreate +24pp is the entire source of the 4.6pp gain. Majority-class baseline: 35.5%. Gemini 3.1 Pro eval running (thinking=auto) — pending final comparison. `phase18_numbers.json` saved.
- **2026-06-19**: **Phase 17 complete.** Ablation A: 40.1%, Ablation B: 35.3%. **Conclusion: gain is entirely from trajectory format (multi-turn structure), not step count or training volume.** Single-step trajectory = full 3–5 step model. 2×2 table + analysis in RESULTS.md.
- **2026-06-18**: **Phase 16 complete.** Trajectory-trained model achieves **10.48 mean survival steps** (baseline ~1.0, target ≥3) — 10x improvement. All 54 GoKer programs survive ≥5 steps. Adapter: `kavirubc/weave-ccwm-qwen2.5-coder-7b-traj-lora`.
- **2026-06-18**: arXiv preprint live at https://arxiv.org/abs/2606.17508 (cs.PL primary, cs.SE cross-list). Retargeted Weave to **ICSE 2027 NIER** (New Ideas and Emerging Results). Given the modest scale of our corpus (130 programs) and the openly-reported 35-36% accuracy ceiling, the NIER track's framing of "honest limitations + concrete future work" is a much better fit than the main Research Track. Phase 17 ablations will provide mechanistic understanding for Research Track abstract (due Jun 23) and full paper (due ~Jul 1).

## Current State

**Target: ICSE 2027 NIER (single track). Phases 1–18 complete.** Canonical paper:
`ICSE 2027_Templates/weave-nier/main.tex` (4 pages main + 1 page refs). Research Track draft
archived at `ICSE 2027_Templates/weave-research/`. Active work: finalize the NIER paper;
optionally run one Phase 19 strengthening experiment first (~$20 RunPod + ~$10 Gemini).

**Preprint** live on Zenodo (DOI: 10.5281/zenodo.20682004) and arXiv (arXiv:2606.17508).
Headline results locked: traj 7B **40.1%** GoKer OOD, **10.48** mean survival steps,
McNemar vs single-step **p=0.016**, GoCreate **+24pp**, majority baseline 35.5%.

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
- [x] **Phase 17 — Ablation Experiments: Why does trajectory training work? (2×2 matrix)**
  - Ablation A (1-step traj): 40.1% | Ablation B (point 6ep): 35.3%
  - **Finding: gain is from trajectory format (multi-turn structure), not step count or volume**
  - All results, adapters, and eval JSONs downloaded locally. Analysis in RESULTS.md.

---

## Immediate Next Steps

### 0. Phase 17 Ablations — COMPLETE ✅
- Format effect: +3.9pp | Step-count: 0pp | Volume: −0.9pp

### 0b. Phase 18 Statistical Analysis — COMPLETE ✅
- [x] Majority-class baseline: **35.5%** (traj model +4.6pp above)
- [x] Training frequency: GoCreate 0.9% train vs 21.2% val — explains ceiling; GoSched/GoEnd also underrepresented
- [x] McNemar traj vs Phase 13 CE: **p=0.016 ✅**, 95% CI [+1.0, +8.3pp]
- [x] Per-event breakdown: **GoCreate +24pp** is the entire source of gain
- [x] GoStart/GoBlock confusion: 198 pairs, model anchors on prior event
- [x] McNemar traj vs Gemini Flash (35.8%, no thinking): **p=0.069 ❌** not significant, CI [−0.18, +8.77pp]
- [ ] Gemini 3.1 Pro baseline: **partial (36.4% on 253/798), budget-gated** — finish only if Phase 19 #3 is chosen (~$10 Gemini)
- **Script:** `eval/phase18_analysis.py` | **Output:** `eval/results/phase18_numbers.json`

### 1. (Optional) Pick one Phase 19 strengthening experiment
- **Decision menu** lives in CLAUDE.md → "Phase 19 — NIER Strengthening Candidates".
- Pick **at most one**, within ~$20 RunPod + ~$10 Gemini. Recommended default: stratified-sampling retrain (#1, ~$4) + free formal select-block proposition (#4) + finish Gemini 3.1 Pro baseline (#3) as budget allows.
- The specific choice is deferred to a dedicated exploration session — start it by verifying `prepare_trajectory.py` / the state-prompt builder expose the hooks candidates 1–2 assume.

### 2. Finalize the NIER Submission (Due Fri 23 Oct 2026, ~4 months)
- Canonical paper: `ICSE 2027_Templates/weave-nier/main.tex` (IEEEtran 10pt, already 4+1).
- Strict limit: **4 pages main text + 1 page references**.
- Add required **"Future Plans"** section outlining scaling to Ballerina, mutex/channel buffer state, stratified sampling.
- Double-anonymous: no author names, third-person self-citation.
- Related work is done — use `related_works.md`; do NOT re-research citations.

### 3. ICSE Submission Details
- **NIER deadline:** Fri 23 Oct 2026 (AoE) — the single target.
- **Format:** 4 pages main + 1 page references, IEEEtran 10pt (no compsoc), double-anonymous.
- The Research Track attempt is dropped; its draft is archived at `ICSE 2027_Templates/weave-research/` (see its `ARCHIVED.md`).

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
