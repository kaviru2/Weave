// WEAVE_META
// outcome: leak
// concurrency_pattern: mutex
// goroutine_count: 2
// expected_nondeterminism: none
// description: main acquires a mutex lock then exits without unlocking; a worker goroutine attempting Lock() is permanently blocked in GoWaiting when the program ends.

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

	// Main acquires the lock and never releases it.
	mu.Lock()
	fmt.Println("main holds the lock")

	// Worker tries to acquire the same lock — blocks immediately in GoWaiting
	// because main never calls mu.Unlock().
	go func() {
		mu.Lock() // blocks here forever
		fmt.Println("worker acquired lock")
		mu.Unlock()
	}()

	// Sleep so the trace captures the worker goroutine in GoWaiting before main exits.
	// main exits without mu.Unlock() — goroutine leaks.
	time.Sleep(50 * time.Millisecond)
}
