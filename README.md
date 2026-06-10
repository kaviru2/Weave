# Weave — Concurrent Code World Models

Weave is a research project extending the **world model** paradigm (Meta CWM,
[arXiv:2510.02387](https://arxiv.org/abs/2510.02387)) from sequential Python execution to
**concurrent, CSP-based Go programs**.

The core research question: can a model learn the concurrent execution state-transition
function — and can we exploit the natural nondeterminism of concurrent programs as a
training signal by predicting *distributions* over next scheduler states rather than point
labels?

---

## Results Summary

| Phase | Metric | Result |
|-------|--------|--------|
| Zero-shot baseline (Phase 4–5) | event_type accuracy | 56.0% |
| Zero-shot baseline | deadlock / race detection | 0% |
| Distribution eval (Phase 7) | ECE vs point-prediction | 0.205 → 0.169 with thinking budget |
| Dirichlet analysis (Phase 8) | select-block leak signature | P(GoUnblock)=0 at all trace depths |
| QLoRA fine-tune (Phase 10) | val token accuracy | 91.7%* |
| QLoRA fine-tune (Phase 12) | truncation bug fixed, re-training | pending |

*Phase 10 accuracy was misleading — SFTTrainer right-truncated 87% of examples at 2048
tokens, cutting the JSON prediction target. Phase 12 fixes this with dataset pre-truncation
(`max_seq_length` raised to 4096).

---

## Dataset

**Weave-Bench** is hosted on Hugging Face:
[huggingface.co/datasets/kavirubc/weave-bench](https://huggingface.co/datasets/kavirubc/weave-bench)

| Split | File | Examples |
|-------|------|----------|
| Train | `data/train.jsonl` | 1,377 |
| Validation | `data/validation.jsonl` | 366 |
| Distributions | `data/aggregated.json` | 75 groups |
| Raw traces | `traces/*.json` | 1,827 files |

Each example is a (program, partial trace, next event) triple for next-scheduler-event
prediction. Multiple runs of the same program capture different nondeterministic
interleavings.

To regenerate locally and re-upload:

```bash
go run dataset/builder.go dataset/schema.go          # regenerates dataset/output/
uv run python dataset/aggregate.py                   # builds aggregated.json
uv run python scripts/upload_dataset_hf.py           # syncs to HF Hub
```

---

## Program Suite (130 programs)

Programs live in `programs/` and are automatically picked up by the dataset builder.

| Category | Count | Description |
|----------|-------|-------------|
| Hand-crafted (`01_`–`26_`) | 26 | Core patterns: channel, mutex, select, pipeline, waitgroup, fan-in/out; includes intentional deadlocks, races, and goroutine leaks |
| Generated (`gen_*`) | 38 | Synthetic programs from `dataset/generate_programs.py` — randomised worker pools, pipelines, producer-consumer, select patterns |
| GoKer real bugs (`goker_*`) | 66 | Reduced concurrency bug kernels from [GoBench/GoKer](https://github.com/nicholasgasior/gobench) (ASPLOS'19 provenance): CockroachDB, etcd, gRPC, Istio, Kubernetes, Moby, Serving, Syncthing |

---

## Project Structure

```
weave/
  tracer/                   — Go trace collector (golang.org/x/exp/trace)
  programs/                 — 130 concurrent Go programs
  dataset/
    builder.go              — runs all programs 5×, emits per-run eval examples
    schema.go               — dataset JSON types
    aggregate.py            — Phase 6: aggregates runs → empirical distributions
    prepare_finetuning.py   — Phase 12: smart truncation, emits train/val JSONL
    train_lora.py           — QLoRA fine-tuning (Qwen2.5-Coder, TRL/PEFT)
    generate_programs.py    — synthesises new gen_* programs
    import_gobench.py       — imports GoKer bug kernels → goker_* programs
  eval/
    zero_shot.go            — Phase 4: point-prediction zero-shot eval (Gemini)
    analyze/analyze.go      — Phase 5: results analyzer
    dist_zero_shot.py       — Phase 7: distribution zero-shot eval (ECE)
    dirichlet_analysis.py   — Phase 8: anomaly scores, deadlock signatures
    simulation_rollout.py   — Phase 11: autoregressive trajectory rollout
  scripts/
    runpod_deploy.sh        — one-command RunPod deploy (run locally)
    runpod_pod.sh           — pod-side: install deps + train + eval
    run_eval.py             — standalone eval, no Kaggle path dependencies
    upload_dataset_hf.py    — sync dataset/output/ → HF Hub
  train_modal.py            — Modal A100-40GB train+eval job
  RUNPOD_STATUS.md          — live RunPod training tracker
  pyproject.toml            — Python dependencies (uv)
  go.mod / go.sum           — Go dependencies
```

---

## Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 1 — Trace Collector | ✅ | `tracer/` — goroutine lifecycle events via `golang.org/x/exp/trace` |
| 2 — Program Suite | ✅ | 26 hand-crafted programs, 5 with ASPLOS'19 bug provenance |
| 3 — Dataset Builder | ✅ | `builder.go` — 377 eval examples (26 × 5 runs × 3 splits) |
| 4 — Zero-shot Eval | ✅ | Gemini point-prediction baseline: 56% accuracy |
| 5 — Results Analysis | ✅ | 56% event_type, 0% bug detection; failure mode analysis |
| 6 — Distribution Aggregation | ✅ | Empirical next-event distributions; entropy stratifies by nondeterminism |
| 7 — Distribution Eval | ✅ | ECE 0.205 → 0.169 with distribution prompting |
| 8 — Dirichlet Analysis | ✅ | P(GoUnblock)=0 for select-block leak class; causal claim confirmed |
| 9 — Dataset Expansion | ✅ | +10 goroutine leak programs; corpus: 26 programs, 365 examples |
| 9b — Select-Block Boundary | ✅ | Multi-case select confirmed; P(GoUnblock)=0 is a theorem |
| 10 — QLoRA Fine-tuning | ✅* | 91.7% val token accuracy (had truncation bug) |
| 11 — Dataset Expansion II | ✅ | +38 generated + 66 GoKer programs; corpus: 130 programs |
| 12 — Truncation Fix + Retrain | 🟡 | Pre-truncate dataset, `max_seq_length=4096`, re-training on A40 |

---

## Getting Started

### Go pipeline

```bash
go run dataset/builder.go dataset/schema.go   # build eval dataset
go run eval/zero_shot.go                      # needs GEMINI_API_KEY in .env
go run eval/analyze/analyze.go                # print accuracy report
```

Requires Go 1.22+. Set `GEMINI_API_KEY` in `.env`.

### Python pipeline

```bash
uv sync                                          # create .venv
uv run python dataset/aggregate.py              # empirical distributions
uv run python eval/dist_zero_shot.py            # ECE eval (needs GEMINI_API_KEY)
uv run python eval/dirichlet_analysis.py        # anomaly scores
uv run python dataset/prepare_finetuning.py     # generate train/val JSONL
```

### Fine-tuning (RunPod)

```bash
# Deploy to a RunPod pod (get IP+port from RunPod dashboard):
RUNPOD_IP=<ip> RUNPOD_PORT=<port> bash scripts/runpod_deploy.sh
```

See `RUNPOD_STATUS.md` for live run status and download commands.

---

## Key Design Decisions

- `go tool trace` exposes goroutine scheduler events only — no local variable state
- Multiple runs per program capture different nondeterministic interleavings, providing the distribution training signal
- `split_percent` grouping for distribution aggregation approximates "same trace prefix family" — acknowledged in the paper
- Deadlocked programs produce no trace (`TimedOut=true`) and are excluded from distribution estimates
- Dataset pre-truncation (Phase 12): prompts left-truncated at source to ≤3,972 tokens so the JSON prediction target is never cut off by `SFTTrainer`

---

## References

- Meta CWM: [arXiv:2510.02387](https://arxiv.org/abs/2510.02387)
- Debugging CWMs: [arXiv:2602.07672](https://arxiv.org/abs/2602.07672)
- CONCUR benchmark: [arXiv:2603.03683](https://arxiv.org/abs/2603.03683)
- Go execution tracer: https://pkg.go.dev/runtime/trace
- GoKer / GoBench: https://github.com/nicholasgasior/gobench
- Weave-Bench dataset: https://huggingface.co/datasets/kavirubc/weave-bench
