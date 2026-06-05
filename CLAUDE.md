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

Phases 1–9 are complete. Feasibility is confirmed, distribution learning is evaluated,
and the leak corpus has been expanded to 25 programs for the WSO2 research proposal.

---

## Project Owner Context

- 4th year undergrad, doing this for fun and potential research
- Has volunteer/org access to WSO2 (creators of Ballerina)
- Has access to WSO2 servers and RunPod for compute when needed
- Working on M3 Pro MacBook, 18GB RAM
- WSO2 is also heavily invested in Go
- The eventual goal is a research proposal to WSO2 for compute + collaboration

---

## Current Phase: Distribution Learning

The four feasibility questions are answered:

1. ✅ **Can we collect concurrent execution traces automatically from Go programs?** — Yes. `tracer/` works.
2. ✅ **Is the concurrent state representation tractable?** — Yes. 212 examples, manageable JSON.
3. ✅ **Do existing models fail predictably on concurrent state prediction zero-shot?** — Yes. 56% accuracy, 0% bug detection.
4. **Does Ballerina's runtime expose enough trace data to be useful?** — Requires WSO2 conversation, not code.

The new research direction: exploit concurrent nondeterminism as a training signal. Instead
of treating each run as a point-labelled example, aggregate multiple runs per program to
derive empirical next-state distributions and train to minimize KL divergence from them.

---

## Completed Phases (1–9)

All phases done and merged to main. See STATUS.md for full details.

- **Phase 1** — `tracer/` — Go trace collector using `golang.org/x/exp/trace`
- **Phase 2** — `programs/` — 15 concurrent Go programs with ASPLOS'19 provenance
- **Phase 3** — `dataset/builder.go` — 365 eval examples (25 programs × 5 runs × 3 splits)
- **Phase 4** — `eval/zero_shot.go` — Gemini zero-shot evaluator; results in `eval/results/`
- **Phase 5** — `eval/analyze/analyze.go` — results analyzer
- **Phase 6** — `dataset/aggregate.py` — 72 aggregated groups with empirical distributions
- **Phase 7** — `eval/dist_zero_shot.py` — distribution zero-shot eval (ECE, entropy)
- **Phase 8** — `eval/dirichlet_analysis.py` — Dirichlet-Categorical analysis
- **Phase 9** — `programs/16–25` — 10 new leak programs; dataset expanded to 25 programs

## Your Job Right Now

The pipeline is complete. WSO2 research proposal is the next step.
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

**Paper implication:** Reframe as "distribution signatures of specific goroutine-leak
mechanisms" rather than "P(GoUnblock)=0 as a general leak detector." The select-block leak
pattern is the cleanest signal; other mechanisms require deeper trace depths.

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
