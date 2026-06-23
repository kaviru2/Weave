// WEAVE_META
// outcome: leak
// concurrency_pattern: channel
// goroutine_count: 2
// expected_nondeterminism: none
// description: Phase-20 instrumented variant of 21_done_channel_leak.
// WeaveChan's recv_waiters makes the permanently-blocked goroutine visible
// in the snapshot — the clearest channel-observability case.

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

	done := instrumented.NewChan[struct{}](0) // unbuffered done channel

	go func() {
		fmt.Println("working...")
		time.Sleep(5 * time.Millisecond)
		fmt.Println("work complete, waiting for shutdown signal")
		done.Recv() // blocks here forever — main never sends/closes
		fmt.Println("shutting down")
	}()

	time.Sleep(50 * time.Millisecond)
}
