// WEAVE_META
// outcome: leak
// concurrency_pattern: channel
// goroutine_count: 6
// expected_nondeterminism: none
// description: Phase-21 instrumented variant of 25_goroutine_per_request.
// WeaveChan records recv_waiters for each per-request response channel;
// main never sends responses, so all five goroutines block and leak.

package main

import (
	"fmt"
	"os"
	"runtime/trace"
	"time"
	"weave/instrumented"
)

type request struct {
	id   int
	resp *instrumented.WeaveChan[int]
}

func main() {
	if tf := os.Getenv("WEAVE_TRACE_FILE"); tf != "" {
		f, err := os.Create(tf)
		if err == nil {
			if err := trace.Start(f); err == nil {
				defer func() { trace.Stop(); f.Close() }()
			}
		}
	}

	// Spawn one goroutine per request — each waits for a response on its own channel.
	// BUG: main never sends responses. All five goroutines block in GoWaiting
	// on their response channels — they all leak when main exits.
	for i := 0; i < 5; i++ {
		req := request{id: i, resp: instrumented.NewChan[int](0)}
		go func(r request) {
			fmt.Printf("request %d: waiting for response\n", r.id)
			result, _ := r.resp.Recv() // blocks here forever
			fmt.Printf("request %d: got %d\n", r.id, result)
		}(req)
	}

	// Sleep so the trace captures all five goroutines in GoWaiting before main exits.
	time.Sleep(50 * time.Millisecond)
}
