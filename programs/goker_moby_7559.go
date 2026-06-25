// WEAVE_META
// outcome: blocking
// concurrency_pattern: mutex
// goroutine_count: 1
// expected_nondeterminism: medium
// description: Auto-extracted GoBench bug kernel moby_7559 (blocking)

/*
 * Project: moby
 * Issue or PR  : https://github.com/moby/moby/pull/7559
 * Buggy version: 64579f51fcb439c36377c0068ccc9a007b368b5a
 * fix commit-id: 6cbb8e070d6c3a66bf48fbe5cbf689557eee23db
 * Flaky: 100/100
 */
package main

import (
	"net"
	"sync"
	"testing"

	"os"
	"runtime/trace"
)

type UDPProxy struct {
	connTrackLock sync.Mutex
}

func (proxy *UDPProxy) Run() {
	for i := 0; i < 2; i++ {
		proxy.connTrackLock.Lock()
		_, err := net.DialUDP("udp", nil, nil)
		if err != nil {
			/// Missing unlock here
			continue
		}
		if i == 0 {
			break
		}
	}
	proxy.connTrackLock.Unlock()
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

	proxy := &UDPProxy{}
	go proxy.Run()
}
