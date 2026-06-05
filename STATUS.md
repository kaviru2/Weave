# Weave — Project Status

> Read this first when picking up on a new machine. Then read CLAUDE.md for the full plan.

## Current Phase
**All phases complete.** Ready for WSO2 research proposal.

## Phase Checklist

- [x] Phase 1 — Go Trace Collector (`tracer/tracer.go`, `parser.go`, `state.go`) — **merged to main**
- [x] Phase 2 — Test Program Suite (`programs/01_*.go` … `15_*.go`) — **merged to main**
- [x] Phase 3 — Trace Dataset Builder (`dataset/builder.go`, `schema.go`) — **merged to main**
- [x] Phase 4 — Zero-shot Evaluator (`eval/zero_shot.go`) — **merged to main**
- [x] Phase 5 — Results Analysis (`eval/analyze/analyze.go`) — **merged to main**
- [x] Phase 6 — Dataset Aggregation (`dataset/aggregate.py`) — **merged to main**
- [x] Phase 7 — Distribution Zero-Shot Eval (`eval/dist_zero_shot.py`) — **merged to main**
- [x] Phase 8 — Dirichlet-Categorical Analysis (`eval/dirichlet_analysis.py`) — **complete**

---

## What's Done

### Phase 1 — Go Trace Collector ✓
- `tracer/state.go` — `EventType` constants, `GoroutineState`, `StateSnapshot`, `RunResult` types
- `tracer/tracer.go` — `RunProgram(ctx, sourceFile, outputDir)`: compiles with `-race`, runs binary under context deadline; `TimedOut=true` when deadline exceeded
- `tracer/parser.go` — `ParseTrace(traceFile)`: reads `golang.org/x/exp/trace` events, maps goroutine state transitions to `[]StateSnapshot`
- `tracer/testdata/simple.go` + `infinite.go` — fixture programs for unit tests
- 17 tests passing (`go test ./tracer/...`)
- Trace API: `golang.org/x/exp/trace` (public API, Go 1.26.4)

### Phase 2 — Test Program Suite ✓
15 programs in `programs/`. Branch `phase-2-programs` merged to main via PR #2.

**5 programs reproduce real bug patterns from Tu et al. ASPLOS'19** (citable provenance):

| Program | Bug Pattern | ASPLOS Source |
|---|---|---|
| `04_deadlock.go` | `Wait()` inside goroutine-creation loop | Docker#25384 (blocking/shared-memory) |
| `05_race_condition.go` | Concurrent map writes without sync | Non-blocking/shared-memory class |
| `06_channel_select.go` | Unbuffered channel + select-timeout leaks goroutine | Kubernetes `finishReq` (blocking/message-passing) |
| `07_worker_pool.go` | Lock acquired after queue pop — correct fix | Kubernetes quota controller (blocking) |
| `12_once.go` | `sync.Once` prevents channel double-close panic | Docker#24007 (non-blocking/message-passing) |

**2 bug/fix pairs** (same pattern, correct vs buggy — key evaluation dimension for paper):
- `04_deadlock.go` ↔ `11_waitgroup.go` — WaitGroup placement
- `06_channel_select.go` ↔ `09_timeout_pattern.go` — unbuffered vs buffered channel on timeout

**Important design decisions for Phase 2:**
- Go 1.22+ fixed loop-closure races (per-iteration variables), so `05_race_condition` uses concurrent unprotected map writes instead — same ASPLOS non-blocking/shared-memory class
- Deadlock sentinel: `go func() { time.Sleep(24*time.Hour) }()` in `04_deadlock.go` prevents the Go runtime deadlock detector from panicking the program before `RunProgram`'s context deadline fires (needed to get `TimedOut=true` in `RunResult`)
- Programs `06_channel_select.go` and `14_goroutine_leak.go` have outcome `leak` — the program exits cleanly but a goroutine is permanently in `GoWaiting` at end-of-trace

---

## Dataset Size Decision

