// WEAVE_META
// outcome: success
// concurrency_pattern: mutex
// goroutine_count: 4
// expected_nondeterminism: medium
// description: sync.Once ensures a channel is closed exactly once despite three concurrent goroutines racing to close it; implements the fix from Docker#24007 (Tu et al. ASPLOS'19).

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

	ch := make(chan struct{})
	var once sync.Once
	// FIX (Docker#24007): wrap close() in Once.Do so only the first caller closes.
	// Without Once, multiple goroutines calling close(ch) simultaneously panics.
	closeOnce := func() { once.Do(func() { close(ch) }) }

	var wg sync.WaitGroup
	for i := 0; i < 3; i++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			closeOnce()
			fmt.Println("closed by goroutine", id)
		}(i)
	}

	<-ch
	wg.Wait()
	fmt.Println("channel closed exactly once")
}
