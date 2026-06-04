# Weave — Claude Code System Prompt

## What is Weave?

Weave is a research project exploring **Concurrent Code World Models (CCWM)** — extending the
world model paradigm (as established by Meta's CWM, arXiv:2510.02387) from sequential Python
execution to **concurrent, CSP-based languages** — specifically Go and Ballerina.

Meta's CWM proved that training a model on execution traces (state after every line) dramatically
improves code reasoning. But it only works for sequential Python. Nobody has done this for
concurrent programs where multiple goroutines/strands run simultaneously, share channels, acquire
locks, and produce non-deterministic interleavings.

Weave's research question:
> Can a model learn the concurrent execution state transition function — predicting how
> goroutine/strand state evolves given a program and a partial execution trace?

This is a research feasibility project. We are not training a model yet. We are building the
infrastructure to answer: **is this tractable?**

---

## Project Owner Context

- 4th year undergrad, doing this for fun and potential research
- Has volunteer/org access to WSO2 (creators of Ballerina)
- Has access to WSO2 servers and RunPod for compute when needed
- Working on M3 Pro MacBook, 18GB RAM
- WSO2 is also heavily invested in Go
- The eventual goal is a research proposal to WSO2 for compute + collaboration

---

## Current Phase: Feasibility

We need to answer four questions before anything else:

1. **Can we collect concurrent execution traces automatically from Go programs?**
2. **Is the concurrent state representation tractable? (Does it stay manageable in size?)**
3. **Do existing models fail predictably on concurrent state prediction zero-shot?**
4. **Does Ballerina's runtime expose enough trace data to be useful?**

Questions 1, 2, and 3 can be answered right now with code and the laptop.
Question 4 requires a conversation with WSO2 — not code.

---

## Your Job Right Now

Build the Go trace collection and evaluation pipeline. Specifically:

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

## Project Structure

```
weave/
  CLAUDE.md                    ← this file
  README.md                    ← keep updated as you build
  tracer/
    tracer.go                  ← core trace collection logic
    parser.go                  ← parse go tool trace output to JSON
    state.go                   ← concurrent state schema and types
  programs/
    01_simple_channel.go
    ... (15 programs)
  dataset/
    builder.go                 ← runs programs, builds eval dataset
    schema.go                  ← dataset JSON schema types
    output/                    ← generated dataset files go here (gitignore)
  eval/
    zero_shot.go               ← calls Claude API, records predictions
    analyze.py                 ← analysis and metrics
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

## Definition of Done for This Phase

We are done with this phase when we can run:

```bash
go run dataset/builder.go        # builds ~225 eval examples
go run eval/zero_shot.go         # runs zero-shot eval against Claude API
python eval/analyze.py           # prints accuracy report
```

And we have a clear answer to:
- What % of next-event predictions does Claude get right zero-shot?
- Where does it fail? (which patterns, which event types)
- Are deadlocks/races detectable from partial traces?

That data is the foundation of the research proposal.

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
