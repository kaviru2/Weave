// WEAVE_META
// outcome: success
// concurrency_pattern: pipeline
// goroutine_count: 4
// expected_nondeterminism: low
// description: Phase-21 instrumented variant of 08_pipeline.
// WeaveChan records send_waiters and recv_waiters at each pipeline stage,
// making the blocking handoffs between gen→square→main observable.

package main

import (
	"fmt"
	"os"
	"runtime/trace"
	"weave/instrumented"
)

// gen sends integers 1..n onto a WeaveChan then closes it.
func gen(n int) *instrumented.WeaveChan[int] {
	out := instrumented.NewChan[int](0)
	go func() {
		for i := 1; i <= n; i++ {
			out.Send(i)
		}
		out.Close()
	}()
	return out
}

// square reads from in, squares each value, and sends to out.
func square(in *instrumented.WeaveChan[int]) *instrumented.WeaveChan[int] {
	out := instrumented.NewChan[int](0)
	go func() {
		for {
			v, ok := in.Recv()
			if !ok {
				break
			}
			out.Send(v * v)
		}
		out.Close()
	}()
	return out
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

	for {
		v, ok := square(gen(5)).Recv()
		if !ok {
			break
		}
		fmt.Println(v)
	}
}
