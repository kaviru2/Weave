// WEAVE_META
// outcome: leak
// concurrency_pattern: channel
// goroutine_count: 2
// expected_nondeterminism: none
// description: subscriber goroutine ranges over an events channel; publisher sends a few events then exits without closing the channel, leaving the subscriber permanently blocked.

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

	events := make(chan string)

	// Subscriber goroutine processes events as they arrive.
	// BUG: main (the publisher) never calls close(events), so the subscriber
	// blocks in GoWaiting after the last event, waiting for a signal that
	// will never come — it leaks.
	go func() {
		for evt := range events {
			fmt.Println("event:", evt)
		}
	}()

	// Publish three events, then stop — subscriber is left blocking.
	events <- "login"
	events <- "purchase"
	events <- "logout"

	// Sleep so the trace captures the subscriber in GoWaiting before main exits.
	time.Sleep(50 * time.Millisecond)
}
