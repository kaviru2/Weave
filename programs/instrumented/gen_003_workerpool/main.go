// WEAVE_META
// outcome: leak
// concurrency_pattern: channel
// goroutine_count: 5
// expected_nondeterminism: medium
// description: Phase-21 instrumented variant of gen_003_workerpool (W=4, J=8, Cap=5, leak_bug=True).
// WeaveChan records recv_waiters when workers block after jobs channel is never closed.

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

	jobs := instrumented.NewChan[int](5)
	var wg sync.WaitGroup

	for w := 1; w <= 4; w++ {
		wg.Add(1)
		go worker(w, jobs, &wg)
	}

	for j := 1; j <= 8; j++ {
		jobs.Send(j)
	}
	// bug: jobs.Close() omitted to cause leak

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
