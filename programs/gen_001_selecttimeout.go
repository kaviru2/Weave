// WEAVE_META
// outcome: success
// concurrency_pattern: select
// goroutine_count: 2
// expected_nondeterminism: low
// description: Select statement on unbuffered channel, leak_bug=False

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

	ch := make(chan int, 1)

	go func() {
		// Simulate processing delay
		time.Sleep(time.Millisecond * 10)
		ch <- 42
	}()

	select {
	case val := <-ch:
		fmt.Println("received:", val)
	case <-time.After(1 * time.Millisecond):
		fmt.Println("timeout occurred")
	}

	// Small delay to allow the leaked goroutine to lock into GoWaiting block
	time.Sleep(time.Millisecond * 20)
}
