// WEAVE_META
// outcome: success
// concurrency_pattern: pipeline
// goroutine_count: 4
// expected_nondeterminism: low
// description: three-stage pipeline where each stage runs in its own goroutine: generate integers, square them, then print.

package main

import (
	"fmt"
	"os"
	"runtime/trace"
)

// gen sends integers 1..n onto a channel then closes it.
func gen(n int) <-chan int {
	out := make(chan int)
	go func() {
		for i := 1; i <= n; i++ {
			out <- i
		}
		close(out)
	}()
	return out
}

// square reads from in, squares each value, and sends to out.
func square(in <-chan int) <-chan int {
	out := make(chan int)
	go func() {
		for v := range in {
			out <- v * v
		}
		close(out)
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

	for v := range square(gen(5)) {
		fmt.Println(v)
	}
}
