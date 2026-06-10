// WEAVE_META
// outcome: race
// concurrency_pattern: channel
// goroutine_count: 3
// expected_nondeterminism: medium
// description: Human-written GoBench bug kernel istio_8144 (race)

package main

import (
	"os"
	"runtime/trace"
	"sync"
	)

type EvictionCallback func()

type callbackRecorder struct {
	callbacks int
}

func (c *callbackRecorder) callback() {
	c.callbacks++
}

type ttlCache struct {
	entries  sync.Map
	callback func()
}

func (c *ttlCache) evicter() {
	c.evictExpired()
}

func (c *ttlCache) evictExpired() {
	c.entries.Range(func(key interface{}, value interface{}) bool {
		c.callback()
		return true
	})
}

func (c *ttlCache) SetWithExpiration(key interface{}, value interface{}) {
	c.entries.Store(key, value)
}

func NewTTLWithCallback(callback EvictionCallback) *ttlCache {
	c := &ttlCache{
		callback: callback,
	}
	go c.evicter()
	return c
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
		defer wg.Done()
		c := &callbackRecorder{callbacks: 0}
		ttl := NewTTLWithCallback(c.callback)
		ttl.SetWithExpiration(1, 1)
		if c.callbacks != 1 {
		}
	}()
	wg.Wait()
}
