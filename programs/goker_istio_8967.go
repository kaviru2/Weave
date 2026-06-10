// WEAVE_META
// outcome: race
// concurrency_pattern: select
// goroutine_count: 3
// expected_nondeterminism: medium
// description: Human-written GoBench bug kernel istio_8967 (race)

package main

import (
	"os"
	"runtime/trace"
	"sync"
		"time"
)

type Source interface {
	Start()
	Stop()
}

type fsSource struct {
	donec chan struct{}
}

func (s *fsSource) Start() {
	go func() {
		for {
			select {
			case <-s.donec:
				return
			}
		}
	}()
}

func (s *fsSource) Stop() {
	close(s.donec)
	s.donec = nil
}

func newFsSource() *fsSource {
	return &fsSource{
		donec: make(chan struct{}),
	}
}

func New() Source {
	return newFsSource()
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
		s := New()
		s.Start()
		s.Stop()
		time.Sleep(5 * time.Millisecond)
	}()
	wg.Wait()
}
