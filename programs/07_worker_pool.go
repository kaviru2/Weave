// WEAVE_META
// outcome: success
// concurrency_pattern: channel
// goroutine_count: 5
// expected_nondeterminism: medium
// description: three workers drain a jobs channel; lock acquired after queue pop, the correct pattern from Kubernetes quota controller (Tu et al. ASPLOS'19).

package main

import (
	"fmt"
	"os"
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

	jobs := make(chan int, 9)
	results := make(chan int, 9)
	var mu sync.RWMutex
	var wg sync.WaitGroup

	// Start 3 workers. Each pops a job first, then acquires the read lock —
	// the fix pattern from the Kubernetes quota controller deadlock (ASPLOS'19).
	for w := 0; w < 3; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for job := range jobs {
				// Acquire lock after dequeue (not before) to avoid deadlock.
				mu.RLock()
				results <- job * job
				mu.RUnlock()
			}
		}()
	}

	// Send 9 jobs then close the channel.
	for j := 1; j <= 9; j++ {
		jobs <- j
	}
	close(jobs)

	go func() {
		wg.Wait()
		close(results)
	}()

	for r := range results {
		fmt.Println(r)
	}
}
