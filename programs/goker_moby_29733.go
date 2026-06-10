// WEAVE_META
// outcome: leak
// concurrency_pattern: mutex
// goroutine_count: 3
// expected_nondeterminism: medium
// description: Human-written GoBench bug kernel moby_29733 (leak)

package main

import (
	"os"
	"runtime/trace"
	"sync"
	)

type Plugin struct {
	activated    bool
	activateWait *sync.Cond
}

type plugins struct {
	sync.Mutex
	plugins map[int]*Plugin
}

func (p *Plugin) waitActive() {
	p.activateWait.L.Lock()
	for !p.activated {
		p.activateWait.Wait()
	}
	p.activateWait.L.Unlock()
}

type extpointHandlers struct {
	sync.RWMutex
	extpointHandlers map[int]struct{}
}

var (
	storage  = plugins{plugins: make(map[int]*Plugin)}
	handlers = extpointHandlers{extpointHandlers: make(map[int]struct{})}
)

func Handle() {
	handlers.Lock()
	for _, p := range storage.plugins {
		p.activated = false
	}
	handlers.Unlock()
}

func testActive(p *Plugin) {
	done := make(chan struct{})
	go func() {
		p.waitActive()
		close(done)
	}()
	<-done
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

	p := &Plugin{activateWait: sync.NewCond(&sync.Mutex{})}
	storage.plugins[0] = p

	testActive(p)
	Handle()
	testActive(p)
}
