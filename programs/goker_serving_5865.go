// WEAVE_META
// outcome: race
// concurrency_pattern: mutex
// goroutine_count: 3
// expected_nondeterminism: medium
// description: Human-written GoBench bug kernel serving_5865 (race)

package main

import (
	"os"
	"runtime/trace"
	"sync"
	)

type revisionWatcher struct {
	destsCh chan struct{}
}

func (rw *revisionWatcher) run() {
	defer close(rw.destsCh)
}

type revisionBackendsManager struct {
	revisionWatchersMux sync.RWMutex
}

func newRevisionWatcher(destsCh chan struct{}) *revisionWatcher {
	return &revisionWatcher{destsCh: destsCh}
}

func (rbm *revisionBackendsManager) endpointsUpdated() {
	rw := rbm.getOrCreateRevisionWatcher()
	rw.destsCh <- struct{}{}
}

func (rbm *revisionBackendsManager) getOrCreateRevisionWatcher() *revisionWatcher {
	rbm.revisionWatchersMux.Lock()
	defer rbm.revisionWatchersMux.Unlock()

	destsCh := make(chan struct{})
	rw := newRevisionWatcher(destsCh)
	go rw.run()

	return rw
}

func newRevisionBackendsManagerWithProbeFrequency() *revisionBackendsManager {
	rbm := &revisionBackendsManager{}
	return rbm
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

	rbm := newRevisionBackendsManagerWithProbeFrequency()

	// Simplified code in the RealTestSuite
	func() {
		rbm.endpointsUpdated()
	}()
}
