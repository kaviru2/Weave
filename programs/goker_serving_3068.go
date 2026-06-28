// WEAVE_META
// outcome: nonblocking
// concurrency_pattern: channel
// goroutine_count: 3
// expected_nondeterminism: medium
// description: Auto-extracted GoBench bug kernel serving_3068 (nonblocking)

package main

import (
	"sync"
	"sync/atomic"
	"time"

	"os"
	"runtime/trace"
)

type Interface interface {
	Go(func())
	Wait()
}

type impl struct {
	wg     sync.WaitGroup
	workCh chan func()
	once   sync.Once
}

var _ Interface = (*impl)(nil)

func NewWithCapacity(workers, capacity int) Interface {
	i := &impl{
		workCh: make(chan func(), capacity),
	}

	for idx := 0; idx < workers; idx++ {
		go func() {
			for work := range i.workCh {
				func() {
					defer i.wg.Done()
					work()
				}()
			}
		}()
	}

	return i
}

func (i *impl) Go(w func()) {
	i.wg.Add(1)
	i.workCh <- w
}

func (i *impl) Wait() {
	i.once.Do(func() {
		close(i.workCh)

		go func() {
			i.wg.Wait()
		}()
	})
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

	p := NewWithCapacity(1, 5)
	wg := &sync.WaitGroup{}
	var cntExecuted int32
	const n = 5
	wg.Add(n)
	go func() {
		for i := 0; i < n; i++ {
			p.Go(func() {
				atomic.AddInt32(&cntExecuted, 1)
			})
			time.Sleep(10 * time.Millisecond)
			wg.Done()
		}
	}()
	p.Wait()
	wg.Wait()
	if cntExecuted == n {
		_ = "Not all items were expected to execute"
	}
}
