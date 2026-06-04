// WEAVE_META
// outcome: deadlock
// concurrency_pattern: waitgroup
// goroutine_count: 4
// expected_nondeterminism: none
// description: Wait() called inside goroutine-creation loop blocks all workers; reproduces Docker#25384 (Tu et al. ASPLOS'19).

package main

import (
	"os"
	"runtime/trace"
	"sync"
	"time"
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

	// Sentinel goroutine prevents "all goroutines are asleep" runtime panic so that
	// RunProgram's context deadline fires instead (giving TimedOut=true in RunResult).
	go func() { time.Sleep(24 * time.Hour) }()

	var wg sync.WaitGroup
	wg.Add(3)
	for i := 0; i < 3; i++ {
		go func() {
			defer wg.Done()
			time.Sleep(5 * time.Millisecond)
		}()
		// BUG (Docker#25384): Wait() is inside the loop. After the first iteration,
		// wg.Wait() blocks here waiting for all 3 Done() calls, but only 1 goroutine
		// has been created so far — the remaining 2 goroutines are never spawned.
		wg.Wait()
	}
}
