// WEAVE_META
// outcome: leak
// concurrency_pattern: channel
// goroutine_count: 4
// expected_nondeterminism: low
// description: Phase-21 instrumented variant of 18_worker_no_close.
// WeaveChan records recv_waiters when all three workers are blocked waiting
// for the next job — main never calls jobs.Close(), so they leak forever.

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

	jobs := instrumented.NewChan[int](0)

	// Three workers drain the jobs channel. Which worker gets which job is
	// nondeterministic (low). All three will block waiting for the next job
	// because main never calls jobs.Close().
	for w := 0; w < 3; w++ {
		go func(id int) {
			for {
				job, ok := jobs.Recv()
				if !ok {
					break
				}
				fmt.Printf("worker %d handling job %d\n", id, job)
			}
		}(w)
	}

	// Dispatch six jobs — all three workers become active — then stop.
	for i := 0; i < 6; i++ {
		jobs.Send(i)
	}

	// Sleep so the trace captures all workers in GoWaiting before main exits.
	time.Sleep(50 * time.Millisecond)
}
