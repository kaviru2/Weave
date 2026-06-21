# Weave — Claude Code System Prompt

## What is Weave?

Weave is a research project exploring **Concurrent Code World Models (CCWM)** — extending the
world model paradigm (as established by Meta's CWM, arXiv:2510.02387) from sequential Python
execution to **concurrent, CSP-based languages** — specifically Go and Ballerina.

Meta's CWM proved that training a model on execution traces (state after every line) dramatically
improves code reasoning. But it only works for sequential Python. Nobody has done this for
concurrent programs where multiple goroutines/strands run simultaneously, share channels, acquire
locks, and produce non-deterministic interleavings.

Weave's research questions:
> 1. Can a model learn the concurrent execution state transition function — predicting how
>    goroutine/strand state evolves given a program and a partial execution trace?
>
> 2. Concurrent execution is nondeterministic. Can we exploit this directly as a training
>    signal — aggregating multiple runs of the same program into empirical next-state
>    distributions, and training a model to predict distributions rather than point labels?
>    Does this produce better-calibrated uncertainty and a more reliable bug-detection signal?

**The paper contribution stated precisely:**
> Current execution trace models treat concurrent programs as if they have deterministic
> execution. They don't. We reformulate next-state prediction as distribution estimation,
> use the natural nondeterminism of concurrent execution to derive empirical target
> distributions from multiple runs, and show that a model trained to match these
> distributions is better calibrated and produces more useful uncertainty estimates for
> bug detection than point-prediction models. Nobody has done this — it is a direct
> consequence of concurrent execution being nondeterministic.

Phases 1–18 in progress. All training complete. Current focus: statistical analysis (Phase 18) and paper writing.

Key results: traj 7B **40.1%** > Phase13 CE 7B 35.5% > Gemini Flash 34.8% > 7B zero-shot 28.6% on GoKer held-out.
McNemar traj vs Phase13: p=0.016 ✅. GoCreate +24pp is the entire source of the 4.6pp gain.
Majority-class baseline (always GoStart): 35.5% — traj model is only model to clearly beat it.
Trajectory training: 10.48 mean survival steps (10× over baseline). Format effect confirmed by Phase 17 ablations.

See STATUS.md for current state and immediate next steps.

---

## Project Owner Context

- 4th year undergrad, doing this for fun and potential research
- Has volunteer/org access to WSO2 (creators of Ballerina)
- Has access to WSO2 servers and RunPod for compute when needed
- Working on M3 Pro MacBook, 18GB RAM (note: can't run 7B+ locally, bitsandbytes 4-bit requires CUDA)
- WSO2 is also heavily invested in Go
- End goal is CCWM itself — not just a WSO2 proposal

## Compute Infrastructure

**RunPod** is the primary GPU compute for training and eval.

**SSH key:** Always use `~/.ssh/id_runpod` — this is the key registered in the RunPod account.
(Public key: `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHHXUJRiDtYdu9XlcMM9Hp6JrXcyUgjvLgYDFJ3awZCv runpod-weave`)
The pod UI may show `id_ed25519` in the connect string — ignore that, `id_runpod` is the correct key.

**Template:** Always use `runpod-torch-v240` (PyTorch 2.4.x pre-installed). tmux is NOT pre-installed — use `nohup ... &` to background long-running jobs, or install tmux via `apt-get install -y tmux` first.

**Storage layout — critical:** Each pod has two separate 20GB storage areas:
- **Container disk** (`/`, 20GB) — fast local SSD, holds OS + pip packages + uploaded files. Do NOT store model weights here — it will fill up and kill the job.
- **Network volume** (`/workspace`, 20GB) — persistent, survives pod restarts. Store all large files here.

Always set `HF_HOME=/workspace/hf_cache` before any HuggingFace downloads so the 7B+ base model weights land on the network volume, not the container disk. Example:
```bash
export HF_HOME=/workspace/hf_cache
mkdir -p /workspace/hf_cache
```
Uploaded data files (`/root/*.jsonl`, `/root/lora_adapter_traj/`) are small (<200MB total) and are fine on the container disk.

**Deploy a new training run:**
```bash
RUNPOD_IP=<ip> RUNPOD_PORT=<port> RUNPOD_KEY=~/.ssh/id_runpod bash scripts/runpod_deploy.sh
```

**Deploy eval-only (trajectory model accuracy):**
```bash
RUNPOD_IP=<ip> RUNPOD_PORT=<port> RUNPOD_KEY=~/.ssh/id_runpod bash scripts/runpod_eval_traj.sh
```
This uploads the local traj adapter + val data and runs `run_eval.py`. Results download:
```bash
scp -P <port> -i ~/.ssh/id_runpod root@<ip>:/root/eval_results_traj.json eval/results/eval_results_traj_accuracy.json
```

**Adapter strategy:** For large adapters already on HuggingFace, prefer downloading on the pod via `huggingface-cli download` rather than SCP-ing from local. For small adapters (<200MB) local SCP is fine.

**GPU selection (current pricing):**
- **RTX 4000 Ada (20GB, ~$0.26/hr)** — first choice for 7B QLoRA and eval; Phases 13, 16
- **A40 (48GB, ~$0.44/hr)** — fallback when RTX 4000 Ada unavailable; Phase 12
- **RTX 5090 (32GB, ~$0.99/hr)** — available option if needed, more expensive

**Unsloth** (`pip install unsloth`) — 2× faster training + 60% less VRAM via fused kernels.
Drop-in replacement for standard HuggingFace training:
```python
from unsloth import FastLanguageModel  # replaces AutoModelForCausalLM
```
See https://github.com/unslothai/unsloth for Qwen2.5 support. Compatible with TRL/PEFT.

**Compatible dep versions for RunPod PyTorch template (torch 2.4.x):**
```
transformers==4.46.3  peft==0.13.2  trl==0.11.4  bitsandbytes==0.44.1  accelerate==0.34.2  datasets==3.0.1
```

---

## Target Venue & Submission Info

* **Venue**: ICSE 2027 **NIER** (New Ideas and Emerging Results)
* **Pivot note (2026-06-22)**: We previously drafted a full Research Track paper, but the corpus scale (130 programs) and the openly-reported ~36–40% accuracy ceiling fit the NIER track's "honest limitations + concrete future work" framing far better. **NIER is now the single target.** The Research Track draft is archived (see below), not active.
* **NIER deadline**: Fri 23 Oct 2026 AoE (~4 months from the pivot date)
* **Format**: **4 pages main text** + **1 page references only** (IEEEtran 10pt, `\documentclass[10pt,conference]{IEEEtran}`, no compsoc options)
* **Anonymization**: Strict double-anonymous. No author names, third-person self-citations, no mention of "submitted to ICSE 2027" on arXiv.
* **Track area**: Likely **Testing and Analysis** (concurrent program analysis, program simulation) or **AI for Software Engineering** (LLM fine-tuning, execution modeling). Indicate one primary, one secondary.
* **Paper folder (canonical)**: `ICSE 2027_Templates/weave-nier/main.tex` — Overleaf-ready, IEEEtran 4+1.
* **Research folder** (archived, superseded): `ICSE 2027_Templates/weave-research/` — kept for reference only. Mine its expanded Related Work, the formal select-block proposition, and longer prose into the NIER version; do not submit it. See its `ARCHIVED.md`.

## Current Phase: Finalize the NIER Paper (+ optional Phase 19 strengthening)

**Phases 1–18 are complete.** The active work is now: (1) finalize the NIER submission from
`ICSE 2027_Templates/weave-nier/main.tex` (4 pages main + 1 page refs, IEEEtran 10pt,
double-anonymous), and (2) optionally run **one** budget-bounded strengthening experiment
(Phase 19 — see "Phase 19 — NIER Strengthening Candidates" below) before writing finishes.
Budget envelope for any new experiment: **~$20 RunPod + ~$10 Gemini** total.

The headline results are locked: 40.1% next-event accuracy, 10.48 mean survival steps,
McNemar p=0.016 vs single-step, GoCreate +24pp, the three-class limitation taxonomy. The
NIER framing leans into honest limitations + concrete future work.

### Phase 16 (DONE): Trajectory-Level Training for Coherent Rollouts
We have selected **Candidate A: Trajectory-level training** as our focus.

* **The Problem**: While the model achieves ~36.2% accuracy on single-step prediction OOD (GoKer), its multi-step autoregressive rollout (coherence) is highly fragile, surviving for an average of only ~1 step before generating invalid states or diverging. This is the project's weakest claim and most flagrant limitation for a "world model."
* **The Solution**: Instead of training on single-step point state transitions, we will train the model on short rolled-out trajectories (3–5 steps). This teaches the model to model sequence coherence and mitigate error accumulation over multi-step rolls.
* **Why this was selected over alternatives**:
  * **vs. Candidate B (Encode channel/mutex state)**: Native Go runtime tracing (`runtime/trace`) does not expose internal channel buffers or mutex holder IDs. Rebuilding the tracer to capture this would require custom instrumentation of the Go runtime or complex source-to-source code rewrite. The cost/engineering overhead is extremely high risk for our timeframe and resources.
  * **vs. Candidate C (Scale GoKer-disjoint set)**: Modestly scaling the training set via synthetic programs might marginally increase single-step OOD accuracy (the ~36% ceiling), but it doesn't solve the core conceptual limitation of multi-step divergence. A "world model" that cannot roll out is not a world model.
  * **Feasibility**: We already have a functioning training pipeline using Unsloth/QLoRA on RTX 4000 Ada (RunPod). Structuring target sequences into multi-step paths requires data-formatting changes rather than invasive system-level modifications. We estimate 2–3 weeks of development and compute time.
* **Definition of "Done" for Phase 16**:
  1. Train the Qwen2.5-Coder-7B model on multi-step trajectory sequences (length 3–5 steps).
  2. Re-run the Phase 15 coherence probe on this trajectory-trained model.
  3. Achieve a **mean survival step rate of >= 3 steps** (a 3x improvement over the current ~1 step baseline) or a statistically significant improvement in survival compared to the single-step model.

---

## Completed Phases (1–15)

All phases done and merged to main. See STATUS.md for full details.

- **Phase 1** — `tracer/` — Go trace collector using `golang.org/x/exp/trace`
- **Phase 2** — `programs/` — 15 concurrent Go programs with ASPLOS'19 provenance
- **Phase 3** — `dataset/builder.go` — 377 eval examples (26 programs × 5 runs × 3 splits)
- **Phase 4** — `eval/zero_shot.go` — Gemini zero-shot evaluator; results in `eval/results/`
- **Phase 5** — `eval/analyze/analyze.go` — results analyzer
- **Phase 6** — `dataset/aggregate.py` — 75 aggregated groups with empirical distributions
- **Phase 7** — `eval/dist_zero_shot.py` — distribution zero-shot eval (ECE, entropy)
- **Phase 8** — `eval/dirichlet_analysis.py` — Dirichlet-Categorical analysis
- **Phase 9** — `programs/16–25` — 10 new leak programs; dataset expanded to 25 programs
- **Phase 9b** — `programs/26` — select-block boundary test; causal claim confirmed for multi-case selects
- **Phase 10** — `dataset/train_lora.py` — QLoRA fine-tuning; 91.7% val accuracy (inflated — truncation bug)
- **Phase 11** — `programs/gen_* + goker_*` — Dataset expansion to 130 programs (26 hand-crafted + 38 generated + 66 GoKer)
- **Phase 12** — Truncation fix + retrain on A40; 40.2% in-distribution accuracy (Qwen2.5-Coder-1.5B)
- **Phase 13** — GoKer held-out split + Unsloth 7B training; **36.2% on GoKer held-out** (Qwen2.5-Coder-7B, RTX 4000 Ada)
- **Phase 14** — `dataset/train_lora_kl.py` — custom KL divergence distribution-loss training; ECE 0.169, 35.8% accuracy on GoKer OOD
- **Phase 15** — `eval/simulation_rollout.py` — autoregressive rollout coherence evaluation (mean survival ~1 step)

## Your Job Right Now

**Target = ICSE 2027 NIER. Phases 1–18 complete. Finalize the NIER paper; optionally run one Phase 19 experiment first.**

### State as of the pivot (2026-06-22)
- Phases 1–18 all done. Headline results locked (see "Key numbers" table below).
- Research Track draft archived; `weave-nier/main.tex` is the canonical paper.
- Phase 18 statistical analysis complete; `phase18_numbers.json` saved.
- Gemini 3.1 Pro baseline eval was partial (36.4% on 253/798) and is now budget-gated (~$10 Gemini left). The paper must read correctly whether or not it is completed — see "Two Scenarios" below.

### Immediately next
1. **Decide Phase 19** (optional, budget ~$20 RunPod + ~$10 Gemini): pick at most one strengthening experiment from "Phase 19 — NIER Strengthening Candidates" below. The specific choice is deliberately deferred to a dedicated exploration session — start there by verifying the scripts the candidates assume actually expose the needed hooks.
2. **Finalize the NIER paper** from `ICSE 2027_Templates/weave-nier/main.tex` (4 pages main + 1 page refs, IEEEtran 10pt, double-anonymous):
   - Key numbers: 40.1% accuracy, 10.48 survival steps, p=0.016 (McNemar), GoCreate +24pp, majority baseline 35.5%
   - Remaining gaps to address: select-block theorem (state as formal Proposition), GoCreate imbalance framing
   - **Related work is done**: use `related_works.md` (see below) — do NOT re-research citations
3. **Submit** by Fri 23 Oct 2026 AoE. Add the required NIER **"Future Plans"** section (Ballerina extension, mutex/channel buffer state, stratified sampling).

### Paper Writing — How to Use related_works.md

`related_works.md` contains **19 verified external citations** with accurate titles, authors, venues, years, and links. Use it as follows:

**Structure of the file:**
- **Section A** (cwm, debugcwm, exectuning, codeexec) → paragraph on "Code World Models and Program Execution Modeling"
- **Section B** (concur, jainpurandare) → paragraph on "LLMs for Concurrent Code"
- **Section C** (goker, gobench, gcatch, gfuzz, gopie) → paragraph on "Go Concurrency Bug Analysis and Tools"
- **Section D** (hinton, diffuse, guocalib, probcalib, spiess) → paragraph on "Distribution Training and Calibration"
- **Section E** (lora, qlora, qwen) → cite in Method section, not Related Work

**Each paper entry has:**
- Full accurate citation (copy directly into BibTeX)
- "What it does" — 2-sentence summary for your own reference
- "USE:" — a draft sentence showing how to cite it in the paper; paste and edit

**Key framing for each section (the gap your paper fills):**
- After Section A: "All prior execution-trace models assume deterministic sequential execution."
- After Section B: "Neither benchmarks execution as a transition function nor addresses nondeterministic scheduling."
- After Section C: "These tools treat nondeterminism as a search space; we treat it as a distributional training signal."
- After Section D: "In prior work, soft targets come from a teacher model. Ours come from the nondeterminism of the program itself."

**Do NOT add more citations** — 19 external papers is appropriate for a 4-page NIER. Adding more would look like padding.

---

## Phase 19 — NIER Strengthening Candidates (costed menu; decision deferred)

A decision **menu**, not a commitment. Pick **at most one** before finalizing the paper.
Budget envelope: RTX 4000 Ada ≈ $0.26/hr → ~$20 ≈ 75 GPU-hr; a Phase 13/16 train+eval cycle
is ~2–4 hr ≈ $1–2, so realistically **2–4 new training cycles** total. Gemini ~$10.
Candidates drawn from STATUS.md "Open Questions" / the three-class limitation taxonomy,
ranked by impact-per-dollar:

1. **Stratified-sampling retrain (Class-1 fix) — strongest single bet.** Oversample
   GoEnd/GoSched/GoUnblock in `prepare_trajectory.py`, retrain the traj model, re-eval on the
   same 798 GoKer held-out set. Target: lift GoEnd/GoSched off 0% and raise the structural
   ceiling above 40.1%. Cost ~1 train+eval cycle (~$2–4). Converts the paper's biggest stated
   limitation into a positive result.
2. **`blocked_on` state representation (Class-3 fix).** Add the `blocked_on` field to the
   prompt state, retrain, measure the GoStart/GoBlock confusion drop (currently 24.8% of all
   errors). Cost ~1 train+eval cycle. Higher risk — may not move the needle.
3. **Finish Gemini 3.1 Pro baseline.** Complete the eval stalled at 253/798 so the
   frontier-model comparison is whole (decides Scenario A vs B). Cost: the whole ~$10 Gemini
   budget. Pure baseline, no new capability.
4. **Formal select-block proposition (zero compute).** Promote the P(GoUnblock)=0
   select-block finding to a stated Proposition with proof sketch (already drafted in the
   archived research paper — mine it). Free; strengthens rigor.
5. **Stronger coherence metric (low compute).** Compare rollout event distribution against
   actual Go tracer runs on GoKer programs (local Go, no GPU). Free-ish; turns the
   FSM-validity lower bound into a distributional claim.

**Recommended default if forced to pick:** #1 (stratified retrain) + #4 (free proposition) +
as-budget-allows #3. Spends ~$4 RunPod, converts the single largest limitation into a result,
and keeps the zero-cost rigor wins. **The exact choice is deferred to a dedicated exploration
session** — its first task is to verify `prepare_trajectory.py` / the state-prompt builder
actually expose the hooks candidates 1–2 assume.

---

## Paper Framing — Two Scenarios (Gemini 3.1 Pro result pending)

These are the two NIER central-claim framings, selected once the Gemini 3.1 Pro baseline is
known. The Pro eval is now **budget-gated** (~$10 Gemini): it may be completed (Phase 19
candidate #3) or may stay at the partial 36.4% on 253/798. The paper must read correctly
either way — if Pro is not finished, report it honestly as a partial frontier baseline and
lead on the Phase 13 McNemar (p=0.016), which is the strongest fully-powered comparison.

### Scenario A: Gemini 3.1 Pro scores BELOW 40.1%

**Central claim:** Task-specific trajectory fine-tuning on 945 examples outperforms frontier models used zero-shot on out-of-distribution concurrent bug programs.

**Lead with:** Traj model (40.1%) > Gemini 3.1 Pro (zero-shot) > Gemini Flash (35.8%) > Phase 13 CE (36.2%).
**Statistical anchor:** Traj vs Phase 13 CE p=0.016 ✅ — trajectory training is a genuine improvement over single-step fine-tuning.
**Don't lead with** Gemini Flash McNemar (p=0.069) — use the stronger model comparison instead.

### Scenario B: Gemini 3.1 Pro scores ABOVE 40.1%

**Central claim:** Trajectory fine-tuning produces a model that matches frontier zero-shot accuracy while additionally exhibiting coherent multi-step rollout and better calibration — capabilities that zero-shot prompting alone cannot provide.

**Three pillars:**
1. **Coherence:** Traj model 10.48 mean survival steps. Gemini Pro zero-shot cannot sustain valid rollout (no training signal for scheduler consistency). Run rollout eval on Pro to confirm.
2. **Calibration:** ECE 0.169 vs Gemini Pro's ECE (need to measure on distribution eval groups). Model knows what it doesn't know — more useful for bug detection.
3. **Efficiency:** 945 training examples + 7B model vs frontier API calls. Domain-specific small model matches large general model.

**Do NOT frame as a failure.** Framing: "We show the capability gap between accuracy and coherence — a model can be accurate one step at a time without understanding execution flow, and our training signal specifically targets coherence."

---

## Training Frequency — Final Numbers (for paper)

Trajectory model trained on `train_trajectory.jsonl` — 3,150 assistant steps:

| Event | Train % | Val % | Val accuracy | Failure mechanism |
|---|---|---|---|---|
| GoBlock | 43.8% | 26.2% | 58% | Overrepresented → good |
| GoStart | 37.6% | 35.5% | 28% | Matched → confused with GoBlock |
| GoUnblock | 15.6% | 6.0% | **0%** | **Structural** — not frequency |
| GoEnd | 1.5% | 4.1% | 0% | Frequency-driven blind spot |
| GoCreate | 0.9% | 21.2% | 72% | Format effect (not frequency) |
| GoSched | 0.5% | 7.0% | 0% | Frequency-driven blind spot |

**Three distinct limitation classes (the Limitations/Future Work taxonomy — use this structure in the paper):**

**Class 1 — Distributional gaps (solvable):** GoEnd (1.5% train, 4.1% val, 0% acc), GoSched (0.5% train, 7.0% val, 0% acc). The model simply never sees enough examples. Fix: stratified sampling. Expected impact: meaningful accuracy improvement on those event types specifically.

**Class 2 — Observability gaps (requires richer instrumentation):** GoUnblock (15.6% train, 6.0% val, **0% acc**). The model sees plenty of examples but cannot predict GoUnblock because predicting it requires knowing which blocked goroutine is about to be woken up — which requires knowing which channel just received a value or which mutex just unlocked. The Go runtime trace exposes neither. No amount of additional training data fixes this. Fix: custom Go runtime instrumentation exposing channel buffer state and mutex holder IDs at unblock time. This is also the Ballerina extension motivation — Ballerina's tracer can be built from scratch to expose this state. This is an **information-theoretic limit**, not a data limit.

**Class 3 — Semantic confusion:** GoStart/GoBlock (198/798 = 24.8% of all errors). The model anchors on the preceding event (46% of confusions follow GoBlock, 40% follow GoStart) rather than reasoning about goroutine state. Fix: richer state representation, explicitly encoding the `blocked_on` field in the prompt.

**One-sentence summary of all empirical findings:**
> Format helps with structurally predictable events (GoCreate — visible from source syntax); no format helps with structurally unobservable events (GoUnblock — causal event is invisible to the tracer).

**GoCreate anomaly (important for paper):**
- Only 0.9% in training, 21.2% in val, yet 72% accuracy
- GoCreate is predictable from program structure (`go` keyword in source → model infers a goroutine spawn is imminent). GoUnblock is not predictable from the observable trace because the causal event (channel receive, mutex unlock) is invisible.
- This is the strongest evidence for the "format effect" beyond Phase 17 ablation.
- Gemini 3.1 Pro gets 76% GoCreate (our 72%) — confirms this is source-structure reasoning, not fine-tuning.
- Gemini 3.1 Pro gets 23% GoUnblock (our 0%) — suggests Pro infers some channel state from source; our model cannot without explicit training on unblock context.

**Gemini 3.1 Pro partial results (253/798, eval still running as of Jun 19):**
| Event | Pro acc | Traj acc | Delta |
|---|---|---|---|
| GoBlock | 25% | 58% | −33pp |
| GoCreate | 76% | 72% | +4pp |
| GoEnd | 17% | 0% | +17pp |
| GoSched | 0% | 0% | 0pp |
| GoStart | 33% | 28% | +5pp |
| GoUnblock | 23% | 0% | **+23pp** |
| **Overall** | **36.4%** | **39.9%** | **−3.5pp (traj wins)** |

---

## When Gemini 3.1 Pro Result Lands — Do This Immediately

1. Check per-event accuracy breakdown for Pro — does it predict GoEnd/GoSched/GoUnblock?
   - If yes: shows what stratified sampling would fix in our model
   - Compare Pro's GoCreate accuracy vs ours (72%) — we likely win there
2. Run `uv run python eval/phase18_analysis.py` — it will auto-compute McNemar traj vs Pro if you add the Pro file path
3. Update `phase18_numbers.json` and RESULTS.md
4. Choose framing (Scenario A or B above) and start writing `weave.tex`

### Key numbers for paper writing
| Claim | Number | Source |
|---|---|---|
| Best single-step accuracy | **40.1%** | eval_results_traj_accuracy.json |
| vs majority-class baseline | **+4.6pp** (35.5% baseline) | phase18_numbers.json |
| vs Phase 13 CE (McNemar) | **p=0.016**, CI [+1.0, +8.3pp] | phase18_numbers.json |
| vs Gemini Flash 35.8% (McNemar) | **p=0.069 ❌ not significant**, CI [−0.18, +8.77pp] | phase18_numbers.json |
| vs Gemini 3.1 Pro (McNemar) | **partial: 36.4% on 253/798 examples, traj leads** | checkpoint (eval still running) |
| Coherence improvement | **10.48 steps** (10× over ~1.0) | rollout_results_traj.json |
| Source of gain | **GoCreate +24pp** (all other events flat) | phase18_numbers.json |
| Format vs steps (ablation) | **+3.9pp format, 0pp steps** | eval_ablation_1step.json |
| Training frequency gap | GoCreate 0.9% train vs 21.2% val | phase18_numbers.json |

### Eval results location (gitignored — keep local)
All per-example JSONs are in `eval/results/`. **Do not delete.** They are gitignored but must persist locally for McNemar tests.
- `eval_results_traj_accuracy.json` — traj model (Phase 16)
- `eval_phase13_ce.json` — Phase 13 CE baseline
- `eval_ablation_1step.json` / `eval_ablation_point6ep.json` — Phase 17 ablations
- `gemini_goker_gemini-3_5-flash.json` — Gemini baseline (generated by re-eval)

Original Phase specs preserved below for reference.

### Phase 6 — Dataset Aggregation

Build `dataset/aggregate.py` that:

1. Reads all `dataset/output/*.json` per-run examples (212 files)
2. Groups by `(program_id, split_percent)` — "same split %" is the approximation for
   "same trace prefix family" across runs. Acknowledge this in the paper.
3. For each group, counts observed next-event types across the 5 runs
4. Computes empirical distribution + Dirichlet posterior (Jeffreys prior α=0.5)
5. Outputs `dataset/output/aggregated.json` with new schema per example:

```json
{
  "program_id": "03_mutex_counter",
  "split_percent": 50,
  "concurrency_pattern": "mutex",
  "nondeterminism": "low",
  "full_outcome": "success",
  "run_count": 5,
  "next_event_distribution": {
    "GoBlock": 0.60, "GoStart": 0.20, "GoUnblock": 0.20,
    "GoEnd": 0.00, "GoSched": 0.00, "GoCreate": 0.00
  },
  "dirichlet_posterior": {
    "GoBlock": 3.5, "GoStart": 1.5, "GoUnblock": 1.5,
    "GoEnd": 0.5, "GoSched": 0.5, "GoCreate": 0.5
  }
}
```

Also: print an exploratory summary — for each group, show the distribution. Do deadlock
programs show P(GoBlock)→1 collapse? This is the key empirical claim; check it in the data
before building Phase 7.

### Phase 7 — Distribution Zero-Shot Eval

Build `eval/dist_zero_shot.py` that:

1. Uses the aggregated dataset from Phase 6
2. Prompts the model for a probability distribution (not a point prediction):

```
Predict the DISTRIBUTION over next scheduler events (probabilities must sum to 1.0).
Respond in JSON:
{"GoBlock": p, "GoCreate": p, "GoEnd": p, "GoSched": p, "GoStart": p, "GoUnblock": p}
```

3. Measures Expected Calibration Error (ECE) against empirical distributions
4. Also measures: does model entropy correlate with program nondeterminism level?
5. Compare ECE to Phase 4 point-prediction baseline

### Phase 8 — Dirichlet-Categorical Analysis

Build `eval/dirichlet_analysis.py` that:

1. Computes anomaly scores: `KL(predicted_dist || uniform)` — high = confident, low = uncertain
2. Shows deadlock distribution collapse: P(GoBlock)→1, P(GoUnblock)→0 as trace progresses
3. Produces the three key results for the paper:
   - Lower ECE for distribution predictions vs. point-prediction baseline
   - High-entropy model predictions correlate with high-nondeterminism programs
   - Deadlock programs have detectable distribution signatures from partial traces

### Phase 9 — Dataset Expansion

**Goal:** Expand the leak corpus from 2 → 12 programs to stress-test the P(GoUnblock)=0
distribution signature claim before the WSO2 research proposal.

Add 10 new `programs/*.go` files, all `outcome: leak`, each using a different leak mechanism:

| File | Leak mechanism | Pattern | Goroutines |
|---|---|---|---|
| `16_http_handler_leak.go` | Handler goroutines range over requests channel; main never closes | channel | 3 |
| `17_ticker_leak.go` | Goroutine reads `time.NewTicker.C`; main exits without `ticker.Stop()` | channel | 2 |
| `18_worker_no_close.go` | 3 workers range over jobs channel; main never closes | channel | 4 |
| `19_context_ignore.go` | Goroutine ignores `ctx.Done()`, blocks on work channel; main cancels + exits | channel | 2 |
| `20_event_listener_leak.go` | Subscriber goroutine ranges over events channel; publisher exits without close | channel | 2 |
| `21_done_channel_leak.go` | Goroutine blocks on `<-done`; main never sends/closes | channel | 2 |
| `22_mutex_deadwait.go` | Main holds mutex lock; worker goroutine blocks on `Lock()`; main exits | mutex | 2 |
| `23_pipeline_no_drain.go` | Stage1 blocks on send to unbuffered channel; stage2 exits after one item | pipeline | 3 |
| `24_select_no_default.go` | Goroutine blocked in select with two cases; neither channel ever receives | select | 2 |
| `25_goroutine_per_request.go` | 5 goroutines each block on their own response channel; main never responds | channel | 6 |

Run sequence:
```bash
go run dataset/builder.go dataset/schema.go  # 365 examples
uv run python dataset/aggregate.py            # 72 groups
uv run python eval/dirichlet_analysis.py      # updated findings
```

**Key finding (Phase 9):** P(GoUnblock)=0 across ALL splits holds only for programs where
the goroutine enters a permanently blocked state before any GoUnblock events appear in the
trace window — specifically `06_channel_select` and `24_select_no_default`. For programs
where goroutines do legitimate work before leaking (receiving items, processing requests),
GoUnblock events appear at early split depths and P(GoUnblock)>0. The signature is
mechanism-dependent, not a general zero-false-positive detector.

**Key finding (Phase 9b):** `26_select_block_multicase` — a select with 4 unreachable cases —
shows P(GoUnblock)=0 at all splits. The signature holds regardless of how many cases the
select has, as long as all cases are structurally unreachable. The causal claim is confirmed
for the select-block class of goroutine leaks.

**Paper implication:** The headline finding is precisely characterised as the "select-block
leak" class — a formal definition exists (goroutine enters select before any GoUnblock events;
no case reachable). P(GoUnblock)=0 is a theorem, not a pattern.

---

## Original Phase Specifications (1–5, for reference)

### Phase 1 — Go Trace Collector

Build a tool in `tracer/` that:

1. Takes a Go source file as input (or a directory of Go programs)
2. Runs it with `go tool trace` and the race detector enabled
3. Parses the raw trace output into **structured concurrent state snapshots**

The state format at each scheduler event should be:

```json
{
  "event_id": 42,
  "timestamp_ns": 1234567890,
  "event_type": "GoStart | GoBlock | GoUnblock | GoCreate | GoEnd | GoSched",
  "goroutine_id": 3,
  "goroutines": {
    "1": {"status": "running", "blocked_on": null, "locals_hint": "main"},
    "2": {"status": "blocked", "blocked_on": "chan_recv", "locals_hint": "worker"},
    "3": {"status": "runnable", "blocked_on": null, "locals_hint": "worker"}
  },
  "channels": {
    "0xc000018080": {"direction": "blocked_recv", "goroutine": 2}
  },
  "mutexes": {}
}
```

Notes on this format:
- We cannot get locals from `go tool trace` directly — that is okay for now, locals_hint is
  just the function name from the stack
- Focus on goroutine lifecycle events, channel operations, mutex operations
- Timestamp is important — it gives us ordering

### Phase 2 — Test Program Suite

Create `programs/` with 10-15 Go programs of increasing complexity:

```
programs/
  01_simple_channel.go       # one goroutine, one channel, clean send/receive
  02_multiple_goroutines.go  # 3 goroutines, fan-out pattern
  03_mutex_counter.go        # shared counter with mutex (like locks.bal from Ballerina)
  04_deadlock.go             # intentional deadlock — important ground truth
  05_race_condition.go       # intentional race — important ground truth
  06_channel_select.go       # select statement across multiple channels
  07_worker_pool.go          # classic worker pool pattern
  08_pipeline.go             # pipeline pattern (stage1 -> stage2 -> stage3)
  09_timeout_pattern.go      # context with timeout
  10_channel_close.go        # close semantics, range over channel
  11_waitgroup.go            # sync.WaitGroup usage
  12_once.go                 # sync.Once — runs exactly once
  13_buffered_channel.go     # buffered vs unbuffered behavior difference
  14_goroutine_leak.go       # goroutine that never exits
  15_fan_in.go               # fan-in pattern, multiple producers one consumer
```

Each program must have a comment block at the top:
```go
// WEAVE_META
// outcome: success | deadlock | race | leak
// concurrency_pattern: channel | mutex | select | waitgroup | pipeline | fanout | fanin
// goroutine_count: N
// expected_nondeterminism: high | medium | low | none
// description: one sentence
```

### Phase 3 — Trace Dataset Builder

Build `dataset/builder.go` that:

1. Runs each program in `programs/` through the trace collector
2. For each program, produces multiple trace samples by running it multiple times
   (concurrent programs can produce different interleavings each run — this is intentional)
3. For each trace, produces evaluation examples in this format:

```json
{
  "program_id": "03_mutex_counter",
  "program_source": "...full go source...",
  "partial_trace": [
    // first N events from the trace
  ],
  "next_event": {
    // ground truth: what actually happened next
  },
  "full_outcome": "success",
  "concurrency_pattern": "mutex",
  "goroutine_count": 4,
  "nondeterminism": "low"
}
```

Split N as: 25%, 50%, 75% of the trace — so each program gives 3 evaluation examples
per run. Run each program 5 times. So 15 programs × 5 runs × 3 splits = ~225 examples.

### Phase 4 — Zero-shot Evaluator

Build `eval/zero_shot.go` (or Python if easier) that:

1. Takes the dataset from Phase 3
2. For each example, sends this prompt to the Claude API (claude-sonnet-4-6):

```
You are reasoning about concurrent Go program execution.

Here is a Go program:
<program>
{program_source}
</program>

Here is a partial execution trace showing goroutine scheduler events so far:
<trace>
{partial_trace as JSON}
</trace>

The current goroutine states are:
<current_state>
{last state in partial_trace}
</current_state>

Predict the next scheduler event. What happens next?
Respond in JSON matching this schema:
{
  "event_type": "GoStart | GoBlock | GoUnblock | GoCreate | GoEnd | GoSched",
  "goroutine_id": <which goroutine>,
  "reasoning": "<brief explanation>",
  "confidence": "high | medium | low"
}
```

3. Compares prediction to ground truth
4. Records: correct event_type, correct goroutine_id, and whether it correctly predicted
   deadlocks/races when those were the outcome

### Phase 5 — Results Analysis

Build `eval/analyze.py` that reads the eval results and produces:

- Overall accuracy by event type
- Accuracy by concurrency pattern
- Accuracy by nondeterminism level
- Deadlock/race detection rate specifically
- A confusion matrix of predicted vs actual event types
- Most common failure patterns (what does the model get wrong consistently?)

This is the output we need to decide if training is worth pursuing.

---

## Cross-Machine Continuity

`STATUS.md` (in the repo root) is the live progress tracker. It is updated after each phase
or significant milestone and committed to git. When picking up on a new machine:

1. `git pull` to get the latest code and status
2. Read `STATUS.md` to know exactly where things stand and what's next
3. `CLAUDE.md` has the plan; `STATUS.md` has the current state

Claude Code: always read `STATUS.md` at the start of a session before doing any work.

---

## Project Structure

```
weave/
  CLAUDE.md                    ← this file (the plan)
  STATUS.md                    ← live progress tracker (update after each phase)
  README.md                    ← keep updated as you build
  tracer/
    tracer.go                  ← core trace collection logic
    parser.go                  ← parse go tool trace output to JSON
    state.go                   ← concurrent state schema and types
  programs/
    01_simple_channel.go
    ... (15 programs)
  dataset/
    builder.go                 ← Phase 3: runs programs, builds per-run eval dataset
    schema.go                  ← dataset JSON schema types
    aggregate.py               ← Phase 6: aggregates runs into empirical distributions
    output/                    ← generated dataset files go here (gitignore)
  eval/
    zero_shot.go               ← Phase 4: point-prediction zero-shot eval (Gemini)
    analyze/
      analyze.go               ← Phase 5: results analyzer
    dist_zero_shot.py          ← Phase 7: distribution zero-shot eval
    dirichlet_analysis.py      ← Phase 8: Dirichlet-Categorical analysis
    results/                   ← eval output files (gitignore)
  go.mod
  go.sum
```

---

## Important Constraints

**Do not build:**
- Any model training code — that comes later, on WSO2/RunPod infrastructure
- A UI or visualizer — interesting but not what we need right now
- Ballerina tracing — that depends on a WSO2 conversation that hasn't happened yet
- Anything that requires a GPU

**Be honest about limitations:**
- `go tool trace` does not give us local variable state — only scheduler events
- Some trace output may be non-deterministic — multiple runs of same program may give
  different valid traces — this is expected and important to document
- The Claude API eval is zero-shot — we are measuring the baseline, not a trained model

**Code quality standards:**
- Every function has a comment explaining what it does
- Error handling is explicit — no silent failures
- Log what you're doing — this is research tooling, verbosity is fine
- Write a README section as you complete each phase

---

## Definition of Done — Phases 1–5 (complete)

```bash
go run dataset/builder.go              # 212 eval examples
go run eval/zero_shot.go               # zero-shot eval, results in eval/results/
go run eval/analyze/analyze.go         # prints accuracy report
```

Results: 56% event_type accuracy, 0% deadlock/race detection. Feasibility confirmed.

## Definition of Done — Phases 6–8

```bash
python dataset/aggregate.py            # aggregated.json with empirical distributions
python eval/dist_zero_shot.py          # ECE vs empirical distributions
python eval/dirichlet_analysis.py      # anomaly scores, deadlock signatures
```

We are done when we have clear answers to:
- Does deadlock produce a detectable distribution collapse (P(GoBlock)→1) in the empirical data?
- Does asking the model for a distribution reduce ECE compared to point-prediction calibration?
- Does model entropy correlate with program nondeterminism level?

That's the data for the WSO2 research proposal and the paper's core claim.

---

## When You're Stuck

- If `go tool trace` output format is unclear: read `runtime/trace` package docs and
  the `golang.org/x/exp/trace` package which has a higher-level API
- If the state representation feels wrong: look at Figure 3 in arXiv:2510.02387 for how
  Meta structured their sequential state — adapt that for concurrent state
- If a program produces no interesting trace: it may be too fast — add `time.Sleep` or
  larger workloads to make scheduler events observable
- If the Claude API eval is too expensive: sample 50 examples instead of all 225

---

## Key References

- Meta CWM paper: arXiv:2510.02387 (the baseline we are extending)
- Debugging CWMs: arXiv:2602.07672 (known failure modes — read section 3)
- CONCUR benchmark: arXiv:2603.03683 (confirms gap in concurrent LLM evaluation, March 2026)
- Go execution tracer: https://pkg.go.dev/runtime/trace
- Go trace analysis: https://pkg.go.dev/golang.org/x/exp/trace
