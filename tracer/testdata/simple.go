// WEAVE_META
// outcome: success
// concurrency_pattern: channel
// goroutine_count: 2
// expected_nondeterminism: low
// description: one goroutine sends a value on a channel, main receives and exits cleanly.

package main

import (
	"fmt"
	"os"
	"runtime/trace"
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

	ch := make(chan int)
	go func() {
		ch <- 42
	}()
	v := <-ch
	fmt.Println(v)
}
