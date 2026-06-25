// WEAVE_META
// outcome: blocking
// concurrency_pattern: mutex
// goroutine_count: 1
// expected_nondeterminism: medium
// description: Auto-extracted GoBench bug kernel moby_30408 (blocking)

package main

import (
	"errors"
	"sync"
	"testing"

	"os"
	"runtime/trace"
)

type Manifest struct {
	Implements []string
}

type Plugin struct {
	activateWait *sync.Cond
	activateErr  error
	Manifest     *Manifest
}

func (p *Plugin) waitActive() error {
	p.activateWait.L.Lock()
	for !p.activated() {
		p.activateWait.Wait()
	}
	p.activateWait.L.Unlock()
	return p.activateErr
}

func (p *Plugin) activated() bool {
	return p.Manifest != nil
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
	p.activateErr = errors.New("some junk happened")

	testActive(p)
}
