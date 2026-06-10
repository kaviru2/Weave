# Weave: Concurrent Code World Models

**Kaviru Hapuarachchi** · [huggingface.co/kavirubc](https://huggingface.co/kavirubc) · [github.com/kaviru2/Weave](https://github.com/kaviru2/Weave)

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

| Experiment | Metric | Value |
|-----------|--------|-------|
| Gemini zero-shot (Phase 4) | event_type accuracy | 56.0% |
| Qwen2.5-Coder-1.5B zero-shot | event_type accuracy | 0.0% |
| Qwen2.5-Coder-1.5B fine-tuned (Phase 12) | event_type accuracy | **40.2%** |
| Distribution prompting, no thinking (Phase 7) | ECE | 0.183 |
| Distribution prompting, thinking=1024 (Phase 7) | ECE | **0.169** |
| Point-prediction baseline ECE (Phase 4) | ECE | 0.205 |
| Entropy–nondeterminism correlation (Phase 8) | Spearman ρ | 0.412, p=0.007 |
| Select-block leak signature | P(GoUnblock)=0 at all trace depths | 3/3 programs |

> **Note on baselines:** Qwen2.5-Coder-1.5B zero-shot scores 0.0% — the base model cannot
> parse the task format without fine-tuning. Fine-tuning adds +40 percentage points.
> Gemini (56%) uses a much larger model and is not a direct comparison.

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
| `data/train.jsonl` | 1,377 | Fine-tuning examples (chat format) |
| `data/validation.jsonl` | 366 | Held-out evaluation |
| `data/aggregated.json` | 75 groups | Empirical next-event distributions with Dirichlet posteriors |
| `traces/*.json` | 1,827 files | Per-run raw trace examples |

Each example is a `(program_source, partial_trace, next_event)` triple. The partial trace
represents 25%, 50%, or 75% of a recorded execution. Five runs per program capture different
nondeterministic interleavings.

---

## Model

**Weave-CCWM (Phase 12)** on Hugging Face: [kavirubc/weave-ccwm-qwen2.5-coder-1.5b-lora](https://huggingface.co/kavirubc/weave-ccwm-qwen2.5-coder-1.5b-lora)

QLoRA fine-tune of `Qwen/Qwen2.5-Coder-1.5B-Instruct` on Weave-Bench.
train_loss=0.094, eval_loss=0.326, 3 epochs, A40 48GB.

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
uv run python dataset/prepare_finetuning.py    # train/val JSONL for fine-tuning
```

### Replicate zero-shot baseline (requires Gemini API key)

```bash
echo "GEMINI_API_KEY=your_key" > .env
go run eval/zero_shot.go                       # point-prediction baseline (56%)
go run eval/analyze/analyze.go                 # accuracy report
uv run python eval/dist_zero_shot.py           # distribution eval (ECE)
uv run python eval/dirichlet_analysis.py       # anomaly scores, leak signatures
```

### Fine-tuning (RunPod)

```bash
RUNPOD_IP=<ip> RUNPOD_PORT=<port> bash scripts/runpod_deploy.sh
```

### Local inference (Mac M-series)

```bash
uv run python scripts/run_eval.py \
    --adapter  dataset/output/lora_adapter_v2/lora_adapter/checkpoint-516 \
    --val_file dataset/output/kaggle_upload/val_point_dups.jsonl
```

Auto-detects MPS (Apple Silicon), CUDA, or CPU.

---

## Repository Structure

```
weave/
  tracer/                   — Go trace collector (golang.org/x/exp/trace)
  programs/                 — 130 concurrent Go programs
  dataset/
    builder.go              — trace collection and eval example generation
    schema.go               — JSON types
    aggregate.py            — empirical distribution aggregation (Phase 6)
    prepare_finetuning.py   — chat-format JSONL with smart truncation (Phase 12 fix)
    train_lora.py           — QLoRA fine-tuning script
    generate_programs.py    — synthetic program synthesiser
    import_gobench.py       — GoKer/GoBench importer
  eval/
    zero_shot.go            — Gemini point-prediction baseline (Phase 4)
    analyze/analyze.go      — accuracy report (Phase 5)
    dist_zero_shot.py       — distribution calibration eval (Phase 7)
    dirichlet_analysis.py   — anomaly scores, leak signatures (Phase 8)
    simulation_rollout.py   — autoregressive trajectory rollout (Phase 11, in progress)
  scripts/
    runpod_deploy.sh        — one-command RunPod deploy
    runpod_pod.sh           — pod-side training script
    run_eval.py             — eval script (CUDA / MPS / CPU)
    run_eval_zeroshot.py    — zero-shot eval (no adapter)
    upload_dataset_hf.py    — sync dataset/output/ → HF Hub
    upload_model_hf.py      — upload LoRA adapter → HF Hub
  weave_final.tex           — paper draft (target: ISSTA/MSR 2027)
  RUNPOD_STATUS.md          — live training tracker
  STATUS.md                 — project state and next steps
```

---

## Key Design Decisions

- `go tool trace` exposes goroutine scheduler events only — no local variable state. This is a deliberate constraint: the model must reason from scheduling behaviour, not data values.
- Multiple runs per program capture different nondeterministic interleavings. The five-run empirical distribution is the training signal for Phase 14 distribution-loss training.
- `split_percent` grouping approximates "same trace prefix family" across runs. Acknowledged limitation: partial traces at the same percentage are structurally similar but not identical.
- Dataset pre-truncation (Phase 12 fix): prompts left-truncated at source to ≤3,972 tokens so the JSON prediction target is never cut off by `SFTTrainer`'s `max_seq_length`.
- GoKer programs are not yet used as a held-out test set (Phase 13 target). The current train/val split is random across all programs.

---

## Limitations and Future Work

- The eval set currently mixes hand-crafted, synthetic, and GoKer programs. Phase 13 will establish a clean held-out test using only GoKer real-world bugs.
- Phase 12 accuracy (40.2%) needs Qwen zero-shot baseline to be interpretable. This measurement is pending.
- Distribution-loss training (Phase 14) — training with KL divergence against empirical distributions rather than cross-entropy — is the core research contribution and is not yet implemented.
- `go tool trace` does not expose local variable state. Extending to Ballerina (where the WSO2 runtime exposes strand-local state) would test the approach on a richer execution model.

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
@misc{weave2026,
  author = {Hapuarachchi, Kaviru},
  title  = {Weave: Concurrent Code World Models},
  year   = {2026},
  url    = {https://github.com/kaviru2/Weave}
}
```
