// WEAVE_META
// outcome: leak
// concurrency_pattern: channel
// goroutine_count: 2
// expected_nondeterminism: none
// description: Phase-21 instrumented variant of 20_event_listener_leak.
// WeaveChan records the recv_waiters state when the subscriber goroutine is
// blocked waiting for events — the publisher exits without calling events.Close().

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

	events := instrumented.NewChan[string](0)

	// Subscriber goroutine processes events as they arrive.
	// BUG: main (the publisher) never calls events.Close(), so the subscriber
	// blocks in GoWaiting after the last event — it leaks.
	go func() {
		for {
			evt, ok := events.Recv()
			if !ok {
				break
			}
			fmt.Println("event:", evt)
		}
	}()

	// Publish three events, then stop — subscriber is left blocking.
	events.Send("login")
	events.Send("purchase")
	events.Send("logout")

	// Sleep so the trace captures the subscriber in GoWaiting before main exits.
	time.Sleep(50 * time.Millisecond)
}
