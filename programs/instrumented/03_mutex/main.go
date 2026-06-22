// WEAVE_META
// outcome: success
// concurrency_pattern: mutex
// goroutine_count: 5
// expected_nondeterminism: medium
// description: Phase-20 instrumented variant of 03_mutex_counter.
// Uses WeaveMutex so the tracer can record which goroutine holds the
// lock and who is waiting — making GoUnblock events for mutex contention
// fully traceable.

package main

import (
	"fmt"
	"os"
	"runtime/trace"
	"sync"
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
	counter := 0
	var wg sync.WaitGroup

	for i := 0; i < 4; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 5; j++ {
				mu.Lock()
				counter++
				mu.Unlock()
			}
		}()
	}

	wg.Wait()
	fmt.Println(counter)
}
