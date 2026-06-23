// WEAVE_META
// outcome: success
// concurrency_pattern: fanin
// goroutine_count: 5
// expected_nondeterminism: high
// description: Phase-21 instrumented variant of 15_fan_in.
// WeaveChan records recv_waiters and send_waiters at each producer channel
// and the merged output channel, exposing the nondeterministic fan-in ordering.

package main

import (
	"fmt"
	"os"
	"runtime/trace"
	"sync"
	"weave/instrumented"
)

// merge fans in values from multiple WeaveChan inputs into a single output channel.
func merge(cs ...*instrumented.WeaveChan[int]) *instrumented.WeaveChan[int] {
	out := instrumented.NewChan[int](0)
	var wg sync.WaitGroup

	relay := func(c *instrumented.WeaveChan[int]) {
		defer wg.Done()
		for {
			v, ok := c.Recv()
			if !ok {
				break
			}
			out.Send(v)
		}
	}

	wg.Add(len(cs))
	for _, c := range cs {
		go relay(c)
	}

	go func() {
		wg.Wait()
		out.Close()
	}()

	return out
}

// producer sends n values starting from start onto a new WeaveChan then closes it.
func producer(start, n int) *instrumented.WeaveChan[int] {
	ch := instrumented.NewChan[int](0)
	go func() {
		for i := 0; i < n; i++ {
			ch.Send(start + i)
		}
		ch.Close()
	}()
	return ch
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

	merged := merge(producer(0, 3), producer(10, 3), producer(20, 3))
	for {
		v, ok := merged.Recv()
		if !ok {
			break
		}
		fmt.Println(v)
	}
}
