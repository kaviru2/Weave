// WEAVE_META
// outcome: race
// concurrency_pattern: channel
// goroutine_count: 3
// expected_nondeterminism: medium
// description: Human-written GoBench bug kernel kubernetes_80284 (race)

package main

import (
	"os"
	"runtime/trace"
	"sync"
	)

type Dialer struct{}

func (d *Dialer) CloseAll() {}

func NewDialer() *Dialer {
	return &Dialer{}
}

type Authenticator struct {
	onRotate func()
}

func (a *Authenticator) UpdateTransportConfig() {
	d := NewDialer()
	a.onRotate = d.CloseAll
}

func newAuthenticator() *Authenticator {
	return &Authenticator{}
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
	wg.Add(2)
	a := newAuthenticator()
	for i := 0; i < 2; i++ {
		go func() {
			defer wg.Done()
			a.UpdateTransportConfig()
		}()
	}
	wg.Wait()
}
