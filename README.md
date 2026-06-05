# Weave — Concurrent Code World Models

Weave is a research project exploring **Concurrent Code World Models (CCWM)** — extending
the world model paradigm (Meta CWM, arXiv:2510.02387) from sequential Python execution to
**concurrent, CSP-based programs** in Go (and eventually Ballerina).

The core research question: can a model learn the concurrent execution state-transition
function, and can we exploit the natural nondeterminism of concurrent programs as a
training signal by predicting *distributions* over next states rather than point labels?

## Key Results (Phases 1–5)

Zero-shot baseline on 212 eval examples (Gemini, no fine-tuning):

| Metric | Score |
|---|---|
| event_type accuracy | 56.0% |
| goroutine_id accuracy | 49.8% |
| deadlock detection | 0 / 5 |
| race detection | 0 / 12 |

Failure modes: block/unblock symmetry confusion (GoStart↔GoUnblock, GoBlock↔GoStart),
zero bug-pattern awareness, and miscalibrated confidence (high-confidence predictions
correct only 58% of the time). This motivates the distribution learning phase.

## Project Structure

```
weave/
  tracer/          — Go trace collector (golang.org/x/exp/trace)
  programs/        — 15 concurrent Go programs (5 with ASPLOS'19 bug provenance)
  dataset/
    builder.go     — runs programs 5×, emits 212 per-run eval examples
    schema.go      — dataset JSON types
    aggregate.py   — Phase 6: aggregates runs into empirical distributions
  eval/
    zero_shot.go         — Phase 4: point-prediction zero-shot eval (Gemini)
    analyze/analyze.go   — Phase 5: results analyzer
    dist_zero_shot.py    — Phase 7: distribution zero-shot eval (ECE)
    dirichlet_analysis.py — Phase 8: anomaly scores, deadlock signatures
  pyproject.toml   — Python dependencies (uv)
  go.mod / go.sum  — Go dependencies
```

## Phases

| Phase | Status | Description |
|---|---|---|
| 1 — Trace Collector | ✅ done | `tracer/` — goroutine lifecycle events from `go tool trace` |
| 2 — Program Suite | ✅ done | 15 Go programs, 5 with ASPLOS'19 bug provenance |
| 3 — Dataset Builder | ✅ done | 212 eval examples (15 programs × 5 runs × 3 splits) |
| 4 — Zero-shot Eval | ✅ done | Gemini point-prediction baseline |
| 5 — Results Analysis | ✅ done | 56% accuracy, 0% bug detection |
| 6 — Dataset Aggregation | 🔄 in progress | Empirical next-event distributions |
| 7 — Distribution Eval | ⬜ planned | ECE vs point-prediction baseline |
| 8 — Dirichlet Analysis | ⬜ planned | Anomaly scores, deadlock signatures |

## Getting Started

### Go (Phases 1–5)

```bash
go run dataset/builder.go dataset/schema.go   # regenerate 212 examples
go run eval/zero_shot.go                      # needs GEMINI_API_KEY in .env
go run eval/analyze/analyze.go                # print accuracy report
```

Requires Go 1.22+. Set `GEMINI_API_KEY` (and optionally `MODEL`) in a `.env` file at the repo root.

### Python (Phases 6–8)

```bash
uv sync                        # create .venv and install dependencies
uv run python dataset/aggregate.py       # Phase 6: empirical distributions
uv run python eval/dist_zero_shot.py     # Phase 7: ECE eval
uv run python eval/dirichlet_analysis.py # Phase 8: anomaly scores
```

Requires [uv](https://docs.astral.sh/uv/). Phases 7–8 also need `GEMINI_API_KEY` in `.env`.

## Key Design Decisions

- `go tool trace` exposes goroutine scheduler events only — no local variable state
- Multiple runs per program are intentional: nondeterminism is the training signal
- The `split_percent` grouping for distribution aggregation is an approximation —
  partial traces across runs are structurally similar but not byte-identical
- Deadlocked programs produce no trace file (`TimedOut=true`) — they have no `next_event`
  and are excluded from distribution estimates

## References

- Meta CWM: arXiv:2510.02387
- Debugging CWMs: arXiv:2602.07672
- CONCUR benchmark: arXiv:2603.03683
- Go execution tracer: https://pkg.go.dev/runtime/trace
