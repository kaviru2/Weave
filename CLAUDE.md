# Weave — Claude Code System Prompt

## What is Weave?

Weave explores **Concurrent Code World Models (CCWM)** — extending the execution-trace world
model paradigm (Meta CWM, arXiv:2510.02387) from sequential Python to **concurrent Go programs**
where goroutines communicate over channels and produce nondeterministic interleavings.

**Core thesis:** Concurrent execution is nondeterministic. We treat that nondeterminism as a
training signal — running each program repeatedly to capture scheduling variation, formatting
traces as multi-step trajectory dialogues, and training a model to predict the next scheduler
event. This produces better accuracy *and* coherent multi-step rollout, unlike single-step CE.

**Observability thesis (Phase 20):** GoUnblock 0% accuracy is an information-theoretic limit,
not a data or capacity limit. The Go runtime tracer does not expose which channel caused the
unblock. We solve this with lightweight wrapper types (WeaveChan, WeaveMutex) that embed causal
sync events into the same scheduler trace — no runtime fork, no sidecar file.

---

## Target Venue & Submission Info

* **Venue**: ICSE 2027 **Research Track** (pivoted from NIER on 2026-06-23)
* **Abstract registered**: 2026-06-23 (today — done)
* **Full paper deadline**: **Mon 30 Jun 2026 AoE** (~7 days from pivot)
* **Format**: 10 pages main text + 2 pages references (IEEEtran 10pt two-column)
* **Anonymization**: Strict double-anonymous. No author names, third-person self-citations.
* **Primary area**: AI for Software Engineering — Secondary: Testing and Analysis
* **Canonical paper**: `ICSE 2027_Templates/weave-nier/main.tex` (expand from 4→10 pages)
* **NIER draft** (archived, use for prose/related work): `ICSE 2027_Templates/weave-research/`
* **Preprint**: arXiv:2606.17508, Zenodo DOI: 10.5281/zenodo.20682004

---

## Project Owner Context

- 4th year undergrad, independent research
- M3 Pro MacBook, 18GB RAM (cannot run 7B+ locally — CUDA required for bitsandbytes 4-bit)
- RunPod for all GPU compute; network volume `Weave` (EU-RO-1) has Qwen3-8B weights cached

---

## Compute Infrastructure

**SSH key:** Always use `~/.ssh/id_runpod` (the pod UI may show `id_ed25519` — ignore it).

**Template:** `runpod-torch-v240` (PyTorch 2.4.x). No tmux pre-installed — use `nohup ... &`.

**Storage:** Container disk (`/`, 20GB) for code/data; network volume (`/workspace`, 20GB)
for model weights. Always set `HF_HOME=/workspace/hf_cache` before any HuggingFace downloads.

**GPU:** RTX 4000 Ada (20GB, ~$0.26/hr) — first choice. A40 (48GB, ~$0.44/hr) fallback.

**Deploy training:**
```bash
RUNPOD_IP=<ip> RUNPOD_PORT=<port> RUNPOD_KEY=~/.ssh/id_runpod bash scripts/runpod_deploy.sh
# Traj variant:
USE_TRAJ=1 RUNPOD_IP=<ip> RUNPOD_PORT=<port> RUNPOD_KEY=~/.ssh/id_runpod bash scripts/runpod_deploy.sh
```

**Deploy eval-only:**
```bash
RUNPOD_IP=<ip> RUNPOD_PORT=<port> RUNPOD_KEY=~/.ssh/id_runpod bash scripts/runpod_eval_traj.sh
scp -P <port> -i ~/.ssh/id_runpod root@<ip>:/root/eval_results_traj.json eval/results/eval_results_traj_accuracy.json
```

**Dep versions (RunPod torch 2.4.x) — for eval:**
```
transformers==4.46.3  peft (latest, -U)  accelerate  bitsandbytes>=0.46.1
```
Note: `bitsandbytes==0.44.1` is too old (rejects 4-bit on newer pods). Always `pip install -U bitsandbytes`.
For Qwen3-8B eval: `transformers>=4.51` + `torchvision` upgrade needed (see `run_eval.py` set_submodule backport).
For training: `pip install unsloth` handles everything.
**Unsloth:** `pip install unsloth` — 2× faster, 60% less VRAM. Use `FastLanguageModel` in place
of `AutoModelForCausalLM`. **Qwen3 requires `enable_thinking=False`** in every
`tokenizer.apply_chat_template()` call — already set in all scripts.

