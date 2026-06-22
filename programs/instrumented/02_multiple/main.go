// WEAVE_META
// outcome: success
// concurrency_pattern: fanout
// goroutine_count: 4
// expected_nondeterminism: medium
// description: Phase-20 instrumented variant of 02_multiple_goroutines.
// WeaveChan on the buffered results channel records recv_waiters when main
// drains results — linking GoUnblock events to the results channel.

package main

import (
	"fmt"
	"os"
	"runtime/trace"
	"sync"
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

	jobs := []int{10, 20, 30}
	results := instrumented.NewChan[int](len(jobs)) // buffered — goroutines won't block on send
	var wg sync.WaitGroup

	for _, j := range jobs {
		wg.Add(1)
		jj := j
		go func() {
			defer wg.Done()
			results.Send(jj * jj)
		}()
	}

	go func() {
		wg.Wait()
		results.Close()
	}()

	for {
		r, ok := results.Recv()
		if !ok {
			break
		}
		fmt.Println(r)
	}
}
