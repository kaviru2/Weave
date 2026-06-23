// WEAVE_META
// outcome: leak
// concurrency_pattern: mutex
// goroutine_count: 2
// expected_nondeterminism: none
// description: Phase-20 instrumented variant of 22_mutex_deadwait.
// WeaveMutex records holder=main and waiters=[worker] — the exact causal state
// needed to predict that the worker goroutine will never be unblocked.

package main

import (
	"fmt"
	"os"
	"runtime/trace"
	"time"
	"weave/instrumented"
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

	mu := instrumented.NewMutex()

	mu.Lock()
	fmt.Println("main holds the lock")

	go func() {
		mu.Lock() // blocks here — main never releases
		fmt.Println("worker acquired lock")
		mu.Unlock()
	}()

	time.Sleep(50 * time.Millisecond)
}