## All Completed Phases (1–21)

| Phase | What | Key result |
|---|---|---|
| 1–5 | Tracer, programs, dataset builder, Gemini zero-shot, analyzer | 56% zero-shot, 0% bug detection |
| 6–8 | Empirical distributions, ECE, Dirichlet analysis | ECE 0.205→0.169, entropy tracks nondeterminism |
| 9–9b | 10 new leak programs, select-block boundary test | P(GoUnblock)=0 theorem confirmed |
| 10–12 | QLoRA fine-tuning (1.5B, truncation fix) | 40.2% in-distribution |
| 13 | 7B CE fine-tuning, GoKer held-out | **36.2%** OOD |
| 14 | KL distribution-loss training | 35.8%, ECE 0.169 |
| 15 | Autoregressive rollout baseline | ~1.0 mean survival steps |
| 16 | Trajectory training | **40.1%** accuracy, **10.48** survival steps |
| 17 | Ablation: format vs step count | Format drives all gain (+3.9pp); steps add 0pp |
| 18 | Statistical analysis | McNemar p=0.016 ✅, GoCreate +24pp, majority 35.5% |
| 20 | Observability wrapper + Qwen3-8B retrain | GoUnblock 0%→4% (798 GoKer), WeaveChan/WeaveMutex proven |
| 21 | Full Instrumentation + Retrain | GoUnblock recovered at scale (**11.4%** vs 0% baseline), trajectory val accuracy **49.7%** (50.6% regex) |
| 22 | Dataset Expansion (Real-World) | Scanned and auto-instrumented 37 new GoKer real-world bugs, expanding evaluation scope to 103 total real-world bugs. |

---

## Locked Key Numbers (for paper)

All experiments complete as of 2026-06-24. Do not re-run evals — use these numbers.

| Claim | Number | Source file |
|---|---|---|
| Best single-step accuracy (P16, 798 GoKer) | **40.1%** | `eval_results_traj_accuracy.json` |
| vs majority-class baseline | **+4.6pp** (35.5% baseline) | `phase18_numbers.json` |
| vs Phase 13 CE (McNemar) | **p=0.016**, CI [+1.0, +8.3pp] | `phase18_numbers.json` |
| vs Gemini Flash (McNemar) | **p=0.069 ❌**, CI [−0.18, +8.77pp] | `phase18_numbers.json` |
| Coherence Phase 16 | **10.48 mean survival steps** | `rollout_results_traj.json` |
| Coherence Phase 21 | **19.64 mean survival steps** (55/56 @ 20-step max) | `rollout_results_phase21.json` |
| GoCreate gain (P16 vs P13) | **+24pp** (all other events flat) | `phase18_numbers.json` |
| Format ablation | **+3.9pp format**, 0pp steps | `eval_ablation_1step.json` |
| GoUnblock without wrappers (all phases) | **0%** (0/48) — information-theoretic limit | `eval_results_traj_accuracy.json` |
| GoUnblock recovery P21, same test set | **4.2%** (2/48) on 798 GoKer | `eval_results_phase21_798.json` |
| GoUnblock recovery P21, in-distribution | **11.4%** (4/35) on 545 traj val | `eval_results_traj_enriched_point.json` |
| P21 in-distribution accuracy | **49.7%** (271/545) | `eval_results_traj_enriched_point.json` |
| P21 cross-format accuracy (plain prompts) | **30.3%** (242/798) | `eval_results_phase21_798.json` |
| P16 on enriched prompts (cross-format) | **58.0%** (316/545) | `eval_results_phase16_545.json` |

**Eval results location (gitignored — do not delete):** `eval/results/`

---

## Current Status: PAPER DRAFTED — FINAL PROOFREAD + SUBMIT

**Deadline: Mon 30 Jun 2026 AoE (~6 days from 2026-06-24)**

