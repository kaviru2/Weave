# Weave — Project Status

> Read this first when picking up on a new machine. Then read CLAUDE.md for the full plan.

## Current Phase
**Phase 3 — Trace Dataset Builder** (not started — start here)

## Phase Checklist

- [x] Phase 1 — Go Trace Collector (`tracer/tracer.go`, `parser.go`, `state.go`) — **merged to main**
- [x] Phase 2 — Test Program Suite (`programs/01_*.go` … `15_*.go`) — **merged to main**
- [ ] Phase 3 — Trace Dataset Builder (`dataset/builder.go`, `schema.go`)
- [ ] Phase 4 — Zero-shot Evaluator (`eval/zero_shot.go`)
- [ ] Phase 5 — Results Analysis (`eval/analyze.py`)

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

## What's Next — Phase 3 Instructions

Create branch `phase-3-dataset`, then build two files:

### `dataset/schema.go`
Go structs for the JSON eval example format:
```go
type WeaveMetadata struct {
    Outcome                string // "success" | "deadlock" | "race" | "leak"
    ConcurrencyPattern     string // "channel" | "mutex" | "select" | "waitgroup" | "pipeline" | "fanout" | "fanin"
    GoroutineCount         int
    ExpectedNondeterminism string // "high" | "medium" | "low" | "none"
    Description            string
}

type EvalExample struct {
    ProgramID          string                   `json:"program_id"`
    ProgramSource      string                   `json:"program_source"`
    PartialTrace       []tracer.StateSnapshot   `json:"partial_trace"`
    NextEvent          *tracer.StateSnapshot    `json:"next_event"`       // nil for deadlock (no trace)
    FullOutcome        string                   `json:"full_outcome"`
    ConcurrencyPattern string                   `json:"concurrency_pattern"`
    GoroutineCount     int                      `json:"goroutine_count"`
    Nondeterminism     string                   `json:"nondeterminism"`
    RunIndex           int                      `json:"run_index"`        // which of the 5 runs
    SplitPercent       int                      `json:"split_percent"`    // 25 | 50 | 75
    RaceOutput         string                   `json:"race_output,omitempty"` // non-empty for race programs
    TimedOut           bool                     `json:"timed_out"`        // true for deadlock programs
}
```

### `dataset/builder.go`
Main logic:
1. Walk `programs/` — glob `*.go` files in sorted order
2. For each file, parse the `// WEAVE_META` header lines into `WeaveMetadata`
3. Read full source into string (for `ProgramSource` field)
4. Determine context timeout per program:
   - `outcome: deadlock` → 500ms (short — just long enough for a few trace events before timeout)
   - all others → 5s
5. Run each program 5 times via `tracer.RunProgram(ctx, sourceFile, outputDir)`
6. For each run:
   - If `TimedOut=true` (deadlock): emit one `EvalExample` with empty `PartialTrace`, `NextEvent=nil`, `TimedOut=true`
   - If trace file exists: call `tracer.ParseTrace(result.TraceFile)` to get `[]StateSnapshot`
     - Skip if fewer than 4 snapshots (not enough to split)
     - Emit 3 examples at 25%, 50%, 75% of len(snapshots):
       - `PartialTrace` = snapshots[0:N]
       - `NextEvent` = &snapshots[N]
7. Write each example to `dataset/output/<program_id>_run<N>_split<P>.json`
8. Print a summary table: program, runs completed, examples produced, any errors

### Output directory
`dataset/output/` — add to `.gitignore` (generated data, not committed)

### Run it
```bash
mkdir -p dataset/output
go run dataset/builder.go
```
Expected output: ~225 JSON files in `dataset/output/`, summary printed to stdout.

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
