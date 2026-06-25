// WEAVE_META
// outcome: nonblocking
// concurrency_pattern: mutex
// goroutine_count: 1
// expected_nondeterminism: medium
// description: Auto-extracted GoBench bug kernel moby_22941 (nonblocking)

package main

import (
	"sync"
	"testing"
	"time"

	"os"
	"runtime/trace"
)

type Conn interface {
	Write(b []byte)
}

type pipe struct {
	wrMu sync.Mutex
}

func (p *pipe) Write(b []byte) {
	p.wrMu.Lock()
	defer p.wrMu.Unlock()
	b = b[1:]
}

func Pipe() Conn {
	return &pipe{}
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

	srv := Pipe()
	tests := [][2][]byte{
		{
			[]byte("GET /foo\nHost: /var/run/docker.sock\nUser-Agent: Docker\r\n\r\n"),
			[]byte("GET /foo\nHost: \r\nConnection: close\r\nUser-Agent: Docker\r\n\r\n"),
		},
		{
			[]byte("GET /foo\nHost: /var/run/docker.sock\nUser-Agent: Docker\nFoo: Bar\r\n"),
			[]byte("GET /foo\nHost: \r\nConnection: close\r\nUser-Agent: Docker\nFoo: Bar\r\n"),
		},
	}
	for _, pair := range tests {
		go func() {
			srv.Write(pair[0])
		}()
	}
	time.Sleep(10 * time.Millisecond)
}
