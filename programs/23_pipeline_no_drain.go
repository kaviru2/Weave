// WEAVE_META
// outcome: leak
// concurrency_pattern: pipeline
// goroutine_count: 3
// expected_nondeterminism: none
// description: pipeline stage1 produces items into an unbuffered channel; stage2 exits after reading one item without draining, leaving stage1 permanently blocked on send.

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

	intermediate := make(chan int) // unbuffered: stage1 blocks if stage2 isn't reading

	// Stage 1: producer sends a sequence of items.
	go func() {
		for i := 0; i < 10; i++ {
			intermediate <- i // blocks on second send once stage2 exits
			fmt.Println("stage1 sent:", i)
		}
		close(intermediate)
	}()

	// Stage 2: BUG — reads only one item and returns without draining the channel.
	// Stage1 is now permanently blocked trying to send the second item.
	go func() {
		v := <-intermediate
		fmt.Println("stage2 processed:", v)
		// returns here — stage1 leaks blocked on the second send
	}()

	// Sleep so the trace captures stage1 in GoWaiting before main exits.
	time.Sleep(50 * time.Millisecond)
}
