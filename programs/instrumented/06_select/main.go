// WEAVE_META
// outcome: leak
// concurrency_pattern: select
// goroutine_count: 2
// expected_nondeterminism: low
// description: Phase-21 instrumented variant of 06_channel_select (Kubernetes finishReq).
// WeaveChan records chan_send_block when the goroutine blocks on Send after the timeout
// case fires in main's select — the causal state for the GoUnblock 0% observability limit.
// Note: main's select uses wch.Chan() for the receive case; only the goroutine's Send
// path is fully instrumented.

package main

import (
	"fmt"
	"os"
	"runtime/trace"
	"time"
	"weave/instrumented"
)

// slowWork simulates a task that takes longer than the caller's timeout.
func slowWork() int {
	time.Sleep(20 * time.Millisecond)
	return 42
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

	// BUG (Kubernetes finishReq): ch is unbuffered. The child goroutine blocks on
	// Send after main has already returned via the timeout case. WeaveChan records
	// chan_send_block here so the tracer can link the GoUnblock to its causal channel.
	wch := instrumented.NewChan[int](0)
	go func() {
		result := slowWork()
		wch.Send(result) // blocks forever once the timeout case fires
	}()

	select {
	case result := <-wch.Chan(): // use underlying chan for select compatibility
		fmt.Println("got:", result)
	case <-time.After(1 * time.Millisecond):
		fmt.Println("timeout")
	}

	// Sleep so the trace captures the goroutine in GoWaiting state before main exits.
	time.Sleep(50 * time.Millisecond)
}