All experiments complete. Paper drafted and compiles clean at **11 pages** (main text ends page 10,
page 11 references-only — page-limit compliant). Remaining: final prose read-through, anonymity sweep, submit.

### Paper finalization (2026-06-24)

* Canonical paper: `ICSE 2027_Templates/weave-research/main.tex`; figures from `gen_figures.py` (run from that dir to regenerate).
* Fixed figure overlaps (Fig 2 stale `p=0.0001` callout + x-labels; Fig 3 annotation/legend) — regenerated.
* To meet the 10-page main-text limit, removed: **Fig 6** (GoCreate scatter), **Table X** (qualitative), **Table XIII** (signature — numbers kept inline), **Acknowledgements** section.
* Removed Gemini 3.1 Pro partial claims; fixed a Discussion contradiction on the observability gap.
* **CAMERA-READY TODO if accepted:** restore the Acknowledgements / generative-AI disclosure (a `.tex` comment marks the location).

### All Gap Evals Complete (2026-06-24)

* **Gap 1** — P21 Qwen3-8B on 798 GoKer: **30.3%** overall, **4.2% GoUnblock** (2/48)
* **Gap 2** — P16 Qwen2.5-7B on 545 traj val (enriched format): **58.0%** overall, 20% GoUnblock (near-random on 35 examples — not the clean proof; the clean proof is Gap 1)
* **Rollout P21** — **19.64 mean steps**, 55/56 programs hit 20-step maximum

---

## Three-Class Limitation Taxonomy (use in paper)

**Class 1 — Distributional gaps (solvable by stratified sampling):**
GoEnd (1.5% train, 0% val acc), GoSched (0.5% train, 0% val acc). Model never sees enough.

**Class 2 — Observability gap (information-theoretic limit, fixed by Phase 21):**
GoUnblock (15.6% train, **0% acc** without instrumentation). The causal event (channel recv /
mutex unlock) is invisible to the native Go runtime tracer. WeaveChan/WeaveMutex fixes this.
Phase 20 confirmed: 18 enriched training examples → 4% GoUnblock on 798 unseen GoKer examples.

**Class 3 — Semantic confusion (addressable with richer state):**
GoStart/GoBlock (24.8% of all errors). Model anchors on prior event rather than goroutine state
direction. Fix: add `blocked_on` field explicitly to prompt state.

**One-sentence summary:**
> Format helps with structurally predictable events (GoCreate — visible from source syntax);
> instrumentation is required for structurally unobservable events (GoUnblock — causal event
> invisible to the tracer without WeaveChan/WeaveMutex).

---

## Paper Writing — Citations

`related_works.md` contains **19 verified external citations** with full BibTeX and "USE:" draft
sentences. Use it directly — do NOT re-research citations. Structure:
- **Section A** (cwm, debugcwm, exectuning, codeexec) → Code World Models paragraph
- **Section B** (concur, jainpurandare) → LLMs for Concurrent Code paragraph
- **Section C** (goker, gobench, gcatch, gfuzz, gopie) → Go Concurrency Bug Analysis paragraph
- **Section D** (hinton, diffuse, guocalib, probcalib, spiess) → Distribution Training paragraph
- **Section E** (lora, qlora, qwen) → cite in Method, not Related Work

For Research Track: 10 pages gives room for ~25–30 citations total. Mine the archived
`weave-research/main.tex` for expanded prose; its Related Work and Method sections are longer.

---

## Cross-Machine Continuity

1. `git pull` → read `STATUS.md` → read `CLAUDE.md`
2. All per-example eval JSONs are in `eval/results/` (gitignored — do not delete locally)
3. Adapters on HuggingFace: `kavirubc/weave-ccwm-qwen3-8b-{ce,traj}-lora`
4. Network volume `Weave` (EU-RO-1) has Qwen3-8B weights at `/workspace/hf_cache`

---

## Key References

- Meta CWM: arXiv:2510.02387
- Debugging CWMs: arXiv:2602.07672
- CONCUR benchmark: arXiv:2603.03683
- Go execution tracer: https://pkg.go.dev/runtime/trace
- Go trace analysis: https://pkg.go.dev/golang.org/x/exp/trace
