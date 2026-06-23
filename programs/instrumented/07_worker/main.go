// WEAVE_META
// outcome: success
// concurrency_pattern: channel
// goroutine_count: 5
// expected_nondeterminism: medium
// description: Phase-21 instrumented variant of 07_worker_pool.
// WeaveChan records recv_waiters on jobs and send_waiters on results for each worker.
// sync.RWMutex is left uninstrumented (WeaveMutex wraps sync.Mutex only).

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

	jobs := instrumented.NewChan[int](9)
	results := instrumented.NewChan[int](9)
	var mu sync.RWMutex
	var wg sync.WaitGroup

	// Start 3 workers. Each pops a job first, then acquires the read lock —
	// the fix pattern from the Kubernetes quota controller deadlock (ASPLOS'19).
	for w := 0; w < 3; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for {
				job, ok := jobs.Recv()
				if !ok {
					break
				}
				// Acquire lock after dequeue (not before) to avoid deadlock.
				mu.RLock()
				results.Send(job * job)
				mu.RUnlock()
			}
		}()
	}

	// Send 9 jobs then close the channel.
	for j := 1; j <= 9; j++ {
		jobs.Send(j)
	}
	jobs.Close()

	go func() {
		wg.Wait()
		results.Close()
	}()

	for {
		r, ok := results.Recv()
		if !ok {
			break
		}
		fmt.Println(r)
	}
}
