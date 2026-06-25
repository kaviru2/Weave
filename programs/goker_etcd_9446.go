// WEAVE_META
// outcome: nonblocking
// concurrency_pattern: channel
// goroutine_count: 3
// expected_nondeterminism: medium
// description: Auto-extracted GoBench bug kernel etcd_9446 (nonblocking)

package main

import (
	"sync"

	"os"
	"runtime/trace"
)

type txBuffer struct {
	buckets map[string]struct{}
}

func (txb *txBuffer) reset() {
	for k, _ := range txb.buckets {
		delete(txb.buckets, k)
	}
}

type txReadBuffer struct{ txBuffer }

func (txr *txReadBuffer) Range() {
	_ = txr.buckets["1"]
}

type readTx struct {
	buf txReadBuffer
}

func (rt *readTx) reset() {
	rt.buf.reset()
}

func (rt *readTx) UnsafeRange() {
	rt.buf.Range()
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
	wg.Add(3)
	go func() {
		defer wg.Done()
		txn := &readTx{
			buf: txReadBuffer{
				txBuffer{
					buckets: make(map[string]struct{}),
				},
			},
		}
		txn.buf.buckets["1"] = struct{}{}
		go func() {
			defer wg.Done()
			txn.reset()
		}()
		go func() {
			defer wg.Done()
			txn.UnsafeRange()
		}()
	}()
	wg.Wait()
}
