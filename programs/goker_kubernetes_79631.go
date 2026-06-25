// WEAVE_META
// outcome: nonblocking
// concurrency_pattern: mutex
// goroutine_count: 2
// expected_nondeterminism: medium
// description: Auto-extracted GoBench bug kernel kubernetes_79631 (nonblocking)

package main

import (
	"sync"

	"os"
	"runtime/trace"
)

type heapData struct {
	items map[string]struct{}
}

func (h *heapData) Pop() {
	delete(h.items, "1")
}

type Interface interface {
	Pop()
}

func Pop(h Interface) {
	h.Pop()
}

type Heap struct {
	data *heapData
}

func (h *Heap) Pop() {
	Pop(h.data)
}

func (h *Heap) Get() {
	h.GetByKey()
}

func (h *Heap) GetByKey() {
	_ = h.data.items["1"]
}

func NewWithRecorder() *Heap {
	return &Heap{
		data: &heapData{
			items: make(map[string]struct{}),
		},
	}
}

type PriorityQueue struct {
	stop        chan struct{}
	lock        sync.RWMutex
	podBackoffQ *Heap
}

func (p *PriorityQueue) flushBackoffQCompleted() {
	p.lock.Lock()
	defer p.lock.Unlock()
	p.podBackoffQ.Pop()

}

func NewPriorityQueue() *PriorityQueue {
	return NewPriorityQueueWithClock()
}

func NewPriorityQueueWithClock() *PriorityQueue {
	pg := &PriorityQueue{
		stop:        make(chan struct{}),
		podBackoffQ: NewWithRecorder(),
	}
	pg.run()
	return pg
}

func (p *PriorityQueue) run() {
	go Until(p.flushBackoffQCompleted, p.stop)
}

func BackoffUntil(f func(), stopCh <-chan struct{}) {
	for {
		select {
		case <-stopCh:
			return
		default:
		}

		func() {
			f()
		}()

		select {
		case <-stopCh:
			return
		}
	}
}

func JitterUntil(f func(), stopCh <-chan struct{}) {
	BackoffUntil(f, stopCh)
}

func Until(f func(), stopCh <-chan struct{}) {
	JitterUntil(f, stopCh)
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

	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		wg.Done()
		q := NewPriorityQueue()
		q.podBackoffQ.Get()
	}()
	wg.Wait()
}
