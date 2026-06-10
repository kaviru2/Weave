// WEAVE_META
// outcome: race
// concurrency_pattern: mutex
// goroutine_count: 3
// expected_nondeterminism: medium
// description: Human-written GoBench bug kernel etcd_8194 (race)

package main

import (
	"os"
	"runtime/trace"
	"sync"
		"time"
)

var leaseRevokeRate = 1000

func testLessorRenewExtendPileup() {
	oldRevokeRate := leaseRevokeRate
	defer func() { leaseRevokeRate = oldRevokeRate }()
	leaseRevokeRate = 10
}

type Lease struct{}

type lessor struct {
	mu    sync.Mutex
	stopC chan struct{}
	doneC chan struct{}
}

func (le *lessor) runLoop() {
	defer close(le.doneC)

	for i := 0; i < 10; i++ {
		var ls []*Lease

		ls = append(ls, &Lease{})

		if len(ls) != 0 {
			// rate limit
			if len(ls) > leaseRevokeRate/2 {
				ls = ls[:leaseRevokeRate/2]
			}
			select {
			case <-le.stopC:
				return
			default:
			}
		}

		select {
		case <-time.After(5 * time.Millisecond):
		case <-le.stopC:
			return
		}
	}
}

func newLessor() *lessor {
	l := &lessor{}
	go l.runLoop()
	return l
}

func testLessorGrant() {
	newLessor()
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
	go func() {
		defer wg.Done()
		testLessorGrant()
	}()
	go func() {
		defer wg.Done()
		testLessorRenewExtendPileup()
	}()
	wg.Wait()
}
