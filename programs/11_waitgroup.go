// WEAVE_META
// outcome: success
// concurrency_pattern: waitgroup
// goroutine_count: 6
// expected_nondeterminism: medium
// description: five goroutines do work and call Done(); Wait() is called outside the loop — the correct pattern fixing Docker#25384 (Tu et al. ASPLOS'19).

package main

import (
	"fmt"
	"os"
	"runtime/trace"
	"sync"
	"time"
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

	var wg sync.WaitGroup
	wg.Add(5)

	// FIX (Docker#25384): all goroutines are spawned first, then Wait() is called
	// once outside the loop. Every goroutine can reach Done() without contention.
	for i := 0; i < 5; i++ {
		go func(id int) {
			defer wg.Done()
			time.Sleep(2 * time.Millisecond)
			fmt.Println("done:", id)
		}(i)
	}

	wg.Wait()
	fmt.Println("all done")
}
