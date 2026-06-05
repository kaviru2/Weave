// WEAVE_META
// outcome: leak
// concurrency_pattern: channel
// goroutine_count: 3
// expected_nondeterminism: none
// description: two handler goroutines range over a requests channel; main sends a few items then exits without closing the channel, leaving handlers permanently blocked.

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

	requests := make(chan int)

	// Two handler goroutines read from requests. They will block in GoWaiting
	// once main stops sending, because main never calls close(requests).
	for i := 0; i < 2; i++ {
		go func(id int) {
			for req := range requests {
				fmt.Printf("handler %d processed request %d\n", id, req)
			}
		}(i)
	}

	// Send three requests then stop — handlers are left waiting for more.
	for i := 0; i < 3; i++ {
		requests <- i
	}

	// Sleep so the trace captures both goroutines in GoWaiting before main exits.
	time.Sleep(50 * time.Millisecond)
}
