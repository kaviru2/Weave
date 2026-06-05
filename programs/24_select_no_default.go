// WEAVE_META
// outcome: leak
// concurrency_pattern: select
// goroutine_count: 2
// expected_nondeterminism: none
// description: goroutine blocks in a select statement with two cases; neither channel will ever receive data, so the goroutine is permanently blocked in GoWaiting.

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

	ch1 := make(chan int)
	ch2 := make(chan string)

	// BUG: goroutine blocks in select with no reachable case. Neither ch1 nor
	// ch2 are ever sent to — the goroutine is permanently stuck in GoWaiting.
	// A correct implementation would include a done channel or timeout case.
	go func() {
		select {
		case v := <-ch1:
			fmt.Println("int:", v)
		case s := <-ch2:
			fmt.Println("string:", s)
		}
	}()

	// Sleep so the trace captures the goroutine in GoWaiting before main exits.
	time.Sleep(50 * time.Millisecond)
}
