// WEAVE_META
// outcome: success
// concurrency_pattern: mutex
// goroutine_count: 4
// expected_nondeterminism: high
// description: Concurrent map access with W=3, race_bug=False

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

	var mu sync.Mutex
	_ = mu // prevent declared and not used error
	sharedMap := make(map[int]int)
	var wg sync.WaitGroup

	for w := 0; w < 3; w++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			for i := 0; i < 5; i++ {
				mu.Lock()
				sharedMap[id] = id * i
				mu.Unlock()
				time.Sleep(time.Microsecond * 50)
			}
		}(w)
	}

	wg.Wait()
	fmt.Println("completed map writes, length:", len(sharedMap))
}
