// WEAVE_META
// outcome: success
// concurrency_pattern: channel
// goroutine_count: 4
// expected_nondeterminism: low
// description: Producer-consumer queue with P=2, Cap=0, leak_bug=False

package main

import (
	"fmt"
	"os"
	"runtime/trace"
	"sync"
	"time"
)

func producer(id int, ch chan<- int, wg *sync.WaitGroup) {
	defer wg.Done()
	for i := 0; i < 3; i++ {
		ch <- id*10 + i
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

	ch := make(chan int, 0)
	var pwg sync.WaitGroup
	var cwg sync.WaitGroup

	// Start producers
	for p := 1; p <= 2; p++ {
		pwg.Add(1)
		go producer(p, ch, &pwg)
	}

	// Start consumer
	cwg.Add(1)
	go func() {
		defer cwg.Done()
		for val := range ch {
			_ = val
		}
	}()

	// Closer goroutine
	go func() {
		pwg.Wait()
		close(ch)
	}()

	// Monitor
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
