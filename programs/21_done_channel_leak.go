// WEAVE_META
// outcome: leak
// concurrency_pattern: channel
// goroutine_count: 2
// expected_nondeterminism: none
// description: goroutine blocks waiting for a shutdown signal on a done channel; main never sends or closes done, so the goroutine leaks permanently in GoWaiting.

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

	done := make(chan struct{})

	// Goroutine does some work, then waits for the done signal before exiting.
	// BUG: main never sends to or closes done. The goroutine finishes its work
	// and blocks on <-done indefinitely — it leaks.
	go func() {
		fmt.Println("working...")
		time.Sleep(5 * time.Millisecond)
		fmt.Println("work complete, waiting for shutdown signal")
		<-done // blocks here forever
		fmt.Println("shutting down")
	}()

	// Sleep long enough for the goroutine to finish work and block on <-done.
	// main exits without sending to done — goroutine leaks in GoWaiting.
	time.Sleep(50 * time.Millisecond)
}
