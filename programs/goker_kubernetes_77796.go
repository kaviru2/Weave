// WEAVE_META
// outcome: race
// concurrency_pattern: mutex
// goroutine_count: 3
// expected_nondeterminism: medium
// description: Human-written GoBench bug kernel kubernetes_77796 (race)

package main

import (
	"os"
	"runtime/trace"
	"sync"
		"time"
)

type cacheWatcher int

type Cacher struct {
	sync.RWMutex
	watcherBuffer []*cacheWatcher
}

func (c *Cacher) startDispatching() {
	c.Lock()
	defer c.Unlock()

	c.watcherBuffer = c.watcherBuffer[:0]
}

func (c *Cacher) dispatchEvent() {
	c.startDispatching()
	for _ = range c.watcherBuffer {
	}
}

func (c *Cacher) dispatchEvents() {
	c.dispatchEvent()
}

func NewCacherFromConfig() *Cacher {
	cacher := &Cacher{}
	go cacher.dispatchEvents()
	return cacher
}

func newTestCacher() *Cacher {
	return NewCacherFromConfig()
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

	cacher := newTestCacher()
	for i := 0; i < 3; i++ {
		go func() {
			cacher.dispatchEvent()
		}()
		time.Sleep(10 * time.Millisecond)
	}
}