**~225 examples is the pilot target.** 15 programs × 5 runs × 3 splits (25%/50%/75%).

This is intentionally a **pilot benchmark** — enough to answer the feasibility question
("does Claude fail at this zero-shot, and where?") and to support the WSO2 research proposal.
Effective sample diversity is 15 programs, not 225 — note this in the paper.

For a full conference submission later, expand to 30–50 programs. For now, proceed with 15.

---

### Phase 6 — Dataset Aggregation ✓

`dataset/aggregate.py` reads 212 per-run examples, groups by `(program_id, split_percent)`,
and computes empirical next-event distributions + Dirichlet posteriors (Jeffreys prior α=0.5).

Output: `dataset/output/aggregated.json` — 42 aggregated groups (207 scoreable examples;
5 deadlock/timeout runs have no `next_event` and are excluded from distributions).

**Key findings:**

| Nondeterminism level | Mean entropy |
|---|---|
| high | 1.396 bits |
| medium | 1.210 bits |
| low | 0.903 bits |
| none | 0.971 bits |

Entropy correctly stratifies by nondeterminism level (high > medium > low). This directly
supports the paper claim that model uncertainty should correlate with program nondeterminism.

**Deadlock collapse — reframing required:**
`04_deadlock` times out on every run (`TimedOut=true`, no `next_event`) so it produces zero
distribution data. Mean P(GoBlock) for leak programs (0.300) vs success programs (0.303) —
no collapse signal. The collapse claim must be reframed as: *partial traces of leak-bound
programs show P(GoUnblock)=0 in all cases*, which is consistent but weaker than originally
stated. Note this limitation explicitly in the paper.

**Python environment:** `pyproject.toml` + `uv` added. Run with `uv run python dataset/aggregate.py`.

Run: `uv run python dataset/aggregate.py` (requires `dataset/output/` populated by Phase 3)

---

### Phase 7 — Distribution Zero-Shot Eval ✓

`eval/dist_zero_shot.py` evaluates model calibration on distribution prediction vs the
Phase 4 point-prediction baseline.

**What it does:**

1. Loads 42 aggregated groups from `dataset/output/aggregated.json` (Phase 6 output)
2. For each group, picks a representative partial trace (run_index=0) and prompts Gemini
   for a probability distribution over the 6 next-event types
3. Scores against empirical distributions using:
   - **ECE** — mean |predicted[et] - empirical[et]| per event type
   - **KL divergence** — KL(empirical || predicted) in nats
   - **Model entropy** — H(predicted); should correlate with program nondeterminism
4. Computes Phase 4 one-hot baseline ECE for direct comparison (same axis)
5. Writes per-group results to `eval/results/dist_zero_shot_results.json`

**Results (gemini-3.5-flash, 42 groups) — two runs:**

| Metric | Phase 4 baseline | Phase 7 no thinking | Phase 7 thinking=1024 |
|---|---|---|---|
| ECE | 0.2050 | 0.1833 | **0.1689** |
| Mean KL(emp ∥ pred) | — | 9.50 nats | **7.00 nats** |

Model entropy by nondeterminism level:

| Level | No thinking | Thinking=1024 | Empirical H |
|---|---|---|---|
| high | 0.287 bits | **1.029 bits** | 1.396 bits |
| medium | 0.686 bits | **0.928 bits** | 1.210 bits |
| low | 0.042 bits | **0.399 bits** | 0.903 bits |
| none | 0.000 bits | **0.687 bits** | 0.971 bits |

**Key findings:**

1. **Thinking budget substantially reduces overconfidence.** Without thinking, model entropy
   is near zero (H ≈ 0 on most groups) — the model dresses up a point prediction as a
   distribution. With thinking=1024, model entropy rises to 0.4–1.0 bits across all levels,
   much closer to the empirical 0.9–1.4 bits.
2. **ECE improves with thinking.** 0.169 (thinking=1024) vs 0.183 (no thinking) vs 0.205
   (Phase 4 one-hot baseline). Thinking is the lever that converts distribution framing from
   marginal to meaningful.
