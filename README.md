# Weave: Concurrent Code World Models

**Kaviru Hapuarachchi** · [huggingface.co/kavirubc](https://huggingface.co/kavirubc) · [github.com/kaviru2/Weave](https://github.com/kaviru2/Weave)

**Preprint:** [doi.org/10.5281/zenodo.20682004](https://doi.org/10.5281/zenodo.20682004)

---

## Abstract

World models for code — models trained on execution traces to predict program state — have
shown strong results for sequential Python ([Meta CWM, arXiv:2510.02387](https://arxiv.org/abs/2510.02387)).
We extend this paradigm to **concurrent programs**, where execution is nondeterministic:
multiple goroutines run simultaneously, communicate over channels, and acquire locks,
producing different interleavings across runs.

We make two contributions. First, we introduce **Weave-Bench**: a benchmark of 130 concurrent
Go programs (26 hand-crafted, 38 generated, 66 real-world bugs from production systems)
with execution traces collected from multiple runs per program. Second, we reformulate
next-state prediction as **distribution estimation** — exploiting the natural nondeterminism
of concurrent execution to derive empirical target distributions from multiple runs rather
than treating one interleaving as ground truth.

We show that (1) distribution framing reduces Expected Calibration Error from 0.205 to 0.169
vs a point-prediction baseline, (2) model entropy positively correlates with program
nondeterminism level (Spearman ρ=0.412, p=0.007), and (3) goroutine leaks of the
select-block class produce a structural distribution signature (P(GoUnblock)=0) that is
detectable from partial traces — a formal consequence of the goroutine's state, not a pattern.

---

## Key Results

### Accuracy on GoKer held-out test set (798 real-world concurrent bug programs)

| Model | Training | Accuracy | GoUnblock |
|-------|----------|----------|-----------|
| Majority-class baseline | — | 35.5% | 0% |
| Gemini 3.5 Flash zero-shot | — | 34.8% | 0% |
| Qwen2.5-Coder-7B zero-shot | — | 28.6% | 0% |
| Qwen2.5-Coder-7B CE (Phase 13) | plain traces | 36.2% | 0% |
| **Qwen2.5-Coder-7B Traj (Phase 16)** | **plain traces** | **40.1%** | **0%** |
| Qwen3-8B Traj (Phase 21, plain prompts) | enriched traces | 30.3%† | **4.2%** |

†Distribution shift: Phase 21 trained on enriched prompts, tested on plain. In-distribution result: 49.7% on 545 traj val.

### Observability — GoUnblock recovery

| Condition | GoUnblock Accuracy |
|-----------|-------------------|
| Any model, plain traces (Phases 13–20) | **0%** (0/48) — information-theoretic limit |
| Qwen3-8B + WeaveChan/WeaveMutex, same test set | **4.2%** (2/48) |
| Qwen3-8B + WeaveChan/WeaveMutex, in-distribution | **11.4%** (4/35) |

### Multi-step coherence (rollout on GoKer programs)

| Model | Mean Survival Steps | Programs ≥10 steps |
|-------|--------------------|--------------------|
| Single-step baseline (Phase 15) | ~1.0 | 0/54 |
| Qwen2.5-7B Traj (Phase 16) | **10.48** | 30/54 |
| **Qwen3-8B Traj + wrappers (Phase 21)** | **19.64** | **55/56** |

### Statistical significance
- Phase 16 traj vs Phase 13 CE: **p=0.016**, CI [+1.0pp, +8.3pp] ✅
- Phase 16 traj vs Gemini Flash: p=0.069 ❌ (not significant)
- Ablation: trajectory format adds +3.9pp; number of rollout steps adds 0pp

---

## Program Corpus (130 programs)

| Category | Count | Source |
|----------|-------|--------|
| Hand-crafted (`01_`–`26_`) | 26 | Designed to cover channel, mutex, select, pipeline, waitgroup, fan-in/out patterns; includes intentional deadlocks, races, leaks |
| Generated (`gen_*`) | 38 | Synthesised by `dataset/generate_programs.py` with randomised parameters |
| Real-world bugs (`goker_*`) | 66 | Reduced concurrency bug kernels from [GoKer/GoBench](https://github.com/nicholasgasior/gobench) (ASPLOS'19): CockroachDB (16), Kubernetes (16), gRPC (11), etcd (9), Istio (6), Moby (5), Serving (2), Syncthing (1) |

All programs carry `WEAVE_META` headers (outcome, concurrency pattern, goroutine count,
nondeterminism level) and are automatically discovered by the dataset builder.

---

## Dataset

**Weave-Bench** on Hugging Face: [kavirubc/weave-bench](https://huggingface.co/datasets/kavirubc/weave-bench)

| Split | Examples | Description |
|-------|----------|-------------|
| `train_point_dups.jsonl` | 945 | Point-prediction fine-tuning — hand-crafted + generated programs only |
| `val_point_dups.jsonl` | 798 | **GoKer held-out test set** — real-world bugs, unseen during training |
| `train_trajectory.jsonl` | 970 | **Trajectory training data** (Phase 16/21) — multi-step rollouts, 308 with enriched channel/mutex state |
| `val_trajectory.jsonl` | 545 | Trajectory val set — 525 GoKer + 20 Phase 20/21 instrumented (p20val_) |
| `train_traj_1step.jsonl` | — | Phase 17 ablation — single-step trajectory format |
| `val_traj_1step.jsonl` | — | Phase 17 ablation val |
| `train_dist.jsonl` | 189 | Distribution-format training examples |
| `val_dist.jsonl` | 162 | Distribution-format GoKer test examples |
| `aggregated.json` | 75 groups | Empirical next-event distributions with Dirichlet posteriors |

Each example is a `(program_source, partial_trace, next_event)` triple. The partial trace
represents 25%, 50%, or 75% of a recorded execution. Five runs per program capture different
nondeterministic interleavings. GoKer programs are held out entirely from training.

---

## Models

| Model | HuggingFace | Notes |
|-------|-------------|-------|
| Weave-CCWM 1.5B (Phase 12) | [kavirubc/weave-ccwm-qwen2.5-coder-1.5b-lora](https://huggingface.co/kavirubc/weave-ccwm-qwen2.5-coder-1.5b-lora) | QLoRA on Qwen2.5-Coder-1.5B, 40.2% in-dist |
| **Weave-CCWM 7B CE (Phase 13)** | [kavirubc/weave-ccwm-qwen2.5-coder-7b-lora](https://huggingface.co/kavirubc/weave-ccwm-qwen2.5-coder-7b-lora) | QLoRA on Qwen2.5-Coder-7B via Unsloth, **36.2% GoKer held-out** |
| **Weave-CCWM 7B KL (Phase 14)** | [kavirubc/weave-ccwm-qwen2.5-coder-7b-kl-lora](https://huggingface.co/kavirubc/weave-ccwm-qwen2.5-coder-7b-kl-lora) | KL distribution loss, **35.8% GoKer held-out**, ECE 0.169 |
| **Weave-CCWM 7B Traj (Phase 16)** | [kavirubc/weave-ccwm-qwen2.5-coder-7b-traj-lora](https://huggingface.co/kavirubc/weave-ccwm-qwen2.5-coder-7b-traj-lora) | Trajectory training, **40.1% GoKer held-out**, 10.48 mean survival steps |
| Weave-CCWM Qwen3-8B CE (Phase 20) | [kavirubc/weave-ccwm-qwen3-8b-ce-lora](https://huggingface.co/kavirubc/weave-ccwm-qwen3-8b-ce-lora) | QLoRA on Qwen3-8B, **36.0% GoKer held-out** |
| **Weave-CCWM Qwen3-8B Traj (Phase 20)** | [kavirubc/weave-ccwm-qwen3-8b-traj-lora](https://huggingface.co/kavirubc/weave-ccwm-qwen3-8b-traj-lora) | Trajectory training on Qwen3-8B, **47.2%** on 545 traj val; GoUnblock 0%→9% |
| **Weave-CCWM Qwen3-8B Traj (Phase 21)** | [kavirubc/weave-ccwm-qwen3-8b-traj-lora](https://huggingface.co/kavirubc/weave-ccwm-qwen3-8b-traj-lora) | Trajectory training on Qwen3-8B, **49.7%** (**50.6%** regex) on 545 val; GoUnblock 0%→11.4% |

Phase 13 training: 3 epochs, batch=1, grad_accum=8, seq_len=4096, LoRA r=16/α=32.
RTX 4000 Ada (20GB), ~2h 11min. Train loss: 0.058. Total compute: ~$12.

---

## Reproducing Results

### Prerequisites

```bash
git clone https://github.com/kaviru2/Weave
cd Weave
go mod download          # Go 1.22+
uv sync                  # Python deps via uv
```

### Build the dataset

```bash
go run dataset/builder.go dataset/schema.go    # collect traces, build eval examples
uv run python dataset/aggregate.py             # empirical distributions
uv run python dataset/prepare_finetuning.py    # GoKer held-out train/val JSONL
```

### Replicate zero-shot baseline (requires Gemini API key)

```bash
echo "GEMINI_API_KEY=your_key" > .env
go run eval/zero_shot.go                       # point-prediction baseline (56%)
go run eval/analyze/analyze.go                 # accuracy report
uv run python eval/dist_zero_shot.py           # distribution eval (ECE)
uv run python eval/dirichlet_analysis.py       # anomaly scores, leak signatures
```

### Fine-tuning on RunPod (7B with Unsloth)

```bash
# Provision RTX 4000 Ada (20GB) on RunPod, then:
RUNPOD_IP=<ip> RUNPOD_PORT=<port> RUNPOD_KEY=~/.ssh/id_runpod bash scripts/runpod_deploy.sh
# Defaults: Qwen2.5-Coder-7B-Instruct, batch=1, grad_accum=8, epochs=3
```

### Evaluate fine-tuned adapter

```bash
# On RunPod (after training):
python scripts/eval_unsloth.py   # uses Unsloth-loaded adapter

# Locally (Mac M-series, float16):
uv run python scripts/run_eval.py \
    --adapter  dataset/output/lora_adapter_v3 \
    --val_file dataset/output/kaggle_upload/val_point_dups.jsonl \
    --load_in_4bit
```

---

## Repository Structure

```
weave/
  tracer/                      — Go trace collector (golang.org/x/exp/trace)
  programs/                    — 130 concurrent Go programs
  dataset/
    builder.go                 — trace collection and eval example generation
    schema.go                  — JSON types
    aggregate.py               — empirical distribution aggregation (Phase 6)
    prepare_finetuning.py      — GoKer held-out split + chat-format JSONL (Phase 13)
    train_lora.py              — standard QLoRA fine-tuning script (1.5B)
    train_lora_unsloth.py      — Unsloth QLoRA fine-tuning script (7B, Phase 13)
    generate_programs.py       — synthetic program synthesiser
    import_gobench.py          — GoKer/GoBench importer
  eval/
    zero_shot.go               — Gemini point-prediction baseline (Phase 4)
    analyze/analyze.go         — accuracy report (Phase 5)
    dist_zero_shot.py          — distribution calibration eval (Phase 7)
    dirichlet_analysis.py      — anomaly scores, leak signatures (Phase 8)
    simulation_rollout.py      — autoregressive trajectory rollout (Phase 15)
  scripts/
    runpod_deploy.sh           — one-command RunPod deploy (7B defaults)
    runpod_pod.sh              — pod-side Unsloth training + eval script
    run_eval.py                — eval script with --load_in_4bit flag (CUDA/MPS/CPU)
    eval_unsloth.py            — Unsloth-based eval for pod (no re-download needed)
    eval_zeroshot_7b.py        — 7B zero-shot eval (no adapter)
    upload_dataset_hf.py       — sync dataset/output/ → HF Hub
    upload_model_hf.py         — upload LoRA adapter → HF Hub
  STATUS.md                    — live project state and next steps
  CLAUDE.md                    — full research plan and phase specifications
```

---

## Key Design Decisions

- `go tool trace` exposes goroutine scheduler events only — no local variable state. The model must reason from scheduling behaviour, not data values.
- Multiple runs per program capture different nondeterministic interleavings. The five-run empirical distribution is the training signal for Phase 14 distribution-loss training.
- **GoKer held-out split (Phase 13):** All 66 GoKer real-world bug programs are reserved as the test set. Training uses only hand-crafted (`01_`–`26_`) and generated (`gen_*`) programs. This gives a clean generalisation measurement.
- **Unsloth (Phase 13):** `use_gradient_checkpointing="unsloth"` with batch=1/grad_accum=8 fits 7B 4-bit QLoRA in 20GB VRAM without OOM.
- Dataset pre-truncation (Phase 12 fix): prompts left-truncated at source to ≤4000 tokens so the JSON prediction target is never cut off by `SFTTrainer`'s `max_seq_length`.

---

## Limitations and Future Work

- **Accuracy ceiling at ~40%:** Trajectory training (Phase 16) lifted the ceiling to 40.1% on point prediction, but rare event types (GoEnd, GoSched) remain frequency-driven blind spots. GoUnblock (previously 0%) was an information-theoretic observability limit which has been resolved.
- **GoUnblock observability wrapper:** Phase 20/21 introduced a wrapper library (`instrumented/WeaveChan`, `WeaveMutex`) that embeds causal channel/mutex state directly into the scheduler trace. Scaling this up in Phase 21 to the full handcrafted and generated training corpus successfully recovered GoUnblock accuracy to **11.4% (4/35)** on unseen OOD programs, demonstrating generalisation.
- **Multi-step coherence:** Trajectory training (Phase 16) increased mean survival steps from ~1 to **10.48** — a 10× improvement. All 54 GoKer programs survive ≥5 steps.
- **Future:** Stratified sampling to fix GoEnd/GoSched; eBPF-based observability for full channel buffer state; Ballerina extension as a second concurrent language.

---

## References

- Meta CWM: [arXiv:2510.02387](https://arxiv.org/abs/2510.02387)
- Debugging CWMs: [arXiv:2602.07672](https://arxiv.org/abs/2602.07672)
- CONCUR benchmark: [arXiv:2603.03683](https://arxiv.org/abs/2603.03683)
- GoKer/GoBench (ASPLOS'19): [Tu et al. 2019](https://dl.acm.org/doi/10.1145/3297858.3304069)
- Go execution tracer: [pkg.go.dev/runtime/trace](https://pkg.go.dev/runtime/trace)

---

## Citation

```bibtex
@misc{hapuarachchi2026weave,
  title     = {When the Next Step Is Not One Step: Distribution-Aware
               Execution Modeling for Concurrent Go Programs},
  author    = {Hapuarachchi, Kaviru},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.20682004},
  url       = {https://doi.org/10.5281/zenodo.20682004},
  note      = {Preprint}
}
```
