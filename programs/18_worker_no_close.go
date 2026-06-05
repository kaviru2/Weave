// WEAVE_META
// outcome: leak
// concurrency_pattern: channel
// goroutine_count: 4
// expected_nondeterminism: low
// description: three worker goroutines range over a jobs channel; main sends items then exits without closing the channel, leaving all workers permanently blocked.

package main

import (
	"fmt"
	"os"
	"runtime/trace"
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

	jobs := make(chan int)

	// Three workers drain the jobs channel. Which worker gets which job is
	// nondeterministic (low). All three will block waiting for the next job
	// because main never calls close(jobs).
	for w := 0; w < 3; w++ {
		go func(id int) {
			for job := range jobs {
				fmt.Printf("worker %d handling job %d\n", id, job)
			}
		}(w)
	}

	// Dispatch six jobs — all three workers become active — then stop.
	for i := 0; i < 6; i++ {
		jobs <- i
	}

	// Sleep so the trace captures all workers in GoWaiting before main exits.
	time.Sleep(50 * time.Millisecond)
}