3. **KL divergence drops from 9.5 → 7.0 nats** with thinking — distributions are closer
   to empirical across the board.
4. **Entropy-nondeterminism monotonicity still fails.** High (1.029) > medium (0.928)
   now holds, but none (0.687) > low (0.399) breaks strict ordering. Only 3 "none" groups —
   likely noise at small sample size. Softened claim: "thinking enables entropy to roughly
   track nondeterminism level."
5. **Root cause of residual gap:** Even with thinking=1024, model H is still 0.3–0.4 bits
   below empirical H — the model remains partially overconfident. The gap is the training
   signal Phase 8 quantifies.

Run: `uv run python eval/dist_zero_shot.py` (requires `.env` with `GEMINI_API_KEY`)

---

### Phase 8 — Dirichlet-Categorical Analysis ✓

`eval/dirichlet_analysis.py` computes anomaly scores, leak/deadlock distribution signatures,
entropy-vs-trace-depth curves, and the three key paper findings. No API calls — pure analysis
of existing Phase 6 and Phase 7 result files.

**Three key paper findings confirmed:**

**Finding 1 — Distribution framing reduces calibration error (17.6% improvement):**

| Condition | ECE |
|---|---|
| Phase 4 point-prediction baseline | 0.2050 |
| Phase 7 distribution, no thinking | 0.1833 |
| Phase 7 distribution, thinking=1024 | **0.1689** |

**Finding 2 — Model entropy tracks nondeterminism level (Spearman rho=0.412, p=0.007):**

With thinking=1024, model entropy is significantly positively correlated with nondeterminism
rank (none < low < medium < high). Moderate-to-strong effect. Claim SUPPORTED.

**Finding 3 — Anomaly scores as unsupervised bug signal (weak, not significant):**

`KL(predicted || uniform)` scores success vs buggy programs: mean 1.342 vs 1.182.
Cohen's d=0.294 (small effect), p=0.503 — not statistically significant. The anomaly score
does not cleanly separate buggy from correct programs at this dataset scale (n=9 buggy groups).

**Additional findings:**

**Distribution signature — P(GoUnblock)=0 is a clean goroutine-leak detector:**

| Outcome | split=25% | split=50% | split=75% |
|---|---|---|---|
| success | P(GoUnblock)=0.145 | 0.182 | 0.164 |
| leak (06, 14) | P(GoUnblock)=**0.000** | **0.000** | **0.000** |
| race (05) | P(GoUnblock)=**0.000** | **0.000** | **0.000** |

Leak programs (06_channel_select, 14_goroutine_leak): P(GoUnblock)=0 is causally motivated.
The leaked goroutine is permanently blocked on a channel that will never be signalled —
GoUnblock is structurally impossible at any trace depth. Zero false positives vs success programs.

Race program (05_race_condition): P(GoUnblock)=0 is a trace-structure confound, not a
consequence of the race. The bug (concurrent map writes) uses no blocking/unblocking
primitives. The WaitGroup unblock fires at the very end of a short trace, falling outside
all three split windows. These are different mechanisms and must be stated separately in
the paper. The headline finding is scoped to goroutine leaks.

**Entropy decreases monotonically as trace deepens (rho=-0.314, p=0.043):**

| Trace depth | Mean model entropy (bits) | Mean empirical entropy (bits) |
|---|---|---|
| 25% | 0.941 | 1.099 |
| 50% | 0.709 | 1.113 |
| 75% | 0.445 | 1.051 |

Model grows more confident as it sees more trace history — a statistically significant effect.
Empirical entropy is stable (~1.1 bits) across depths, showing the model's confidence gain
is from reasoning over trace context, not a property of the programs at that depth.

**Limitations documented:**
- P(GoUnblock)=0 signature is causally motivated for leak programs; the race program's
  P(GoUnblock)=0 is a confound (no blocking primitives in the bug path + short trace) —
  do not conflate the two mechanisms in the paper
