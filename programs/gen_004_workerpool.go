// WEAVE_META
// outcome: success
// concurrency_pattern: channel
// goroutine_count: 6
// expected_nondeterminism: medium
// description: Randomized worker pool with W=5, J=11, Cap=2, leak_bug=False

package main

import (
	"fmt"
	"os"
	"runtime/trace"
	"sync"
	"time"
)

func worker(id int, jobs <-chan int, wg *sync.WaitGroup) {
	defer wg.Done()
	for job := range jobs {
		_ = job
		// Simulate processing workload
		time.Sleep(time.Millisecond * 2)
	}
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

	jobs := make(chan int, 2)
	var wg sync.WaitGroup

	// Start workers
	for w := 1; w <= 5; w++ {
		wg.Add(1)
		go worker(w, jobs, &wg)
	}

	// Send jobs
	for j := 1; j <= 11; j++ {
		jobs <- j
	}
	close(jobs)

	// Wait for completion (will block forever if jobs channel is not closed)
	// WaitGroup placement is correct, but leak occurs inside worker range.
	// To ensure program exits in leak case for trace collection, we use a timeout.
	
	// Create channel to notify main
	done := make(chan struct{})
	go func() {
		wg.Wait()
		close(done)
	}()

	select {
	case <-done:
		fmt.Println("success")
	case <-time.After(250 * time.Millisecond):
		// If leaked, we exit cleanly so runtime trace stops and we save it.
		fmt.Println("timeout")
	}
}
