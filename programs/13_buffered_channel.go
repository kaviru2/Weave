// WEAVE_META
// outcome: success
// concurrency_pattern: channel
// goroutine_count: 2
// expected_nondeterminism: low
// description: sender fills a buffered channel (cap=3) before the receiver goroutine starts, demonstrating that sends do not block until the buffer is full.

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

	ch := make(chan int, 3)

	// Sender fills the buffer without blocking — no receiver is running yet.
	ch <- 1
	ch <- 2
	ch <- 3

	// Receiver starts after the buffer is already full.
	go func() {
		time.Sleep(5 * time.Millisecond)
		for v := range ch {
			fmt.Println(v)
		}
	}()

	close(ch)
	time.Sleep(20 * time.Millisecond) // wait for receiver to drain
}
