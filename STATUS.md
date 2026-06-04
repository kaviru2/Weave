# Weave — Project Status

> Read this first when picking up on a new machine. Then read CLAUDE.md for the full plan.

## Current Phase
**Phase 3 — Trace Dataset Builder** (not started — start here)

## Phase Checklist

- [x] Phase 1 — Go Trace Collector (`tracer/tracer.go`, `parser.go`, `state.go`) — **merged to main**
- [x] Phase 2 — Test Program Suite (`programs/01_*.go` … `15_*.go`) — **on branch phase-2-programs**
- [ ] Phase 3 — Trace Dataset Builder (`dataset/builder.go`, `schema.go`)
- [ ] Phase 4 — Zero-shot Evaluator (`eval/zero_shot.go`)
- [ ] Phase 5 — Results Analysis (`eval/analyze.py`)

## What's Done

### Phase 1 — Go Trace Collector ✓
- `tracer/state.go` — `EventType` constants, `GoroutineState`, `StateSnapshot`, `RunResult` types
- `tracer/tracer.go` — `RunProgram(ctx, sourceFile, outputDir)`: builds binary with `-race`, runs under context deadline; `TimedOut=true` for deadlocked programs
- `tracer/parser.go` — `ParseTrace(traceFile)`: reads `golang.org/x/exp/trace` events, maps goroutine state transitions to `[]StateSnapshot`
- `tracer/testdata/simple.go` + `infinite.go` — fixture programs for tests
- 17 tests passing (`go test ./tracer/...`)
- Trace API: `golang.org/x/exp/trace` (public API, Go 1.26.4)

## What's Done

### Phase 2 — Test Program Suite ✓
- 15 programs in `programs/` covering all concurrency patterns from CLAUDE.md
- 5 programs reproduce bug patterns from Tu et al. ASPLOS'19 (citable provenance for paper):
  - `04_deadlock.go` — WaitGroup misuse, Docker#25384
  - `05_race_condition.go` — concurrent map writes without sync (non-blocking/shared-memory class)
  - `06_channel_select.go` — goroutine leak via unbuffered channel + timeout, Kubernetes finishReq
  - `12_once.go` — sync.Once prevents double-close panic, Docker#24007
  - `07_worker_pool.go` — worker pool with correct lock ordering (fix of Kubernetes quota deadlock)
- 2 bug/fix pairs for the paper's evaluation: 04↔11 (WaitGroup), 06↔09 (timeout + channel buffer)
- Go 1.22+ loop-closure bug is gone (per-iteration variables); race in 05 uses concurrent map writes instead
- Deadlock sentinel pattern: `go func() { time.Sleep(24*time.Hour) }()` prevents runtime deadlock
  detector from firing before RunProgram context deadline (gives TimedOut=true as documented)
- All 17 Phase 1 tracer tests still pass

## What's Next — Phase 3 Instructions
Create branch `phase-3-dataset`, then build `dataset/builder.go` and `dataset/schema.go`.

The builder must:
1. Walk `programs/` and collect all `.go` files
2. Parse `// WEAVE_META` header from each file into metadata struct
3. For each program, call `tracer.RunProgram()` 5 times (different interleavings)
4. For each run that produces a trace, call `tracer.ParseTrace()` to get `[]StateSnapshot`
5. For each trace, produce 3 evaluation examples at 25%, 50%, 75% of events:
   ```json
   {
     "program_id": "03_mutex_counter",
     "program_source": "...full source...",
     "partial_trace": [ ...first N snapshots... ],
     "next_event": { ...snapshot N+1... },
     "full_outcome": "success",
     "concurrency_pattern": "mutex",
     "goroutine_count": 5,
     "nondeterminism": "medium"
   }
   ```
6. Write output to `dataset/output/<program_id>_<run>.json` (gitignored)
7. Handle TimedOut=true (no trace file) — record as deadlock example with empty partial_trace
8. Handle race programs — record RaceOutput alongside the example

Target: 15 programs × 5 runs × 3 splits = ~225 examples (fewer for deadlock/leak programs)

Key: programs 04 and 14 may time out (use a short context, e.g. 500ms, for deadlock programs)

## Known Design Decisions
- `channels` and `mutexes` in `StateSnapshot` are always empty — `go tool trace` doesn't expose object addresses
- `GoUndetermined` transitions are skipped (goroutines alive before tracing started)
- Deadlocked programs produce no trace file (`trace.Stop()` never runs); `RunResult.TimedOut=true` signals this
- Use `go build` + run binary, NOT `go run` — context cancellation must kill the actual program

## Environment
- Go 1.26.4 (Homebrew), `golang.org/x/exp v0.0.0-20260603202125-055de637280b`
- `ANTHROPIC_API_KEY` needed for Phase 4
