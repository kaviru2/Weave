// WEAVE_META
// outcome: success
// concurrency_pattern: channel
// goroutine_count: 2
// expected_nondeterminism: low
// description: one goroutine sends five integers on an unbuffered channel, main receives them all.

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
		for i := 0; i < 5; i++ {
			ch <- i
		}
		close(ch)
	}()
	for v := range ch {
		fmt.Println(v)
	}
}
