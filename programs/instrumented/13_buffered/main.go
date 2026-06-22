// WEAVE_META
// outcome: success
// concurrency_pattern: channel
// goroutine_count: 2
// expected_nondeterminism: low
// description: Phase-20 instrumented variant of 13_buffered_channel.
// WeaveChan tracks qcount as main fills the buffer; shows that
// sends don't block until the buffer is full.

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

	ch := instrumented.NewChan[int](3)

	// Main fills the buffer without blocking — receiver goroutine not started yet.
	ch.Send(1)
	ch.Send(2)
	ch.Send(3)

	// Receiver starts after the buffer is already full.
	go func() {
		time.Sleep(5 * time.Millisecond)
		for {
			v, ok := ch.Recv()
			if !ok {
				break
			}
			fmt.Println(v)
		}
	}()

	ch.Close()
	time.Sleep(20 * time.Millisecond)
}
