// WEAVE_META
// outcome: leak
// concurrency_pattern: channel
// goroutine_count: 2
// expected_nondeterminism: none
// description: Phase-20 instrumented variant of 14_goroutine_leak.
// WeaveChan shows the goroutine's recv_waiters state when it blocks
// after receiving all values — demonstrating the P(GoUnblock)=0 leak signature.

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

	ch := instrumented.NewChan[int](0) // unbuffered

	go func() {
		for {
			v, ok := ch.Recv()
			if !ok {
				break
			}
			fmt.Println("received:", v)
		}
	}()

	for i := 0; i < 3; i++ {
		ch.Send(i)
	}

	// Sleep with goroutine permanently blocked on Recv — channel never closed.
	time.Sleep(50 * time.Millisecond)
}
