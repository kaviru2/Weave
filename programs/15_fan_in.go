// WEAVE_META
// outcome: success
// concurrency_pattern: fanin
// goroutine_count: 5
// expected_nondeterminism: high
// description: three producer goroutines send values onto separate channels; a merge goroutine fans them into one output channel consumed by main.

package main

import (
	"fmt"
	"os"
	"runtime/trace"
	"sync"
)

// merge fans in values from multiple input channels into a single output channel.
func merge(cs ...<-chan int) <-chan int {
	out := make(chan int)
	var wg sync.WaitGroup

	relay := func(c <-chan int) {
		defer wg.Done()
		for v := range c {
			out <- v
		}
	}

	wg.Add(len(cs))
	for _, c := range cs {
		go relay(c)
	}

	go func() {
		wg.Wait()
		close(out)
	}()

	return out
}

// producer sends n values starting from start onto a new channel then closes it.
func producer(start, n int) <-chan int {
	ch := make(chan int)
	go func() {
		for i := 0; i < n; i++ {
			ch <- start + i
		}
		close(ch)
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
	for v := range merged {
		fmt.Println(v)
	}
}
