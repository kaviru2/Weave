// WEAVE_META
// outcome: leak
// concurrency_pattern: channel
// goroutine_count: 3
// expected_nondeterminism: none
// description: Phase-21 instrumented variant of 16_http_handler_leak.
// WeaveChan shows recv_waiters state when both handler goroutines are blocked
// waiting for requests that will never arrive — the channel is never closed.

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

	requests := instrumented.NewChan[int](0)

	// Two handler goroutines read from requests. They will block in GoWaiting
	// once main stops sending, because main never calls requests.Close().
	for i := 0; i < 2; i++ {
		go func(id int) {
			for {
				req, ok := requests.Recv()
				if !ok {
					break
				}
				fmt.Printf("handler %d processed request %d\n", id, req)
			}
		}(i)
	}

	// Send three requests then stop — handlers are left waiting for more.
	for i := 0; i < 3; i++ {
		requests.Send(i)
	}

	// Sleep so the trace captures both goroutines in GoWaiting before main exits.
	time.Sleep(50 * time.Millisecond)
}
