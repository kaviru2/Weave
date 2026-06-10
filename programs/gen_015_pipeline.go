// WEAVE_META
// outcome: leak
// concurrency_pattern: pipeline
// goroutine_count: 4
// expected_nondeterminism: medium
// description: Pipeline pipeline stages stage1 -> stage2 -> stage3, leak_bug=True

package main

import (
	"fmt"
	"os"
	"runtime/trace"
	"sync"
	"time"
)

func stage1(out chan<- int, wg *sync.WaitGroup) {
	defer wg.Done()
	for i := 0; i < 5; i++ {
		out <- i
		time.Sleep(time.Millisecond * 1)
	}
	close(out)
}

func stage2(in <-chan int, out chan<- int, wg *sync.WaitGroup) {
	defer wg.Done()
	for v := range in {
		out <- v * 2
		time.Sleep(time.Millisecond * 1)
	}
	close(out)
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

	var wg1, wg2, wg3 sync.WaitGroup
	ch1 := make(chan int)
	ch2 := make(chan int)

	wg1.Add(1)
	go stage1(ch1, &wg1)

	wg2.Add(1)
	go stage2(ch1, ch2, &wg2)

	wg3.Add(1)
	go func(inCh <-chan int) {
		defer wg3.Done()
			// Bug: exit early after 1 item, leaving stage2 blocked
	val := <-inCh
	_ = val
	}(ch2)

	// Exit harness
	done := make(chan struct{})
	go func() {
		wg1.Wait()
		wg2.Wait()
		wg3.Wait()
		close(done)
	}()

	select {
	case <-done:
		fmt.Println("pipeline done")
	case <-time.After(200 * time.Millisecond):
		fmt.Println("pipeline timeout")
	}
}
