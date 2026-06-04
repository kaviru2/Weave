// WEAVE_META
// outcome: leak
// concurrency_pattern: select
// goroutine_count: 2
// expected_nondeterminism: low
// description: unbuffered channel plus select-timeout leaks child goroutine forever; reproduces Kubernetes finishReq bug (Tu et al. ASPLOS'19).

package main

import (
	"fmt"
	"os"
	"runtime/trace"
	"time"
)

// slowWork simulates a task that takes longer than the caller's timeout.
func slowWork() int {
	time.Sleep(20 * time.Millisecond)
	return 42
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

	// BUG (Kubernetes finishReq): ch is unbuffered. The child goroutine blocks on
	// ch <- result after main has already returned via the timeout case. The goroutine
	// is now permanently blocked with no receiver — it leaks.
	ch := make(chan int)
	go func() {
		result := slowWork()
		ch <- result // blocks forever once the timeout case fires
	}()

	select {
	case result := <-ch:
		fmt.Println("got:", result)
	case <-time.After(1 * time.Millisecond):
		fmt.Println("timeout")
	}

	// Sleep so the trace captures the goroutine in GoWaiting state before main exits.
	time.Sleep(50 * time.Millisecond)
}
