// WEAVE_META
// outcome: deadlock
// concurrency_pattern: channel
// goroutine_count: 1
// expected_nondeterminism: none
// description: blocks forever on an empty select — used to test tracer timeout handling.

package main

import (
	"os"
	"runtime/trace"
)

func main() {
	if tf := os.Getenv("WEAVE_TRACE_FILE"); tf != "" {
		f, err := os.Create(tf)
		if err == nil {
			if err := trace.Start(f); err == nil {
				defer func() { trace.Stop(); f.Close() }()
			}
		}
	}

	select {} // blocks forever
}