- Anomaly detection (Finding 3) is underpowered at n=9 buggy groups — revisit with more programs
- Deadlock programs (04_deadlock) produce no trace at all (TimedOut=true), so the collapse
  claim is P(GoUnblock)=0 in leak programs, not P(GoBlock)→1 in deadlock programs
- Entropy-nondeterminism ordering (none < low < medium < high) holds in mean but breaks for
  "none" vs "low" at specific depths — likely noise at n=3 "none" groups

Run: `uv run python eval/dirichlet_analysis.py`
Output: `eval/results/dirichlet_analysis.json`

---

### Phase 5 — Results Analysis ✓

`eval/analyze/analyze.go` reads all `eval/results/*_result.json` files and prints:

```
=== Weave Zero-Shot Eval — 212 total examples ===
  Scored: 207 | Deadlock/no-next-event: 5 | Errors: 0

event_type accuracy:   116/207  (56.0%)
goroutine_id accuracy: 103/207  (49.8%)
```

**Key findings (Gemini zero-shot baseline):**

| Dimension | Best | Worst |
|---|---|---|
| Concurrency pattern | fanout 73.3% | mutex 43.3% |
| Event type | GoStart 67.0% | GoUnblock 40.7% |
| Nondeterminism | low 63.3% | high 44.4% |
| Trace split point | 25% / 50% tied 58.0% | 75% 52.2% |

**Confidence calibration failure:** High-confidence predictions correct only 58.0% of the time.
The model does not know what it doesn't know.

**Bug detection failure:** 0/5 deadlock examples mention "deadlock"; 0/12 race examples
mention "race" in reasoning. Point-prediction framing gives no signal for pathological outcomes.

**Most common confusions:** GoStart↔GoUnblock (20 cases), GoBlock↔GoStart (19 cases).
Block/unblock symmetry is the dominant failure mode.

Run: `go run eval/analyze/analyze.go` (requires `eval/results/` populated by Phase 4)

---

### Phase 4 — Zero-shot Evaluator ✓
- `eval/zero_shot.go` — loads 212 examples, calls Gemini API concurrently (10 goroutines),
  scores `correct_event_type` and `correct_goroutine_id`, writes per-example result JSON
- SDK: `google.golang.org/genai v1.59.0`; thinking budget set to 0
- Config: `GEMINI_API_KEY` + `MODEL` from `.env`
- Run: `go run eval/zero_shot.go` (requires `.env` in repo root)
- Results go to `eval/results/` (gitignored)

---

### Phase 3 — Trace Dataset Builder ✓
- `dataset/schema.go` — `WeaveMetadata` and `EvalExample` types
- `dataset/builder.go` — globs `programs/*.go`, runs each 5×, emits split examples
- `dataset/output/` — gitignored; regenerate with `go run dataset/builder.go dataset/schema.go`
- **212 examples** produced (225 max; 04_deadlock yields 1/run not 3, and one race run had 0 events)
- All 15 programs processed, 0 errors

---

## What's Next — Phase 6 Instructions

### Research Direction Change

The Phase 5 results confirm the feasibility question: existing models fail predictably at
concurrent next-state prediction (56% event_type accuracy, 0% bug detection). The failure
modes are clear: block/unblock symmetry confusion and zero bug-pattern awareness.

The new direction exploits what point-prediction throws away: **concurrent execution is
nondeterministic, so multiple runs of the same program give empirical evidence about the
*distribution* over next states, not just one sample from it.**

We reformulate the problem:

```
OLD: partial_trace → model → single prediction (GoBlock)
NEW: partial_trace → model → distribution  {GoBlock: 0.6, GoStart: 0.2, GoUnblock: 0.2}
```

The 5 runs per program in the existing dataset already contain this signal. We just need to
aggregate it.

---

### Phase 6 — Dataset Aggregation

Create branch `phase-6-aggregation`, then build `dataset/aggregate.py`.

