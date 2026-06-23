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

**Dep versions (RunPod torch 2.4.x):**
```
transformers==4.46.3  peft==0.13.2  trl==0.11.4  bitsandbytes==0.44.1  accelerate==0.34.2  datasets==3.0.1
```
**Unsloth:** `pip install unsloth` — 2× faster, 60% less VRAM. Use `FastLanguageModel` in place
of `AutoModelForCausalLM`. **Qwen3 requires `enable_thinking=False`** in every
`tokenizer.apply_chat_template()` call — already set in all scripts.

---

## All Completed Phases (1–20)

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

---

## Locked Key Numbers (for paper)

| Claim | Number | Source file |
|---|---|---|
| Best single-step accuracy | **40.1%** (Qwen2.5-7B traj, Phase 16) | `eval_results_traj_accuracy.json` |
| vs majority-class baseline | **+4.6pp** (35.5% baseline) | `phase18_numbers.json` |
| vs Phase 13 CE (McNemar) | **p=0.016**, CI [+1.0, +8.3pp] | `phase18_numbers.json` |
| vs Gemini Flash (McNemar) | **p=0.069 ❌**, CI [−0.18, +8.77pp] | `phase18_numbers.json` |
| Coherence | **10.48 mean survival steps** (10×) | `rollout_results_traj.json` |
| GoCreate gain | **+24pp** (all other events flat) | `phase18_numbers.json` |
| Format ablation | **+3.9pp format**, 0pp steps | `eval_ablation_1step.json` |
| Gemini 3.1 Pro (partial) | **36.4%** on 253/798 (traj leads) | checkpoint — not final |
| GoUnblock recovery | **0% → 4%** on 798 GoKer (Phase 20) | `eval_results_qwen3_traj_798.json` |
| Qwen3-8B traj 798 GoKer | **35.8%** (−4.3pp vs P16, p=0.005) | `eval_results_qwen3_traj_798.json` |

**Eval results location (gitignored — do not delete):** `eval/results/`

---

## Current Phase: Research Track Engineering Sprint (Phase 21)

**Deadline: Mon 30 Jun 2026 AoE (~7 days)**

The Research Track paper needs the observability result as a **completed experiment**, not
future work. Phase 20 proved feasibility (18 enriched examples → GoUnblock 0%→4%). Phase 21
scales this to the full 130-program corpus and retrains.

### Phase 21 — Full Instrumentation + Retrain

**Goal:** Show GoUnblock recovery at scale with the full enriched corpus.

**Step 1 — Instrument remaining programs (~2 days, local):**
- Already done: `01_simple_channel`, `03_mutex_counter`, `06_channel_select`, `07_worker_pool`,
  `02_multiple_goroutines`, `13_buffered_channel`, `14_goroutine_leak`, `21_done_channel_leak`,
  `22_mutex_deadwait` (9 programs in `instrumented/`)
- Remaining: extend `WeaveChan`/`WeaveMutex` wrappers to the remaining channel/mutex programs
  in `programs/`. GoKer programs do not need instrumentation (they are eval-only).
- Script: `cmd/build_p20/main.go` — extend to cover all hand-crafted programs.

**Step 2 — Rebuild trajectory dataset (~30 min, local):**
```bash
uv run python dataset/prepare_trajectory.py
```
Target: all p20-instrumented examples have `recv_waiters`/`send_waiters` populated in
`<current_state>`. Verify with: `grep -c "recv_waiters" dataset/output/train_trajectory.jsonl`

**Step 3 — Retrain on RTX 4000 Ada (~2–3 hr, ~$1):**
```bash
USE_TRAJ=1 RUNPOD_IP=<ip> RUNPOD_PORT=<port> RUNPOD_KEY=~/.ssh/id_runpod bash scripts/runpod_deploy.sh
```

**Step 4 — Eval on 798 GoKer (~45 min, ~$0.20):**
```bash
RUNPOD_IP=<ip> RUNPOD_PORT=<port> RUNPOD_KEY=~/.ssh/id_runpod bash scripts/runpod_eval_traj.sh
```
Download: `eval_results_traj_enriched_798.json` → `eval/results/`.
Run McNemar vs Phase 16 (40.1%) and vs Phase 20 Qwen3 (35.8%).

**Definition of done:** GoUnblock accuracy > 0% on GoKer 798, confirmed by McNemar.
If GoUnblock doesn't move, report honestly as a null result — the observability claim still
stands from the 18-example proof-of-concept.

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
