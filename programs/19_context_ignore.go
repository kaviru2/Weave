// WEAVE_META
// outcome: leak
// concurrency_pattern: channel
// goroutine_count: 2
// expected_nondeterminism: none
// description: goroutine blocks on a work channel instead of using select with ctx.Done(); main cancels the context and exits, but the goroutine cannot see the cancellation and leaks.

package main

import (
	"context"
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

	ctx, cancel := context.WithCancel(context.Background())
	_ = ctx // context created but goroutine never reads ctx.Done()

	work := make(chan int)

	// BUG: goroutine ignores ctx.Done(). A correct implementation would use
	// select { case v := <-work: ... case <-ctx.Done(): return }.
	// Instead it blocks directly on work — context cancellation is invisible to it.
	go func() {
		for {
			v := <-work // blocks here; ctx cancel has no effect
			fmt.Println("processed:", v)
		}
	}()

	work <- 1   // give goroutine one item so it starts
	cancel()    // cancel context — goroutine doesn't see this
	work <- 2   // goroutine processes one more, then blocks waiting for a third

	// Sleep so the trace captures the goroutine in GoWaiting before main exits.
	time.Sleep(50 * time.Millisecond)
}
