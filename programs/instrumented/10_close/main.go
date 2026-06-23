// WEAVE_META
// outcome: success
// concurrency_pattern: channel
// goroutine_count: 2
// expected_nondeterminism: low
// description: Phase-21 instrumented variant of 10_channel_close.
// WeaveChan records the recv_waiters state as the goroutine blocks on each
// receive, and the causal chan_close event that terminates the loop.

package main

import (
	"fmt"
	"os"
	"runtime/trace"
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

	ch := instrumented.NewChan[string](0)
	go func() {
		words := []string{"alpha", "beta", "gamma", "delta", "epsilon"}
		for _, w := range words {
			ch.Send(w)
		}
		ch.Close()
	}()

	for {
		word, ok := ch.Recv()
		if !ok {
			break
		}
		fmt.Println(word)
	}
}
