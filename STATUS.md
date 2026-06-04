# Weave — Project Status

> Read this first when picking up on a new machine. Then read CLAUDE.md for the full plan.

## Current Phase
**Phase 2 — Test Program Suite** (not started — start here)

## Phase Checklist

- [x] Phase 1 — Go Trace Collector (`tracer/tracer.go`, `parser.go`, `state.go`) — **merged to main**
- [ ] Phase 2 — Test Program Suite (`programs/01_*.go` … `15_*.go`)
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

## What's Next — Phase 2 Instructions
Create branch `phase-2-programs`, then build `programs/` with 15 Go programs.

Each program needs:
1. A `// WEAVE_META` comment block at the top (outcome, concurrency_pattern, goroutine_count, expected_nondeterminism, description)
2. This trace boilerplate at the top of `main()`:
```go
if tf := os.Getenv("WEAVE_TRACE_FILE"); tf != "" {
    f, err := os.Create(tf)
    if err == nil {
        if err := trace.Start(f); err == nil {
            defer func() { trace.Stop(); f.Close() }()
        }
    }
}
```
Imports needed: `"os"`, `"runtime/trace"`

Programs to build (in order):
```
01_simple_channel.go       — one goroutine, one channel, clean send/receive
02_multiple_goroutines.go  — 3 goroutines, fan-out pattern
03_mutex_counter.go        — shared counter with mutex
04_deadlock.go             — intentional deadlock
05_race_condition.go       — intentional race condition
06_channel_select.go       — select across multiple channels
07_worker_pool.go          — classic worker pool
08_pipeline.go             — pipeline (stage1 → stage2 → stage3)
09_timeout_pattern.go      — context with timeout
10_channel_close.go        — close semantics, range over channel
11_waitgroup.go            — sync.WaitGroup
12_once.go                 — sync.Once
13_buffered_channel.go     — buffered vs unbuffered difference
14_goroutine_leak.go       — goroutine that never exits
15_fan_in.go               — fan-in, multiple producers one consumer
```

After writing each program, do a quick smoke test:
```bash
WEAVE_TRACE_FILE=/tmp/test.trace go run programs/<file>.go
```

## Known Design Decisions
- `channels` and `mutexes` in `StateSnapshot` are always empty — `go tool trace` doesn't expose object addresses
- `GoUndetermined` transitions are skipped (goroutines alive before tracing started)
- Deadlocked programs produce no trace file (`trace.Stop()` never runs); `RunResult.TimedOut=true` signals this
- Use `go build` + run binary, NOT `go run` — context cancellation must kill the actual program

## Environment
- Go 1.26.4 (Homebrew), `golang.org/x/exp v0.0.0-20260603202125-055de637280b`
- `ANTHROPIC_API_KEY` needed for Phase 4
