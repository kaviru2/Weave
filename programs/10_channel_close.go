// WEAVE_META
// outcome: success
// concurrency_pattern: channel
// goroutine_count: 2
// expected_nondeterminism: low
// description: sender goroutine closes the channel after sending all values; receiver uses range and exits cleanly.

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

	ch := make(chan string)
	go func() {
		words := []string{"alpha", "beta", "gamma", "delta", "epsilon"}
		for _, w := range words {
			ch <- w
		}
		close(ch)
	}()

	for word := range ch {
		fmt.Println(word)
	}
}
