// WEAVE_META
// outcome: race
// concurrency_pattern: channel
// goroutine_count: 6
// expected_nondeterminism: high
// description: five goroutines concurrently write to a shared map without synchronization, triggering the race detector; represents the non-blocking/shared-memory bug class from Tu et al. ASPLOS'19.

package main

import (
	"fmt"
	"os"
	"runtime"
	"runtime/trace"
	"sync"
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

	// NOTE: Go 1.22+ fixed loop-closure races by giving each iteration its own variable.
	// This program instead uses concurrent unprotected map writes — the most common
	// non-blocking/shared-memory bug class identified in Tu et al. ASPLOS'19.
	shared := map[int]int{}
	var wg sync.WaitGroup

	for i := 0; i < 5; i++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			// Yield to let other goroutines start, increasing race likelihood.
			runtime.Gosched()
			// BUG: concurrent writes to shared map without any synchronization.
			shared[id] = id * id
		}(i)
	}

	wg.Wait()
	fmt.Println(len(shared))
}
