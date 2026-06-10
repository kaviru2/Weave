// WEAVE_META
// outcome: leak
// concurrency_pattern: select
// goroutine_count: 3
// expected_nondeterminism: medium
// description: Human-written GoBench bug kernel grpc_660 (leak)

/*
 * Project: grpc-go
 * Issue or PR  : https://github.com/grpc/grpc-go/pull/660
 * Buggy version: db85417dd0de6cc6f583672c6175a7237e5b5dd2
 * fix commit-id: ceacfbcbc1514e4e677932fd55938ac455d182fb
 * Flaky: 100/100
 * Description:
 *   The parent function could return without draining the done channel.
 */
package main

import (
	"os"
	"runtime/trace"
	"math/rand"
	)

type benchmarkClient struct {
	stop chan bool
}

func (bc *benchmarkClient) doCloseLoopUnary() {
	for {
		done := make(chan bool)
		go func() { // G2
			if rand.Intn(10) > 7 {
				done <- false
				return
			}
			done <- true
		}()
		select {
		case <-bc.stop:
			return
		case <-done:
		}
	}
}

///
/// G1 						G2 				helper goroutine
/// doCloseLoopUnary()
///											bc.stop <- true
/// <-bc.stop
/// return
/// 						done <-
/// ----------------------G2 leak--------------------------
///

func main() {
	if tf := os.Getenv("WEAVE_TRACE_FILE"); tf != "" {
		f, err := os.Create(tf)
		if err == nil {
			if err := trace.Start(f); err == nil {
				defer func() { trace.Stop(); f.Close() }()
			}
		}
	}

	bc := &benchmarkClient{
		stop: make(chan bool),
	}
	go bc.doCloseLoopUnary() // G1
	go func() {              // helper goroutine
		bc.stop <- true
	}()
}
