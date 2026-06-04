# Weave — Project Status

> Read this first when picking up on a new machine. Then read CLAUDE.md for the full plan.

## Current Phase
**Phase 5 — Results Analysis** (not started — start here)

## Phase Checklist

- [x] Phase 1 — Go Trace Collector (`tracer/tracer.go`, `parser.go`, `state.go`) — **merged to main**
- [x] Phase 2 — Test Program Suite (`programs/01_*.go` … `15_*.go`) — **merged to main**
- [x] Phase 3 — Trace Dataset Builder (`dataset/builder.go`, `schema.go`) — **merged to main**
- [x] Phase 4 — Zero-shot Evaluator (`eval/zero_shot.go`) — **merged to main**
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

## What's Next — Phase 5 Instructions

Create branch `phase-5-analysis`, then build `eval/analyze.py` (see CLAUDE.md §Phase 5).

Key inputs:
- `eval/results/*_result.json` — one file per eval example, written by `zero_shot.go`

Run Phase 4 first to populate `eval/results/`:
```bash
# create .env with GEMINI_API_KEY and MODEL=gemini-3.5-flash
go run eval/zero_shot.go
```

Then run analysis:
```bash
python eval/analyze.py
```

Expected outputs (to stdout):
- Overall accuracy by event type
- Accuracy by concurrency pattern
- Accuracy by nondeterminism level
- Deadlock/race detection rate
- Confusion matrix (predicted vs actual event types)
- Most common failure patterns

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