**What it does:**
1. Reads all `dataset/output/*.json` examples (the 212 per-run point-prediction examples)
2. Groups by `(program_id, split_percent)` — treating same split % as "same prefix family"
   (approximation: partial traces across runs aren't identical, acknowledge in paper)
3. Counts occurrences of each `next_event.event_type` across the 5 runs in each group
4. Outputs aggregated examples with empirical distributions + Dirichlet posteriors

**New dataset schema per example:**
```json
{
  "program_id": "03_mutex_counter",
  "split_percent": 50,
  "concurrency_pattern": "mutex",
  "nondeterminism": "low",
  "full_outcome": "success",
  "run_count": 5,
  "next_event_distribution": {
    "GoBlock": 0.60,
    "GoStart": 0.20,
    "GoUnblock": 0.20,
    "GoEnd": 0.00,
    "GoSched": 0.00,
    "GoCreate": 0.00
  },
  "dirichlet_posterior": {
    "GoBlock": 3.5,
    "GoStart": 1.5,
    "GoUnblock": 1.5,
    "GoEnd": 0.5,
    "GoSched": 0.5,
    "GoCreate": 0.5
  }
}
```

Dirichlet prior: symmetric α=0.5 (Jeffreys prior — principled for small samples).
Posterior: α_posterior[k] = 0.5 + observed_count[k].

Also produce an **exploratory analysis**: for each group, print the distribution. Do
deadlock programs show P(GoBlock)→1 distribution collapse? Check this first — it's the
key empirical claim.

Run:
```bash
python dataset/aggregate.py
```

Output: `dataset/output/aggregated.json` (gitignored)

---

### Phase 7 — Distribution Zero-Shot Eval

Build `eval/dist_zero_shot.py`. New prompt asks for a probability distribution:

```
Predict the DISTRIBUTION over next scheduler events (probabilities summing to 1.0).
Respond in JSON: {"GoBlock": p, "GoCreate": p, "GoEnd": p, "GoSched": p, "GoStart": p, "GoUnblock": p}
```

Evaluate using Expected Calibration Error (ECE) — does P=0.6 mean correct 60% of the time?
Compare ECE to Phase 4 point-prediction baseline.

Also measure: does model entropy correlate with program nondeterminism level?

---

### Phase 8 — Dirichlet-Categorical Analysis

Build `eval/dirichlet_analysis.py`. Uses the aggregated dataset from Phase 6 to:

1. Compute anomaly scores per example:
   `anomaly = KL(predicted_dist || uniform)` — high = model is confident, low = uncertain/novel
2. Show deadlock distribution collapse signature: P(GoBlock) near 1.0, P(GoUnblock) near 0.0
3. Measure whether high model entropy predicts high observed nondeterminism
4. Produce the three key results for the paper:
   - Distribution-trained model has lower ECE than point-prediction model
   - High-entropy predictions correlate with high-nondeterminism programs
   - Deadlock programs have distinctive distribution signatures detectable from partial traces

---

## Known Design Decisions
- `channels` and `mutexes` in `StateSnapshot` are always empty — `go tool trace` doesn't expose object addresses
- `GoUndetermined` transitions are skipped in parser (goroutines alive before tracing started)
- Deadlocked programs produce no trace file (`trace.Stop()` never runs) — `RunResult.TimedOut=true`
- `RunProgram` uses `go build` + run binary, NOT `go run` — context cancellation must kill the actual process
- Race detector (`-race`) is always enabled in `RunProgram` — this is how `RaceOutput` gets populated

## Environment
- Go 1.26.4 (Homebrew), module name: `weave`
- `golang.org/x/exp v0.0.0-20260603202125-055de637280b`
- `ANTHROPIC_API_KEY` needed for Phase 4 (not needed for Phase 3)
- Programs directory: `programs/` (15 files, all `package main`)
- All programs use `WEAVE_TRACE_FILE` env var to write trace — set by `RunProgram` automatically
