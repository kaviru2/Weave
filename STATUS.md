# Weave — Project Status

> Read this first when picking up on a new machine. Then read CLAUDE.md for the full plan.

## Current Phase
**Phase 2 — Test Program Suite** (not started)

## Phase Checklist

- [x] Phase 1 — Go Trace Collector (`tracer/tracer.go`, `parser.go`, `state.go`)
- [ ] Phase 2 — Test Program Suite (`programs/01_*.go` … `15_*.go`)
- [ ] Phase 3 — Trace Dataset Builder (`dataset/builder.go`, `schema.go`)
- [ ] Phase 4 — Zero-shot Evaluator (`eval/zero_shot.go`)
- [ ] Phase 5 — Results Analysis (`eval/analyze.py`)

## What's Done

### Phase 1 — Go Trace Collector (branch: `phase-1-tracer`, ready to merge)
- `tracer/state.go` — `EventType` constants, `GoroutineState`, `StateSnapshot`, `RunResult` types
- `tracer/tracer.go` — `RunProgram(ctx, sourceFile, outputDir)`: builds binary with `-race`, runs it under context deadline; handles deadlocks via timeout
- `tracer/parser.go` — `ParseTrace(traceFile)`: reads `golang.org/x/exp/trace` events, maps goroutine state transitions to `StateSnapshot` slices
- `tracer/testdata/simple.go` + `infinite.go` — fixture programs for tests
- `tracer/tracer_test.go` + `parser_test.go` — 17 tests, all passing
- Trace API used: `golang.org/x/exp/trace` (public API, NOT `internal/trace`)
- **Key design decision**: `go build` + run binary (not `go run`) so context cancellation kills the actual program, not the go wrapper

## What's Next
Start Phase 2: create `programs/` with 15 Go programs of increasing complexity.
Each program needs the WEAVE_META comment block and the trace boilerplate in `main()`:
```go
if tf := os.Getenv("WEAVE_TRACE_FILE"); tf != "" {
    f, _ := os.Create(tf)
    if err := trace.Start(f); err == nil {
        defer func() { trace.Stop(); f.Close() }()
    }
}
```
New branch: `phase-2-programs`

## Known Issues / Decisions
- `go tool trace` does NOT expose channel/mutex addresses — `channels` and `mutexes` fields in `StateSnapshot` are always empty maps. This is documented in `state.go`.
- `GoUndetermined` transitions are skipped — goroutines alive before tracing started won't emit phantom events.
- Deadlocked programs (e.g. `select {}`) produce no trace file since `trace.Stop()` never runs. `RunResult.TimedOut=true` signals this to the dataset builder.

## Environment Notes
- Go 1.26.4 (installed via Homebrew)
- `golang.org/x/exp v0.0.0-20260603202125-055de637280b`
- Claude API key needed for Phase 4 (`ANTHROPIC_API_KEY`)
