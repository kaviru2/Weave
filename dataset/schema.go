package main

import "weave/tracer"

// WeaveMetadata holds the structured metadata parsed from the // WEAVE_META comment block
// at the top of each test program.
type WeaveMetadata struct {
	Outcome                string // "success" | "deadlock" | "race" | "leak"
	ConcurrencyPattern     string // "channel" | "mutex" | "select" | "waitgroup" | "pipeline" | "fanout" | "fanin"
	GoroutineCount         int
	ExpectedNondeterminism string // "high" | "medium" | "low" | "none"
	Description            string
}

// EvalExample is one evaluation sample: a partial trace, the next ground-truth event,
// and all metadata needed to bucket results by pattern, nondeterminism, and outcome.
type EvalExample struct {
	ProgramID          string                  `json:"program_id"`
	ProgramSource      string                  `json:"program_source"`
	PartialTrace       []tracer.StateSnapshot  `json:"partial_trace"`
	NextEvent          *tracer.StateSnapshot   `json:"next_event"`            // nil for deadlock (no trace)
	FullOutcome        string                  `json:"full_outcome"`
	ConcurrencyPattern string                  `json:"concurrency_pattern"`
	GoroutineCount     int                     `json:"goroutine_count"`
	Nondeterminism     string                  `json:"nondeterminism"`
	RunIndex           int                     `json:"run_index"`             // 0-indexed, which of the 5 runs
	SplitPercent       int                     `json:"split_percent"`         // 25 | 50 | 75
	RaceOutput         string                  `json:"race_output,omitempty"` // non-empty when race detector fires
	TimedOut           bool                    `json:"timed_out"`             // true for deadlock programs
}
