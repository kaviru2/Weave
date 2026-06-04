// WEAVE_META
// outcome: success
// concurrency_pattern: mutex
// goroutine_count: 5
// expected_nondeterminism: medium
// description: four goroutines increment a shared counter protected by sync.Mutex, main prints final value.

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

	var mu sync.Mutex
	counter := 0
	var wg sync.WaitGroup

	for i := 0; i < 4; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 5; j++ {
				mu.Lock()
				counter++
				mu.Unlock()
			}
		}()
	}

	wg.Wait()
	fmt.Println(counter)
}
