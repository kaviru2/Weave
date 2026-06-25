// WEAVE_META
// outcome: success
// concurrency_pattern: channel
// goroutine_count: 4
// expected_nondeterminism: low
// description: Phase-21 instrumented variant of gen_025_prodcons (P=2, Cap=0).
// WeaveChan records send_waiters/recv_waiters at each blocking handoff.

package main

import (
	"fmt"
	"os"
	"runtime/trace"
	"sync"
	"time"
	"weave/instrumented"
)

func producer(id int, ch *instrumented.WeaveChan[int], wg *sync.WaitGroup) {
	defer wg.Done()
	for i := 0; i < 3; i++ {
		ch.Send(id*10 + i)
		time.Sleep(time.Millisecond * 1)
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

	ch := instrumented.NewChan[int](0)
	var pwg sync.WaitGroup
	var cwg sync.WaitGroup

	for p := 1; p <= 2; p++ {
		pwg.Add(1)
		go producer(p, ch, &pwg)
	}

	cwg.Add(1)
	go func() {
		defer cwg.Done()
		for {
			val, ok := ch.Recv()
			if !ok {
				break
			}
			_ = val
		}
	}()

	go func() {
		pwg.Wait()
		ch.Close()
	}()

	done := make(chan struct{})
	go func() {
		cwg.Wait()
		close(done)
	}()

	select {
	case <-done:
		fmt.Println("success")
	case <-time.After(200 * time.Millisecond):
		fmt.Println("timeout")
	}
}
