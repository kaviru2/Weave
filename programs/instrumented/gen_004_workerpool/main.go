// WEAVE_META
// outcome: success
// concurrency_pattern: channel
// goroutine_count: 6
// expected_nondeterminism: medium
// description: Phase-21 instrumented variant of gen_004_workerpool (W=5, J=11, Cap=2, leak_bug=False).
// WeaveChan records recv_waiters on jobs channel as workers compete for items.

package main

import (
	"fmt"
	"os"
	"runtime/trace"
	"sync"
	"time"
	"weave/instrumented"
)

func worker(id int, jobs *instrumented.WeaveChan[int], wg *sync.WaitGroup) {
	defer wg.Done()
	for {
		job, ok := jobs.Recv()
		if !ok {
			break
		}
		_ = job
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

	jobs := instrumented.NewChan[int](2)
	var wg sync.WaitGroup

	for w := 1; w <= 5; w++ {
		wg.Add(1)
		go worker(w, jobs, &wg)
	}

	for j := 1; j <= 11; j++ {
		jobs.Send(j)
	}
	jobs.Close()

	done := make(chan struct{})
	go func() {
		wg.Wait()
		close(done)
	}()

	select {
	case <-done:
		fmt.Println("success")
	case <-time.After(250 * time.Millisecond):
		fmt.Println("timeout")
	}
}
