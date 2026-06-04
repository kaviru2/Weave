// WEAVE_META
// outcome: success
// concurrency_pattern: channel
// goroutine_count: 2
// expected_nondeterminism: low
// description: buffered channel (cap=1) prevents goroutine leak on timeout; this is the fixed version of 06_channel_select (Kubernetes finishReq fix, Tu et al. ASPLOS'19).

package main

import (
	"fmt"
	"os"
	"runtime/trace"
	"time"
)

// fastWork completes well within the timeout.
func fastWork() int {
	time.Sleep(1 * time.Millisecond)
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

	// FIX: buffered channel with cap=1 ensures the child goroutine can always send
	// even if the parent has already returned via timeout. No goroutine is leaked.
	ch := make(chan int, 1)
	go func() {
		result := fastWork()
		ch <- result // never blocks — buffer absorbs the send if parent timed out
	}()

	select {
	case result := <-ch:
		fmt.Println("got:", result)
	case <-time.After(50 * time.Millisecond):
		fmt.Println("timeout")
	}
}
