// WEAVE_META
// outcome: success
// concurrency_pattern: pipeline
// goroutine_count: 4
// expected_nondeterminism: medium
// description: Phase-21 instrumented variant of gen_003_pipeline (leak_bug=False).
// WeaveChan records send/recv blocking at each stage handoff.

package main

import (
	"fmt"
	"os"
	"runtime/trace"
	"sync"
	"time"
	"weave/instrumented"
)

func stage1(out *instrumented.WeaveChan[int], wg *sync.WaitGroup) {
	defer wg.Done()
	for i := 0; i < 5; i++ {
		out.Send(i)
		time.Sleep(time.Millisecond * 1)
	}
	out.Close()
}

func stage2(in *instrumented.WeaveChan[int], out *instrumented.WeaveChan[int], wg *sync.WaitGroup) {
	defer wg.Done()
	for {
		v, ok := in.Recv()
		if !ok {
			break
		}
		out.Send(v * 2)
		time.Sleep(time.Millisecond * 1)
	}
	out.Close()
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
	ch1 := instrumented.NewChan[int](0)
	ch2 := instrumented.NewChan[int](0)

	wg1.Add(1)
	go stage1(ch1, &wg1)

	wg2.Add(1)
	go stage2(ch1, ch2, &wg2)

	wg3.Add(1)
	go func() {
		defer wg3.Done()
		for {
			_, ok := ch2.Recv()
			if !ok {
				break
			}
		}
	}()

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
