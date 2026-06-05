// WEAVE_META
// outcome: leak
// concurrency_pattern: channel
// goroutine_count: 2
// expected_nondeterminism: none
// description: goroutine reads from time.Ticker.C in a loop; main never calls ticker.Stop() and exits, leaving the goroutine permanently blocked on the ticker channel.

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

	ticker := time.NewTicker(10 * time.Millisecond)

	// Goroutine reads tick events. It will block on ticker.C between ticks.
	// BUG: main never calls ticker.Stop(); the goroutine is left alive and
	// permanently cycling between GoWaiting and GoRunnable when main exits.
	go func() {
		for t := range ticker.C {
			fmt.Println("tick at", t.UnixMilli())
		}
	}()

	// Let one tick fire so the goroutine runs at least once.
	time.Sleep(15 * time.Millisecond)

	// Exit without ticker.Stop() or closing ticker.C — goroutine leaks.
	time.Sleep(50 * time.Millisecond)
}
