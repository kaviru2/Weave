// WEAVE_META
// outcome: nonblocking
// concurrency_pattern: channel
// goroutine_count: 1
// expected_nondeterminism: medium
// description: Auto-extracted GoBench bug kernel moby_27037 (nonblocking)

package main

import (
	"fmt"
	"sync"

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

	wg := sync.WaitGroup{}
	for i := 17; i <= 21; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_ = fmt.Sprintf("v1.%d", i)
		}()
	}
	wg.Wait()
}
