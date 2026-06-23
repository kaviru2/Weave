// WEAVE_META
// outcome: leak
// concurrency_pattern: pipeline
// goroutine_count: 3
// expected_nondeterminism: none
// description: Phase-21 instrumented variant of 23_pipeline_no_drain.
// WeaveChan records the send_waiters state when stage1 goroutine is permanently
// blocked on Send after stage2 exits without draining the channel.

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

	intermediate := instrumented.NewChan[int](0) // unbuffered: stage1 blocks if stage2 isn't reading

	// Stage 1: producer sends a sequence of items.
	go func() {
		for i := 0; i < 10; i++ {
			intermediate.Send(i) // blocks on second send once stage2 exits
			fmt.Println("stage1 sent:", i)
		}
		intermediate.Close()
	}()

	// Stage 2: BUG — reads only one item and returns without draining the channel.
	// Stage1 is now permanently blocked trying to send the second item.
	go func() {
		v, _ := intermediate.Recv()
		fmt.Println("stage2 processed:", v)
		// returns here — stage1 leaks blocked on the second send
	}()

	// Sleep so the trace captures stage1 in GoWaiting before main exits.
	time.Sleep(50 * time.Millisecond)
}
