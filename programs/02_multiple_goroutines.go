// WEAVE_META
// outcome: success
// concurrency_pattern: fanout
// goroutine_count: 4
// expected_nondeterminism: medium
// description: main fans out work to three goroutines and collects results through a shared results channel.

package main

import (
	"fmt"
	"os"
	"runtime/trace"
	"sync"
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
	results := make(chan int, len(jobs))
	var wg sync.WaitGroup

	for _, j := range jobs {
		wg.Add(1)
		go func(n int) {
			defer wg.Done()
			results <- n * n
		}(j)
	}

	go func() {
		wg.Wait()
		close(results)
	}()

	for r := range results {
		fmt.Println(r)
	}
}
