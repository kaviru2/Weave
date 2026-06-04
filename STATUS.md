# Weave — Project Status

> Read this first when picking up on a new machine. Then read CLAUDE.md for the full plan.

## Current Phase
**Phase 1 — Go Trace Collector** (not started)

## Phase Checklist

- [ ] Phase 1 — Go Trace Collector (`tracer/tracer.go`, `parser.go`, `state.go`)
- [ ] Phase 2 — Test Program Suite (`programs/01_*.go` … `15_*.go`)
- [ ] Phase 3 — Trace Dataset Builder (`dataset/builder.go`, `schema.go`)
- [ ] Phase 4 — Zero-shot Evaluator (`eval/zero_shot.go`)
- [ ] Phase 5 — Results Analysis (`eval/analyze.py`)

## What's Done
- Repo initialized, connected to `kaviru2/Weave` on GitHub
- `CLAUDE.md` written with full project plan and constraints
- `STATUS.md` added for cross-machine continuity

## What's Next
Start Phase 1: scaffold `go.mod`, then build `tracer/state.go` (types), `tracer/tracer.go`
(runs the program with trace enabled), and `tracer/parser.go` (parses raw trace output to JSON).

## Known Issues / Decisions
_None yet._

## Environment Notes
- M3 Pro MacBook, 18GB RAM
- Go installed (verify with `go version` on new machine)
- Claude API key needed for Phase 4 (`ANTHROPIC_API_KEY`)
