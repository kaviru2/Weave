// WEAVE_META
// outcome: leak
// concurrency_pattern: mutex
// goroutine_count: 3
// expected_nondeterminism: medium
// description: Human-written GoBench bug kernel grpc_795 (leak)

package main

import (
	"os"
	"runtime/trace"
	"sync"
	)

type Server struct {
	mu    sync.Mutex
	drain bool
}

func (s *Server) GracefulStop() {
	s.mu.Lock()
	if s.drain == true {
		s.mu.Lock()
		return
	}
	s.drain = true
} // Missing Unlock

func (s *Server) Serve() {
	s.mu.Lock()
	s.mu.Unlock()
}

func NewServer() *Server {
	return &Server{}
}

type test struct {
	srv *Server
}

func (te *test) startServer() {
	s := NewServer()
	te.srv = s
	go s.Serve()
}

func newTest() *test {
	return &test{}
}

func testServerGracefulStopIdempotent() {
	te := newTest()

	te.startServer()

	for i := 0; i < 3; i++ {
		te.srv.GracefulStop()
	}
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

	testServerGracefulStopIdempotent()
}
