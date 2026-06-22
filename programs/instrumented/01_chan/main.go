// WEAVE_META
// outcome: success
// concurrency_pattern: channel
// goroutine_count: 2
// expected_nondeterminism: low
// description: Phase-20 instrumented variant of 01_simple_channel.
// Uses WeaveChan so the tracer can record which goroutine is blocked
// on receive and link it to the GoUnblock event at send time.

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

	ch := instrumented.NewChan[int](0) // unbuffered — sender always blocks until receiver is ready
	go func() {
		for i := 0; i < 5; i++ {
			ch.Send(i)
		}
		ch.Close()
	}()

	for {
		v, ok := ch.Recv()
		if !ok {
			break
		}
		fmt.Println(v)
	}
}
