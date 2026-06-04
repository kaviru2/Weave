// WEAVE_META
// outcome: leak
// concurrency_pattern: channel
// goroutine_count: 2
// expected_nondeterminism: none
// description: worker goroutine ranges over a channel that main never closes; goroutine is permanently blocked in GoWaiting when main exits.

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

	ch := make(chan int)

	// Worker ranges over ch. It will block waiting for the next value after
	// main stops sending, because main never calls close(ch).
	go func() {
		for v := range ch {
			fmt.Println("received:", v)
		}
	}()

	// Send a few values so the goroutine starts, then stop sending.
	for i := 0; i < 3; i++ {
		ch <- i
	}

	// Sleep long enough for the trace to capture the goroutine in GoWaiting state.
	// main exits without close(ch) — the goroutine leaks.
	time.Sleep(50 * time.Millisecond)
}
