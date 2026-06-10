// WEAVE_META
// outcome: leak
// concurrency_pattern: select
// goroutine_count: 3
// expected_nondeterminism: medium
// description: Human-written GoBench bug kernel cockroach_2448 (leak)

package main

import (
	"os"
	"runtime/trace"
		"time"
)

type Stopper struct {
	Done chan bool
}

func (s *Stopper) ShouldStop() <-chan bool {
	return s.Done
}

type EventMembershipChangeCommitted struct {
	Callback func()
}
type MultiRaft struct {
	stopper      *Stopper
	Events       chan interface{}
	callbackChan chan func()
}

// sendEvent can be invoked many times
func (m *MultiRaft) sendEvent(event interface{}) {
	/// FIX:
	/// Let event append a event queue instead of pending here
	select {
	case m.Events <- event: // Waiting for events consumption
	case <-m.stopper.ShouldStop():
	}
}

type state struct {
	*MultiRaft
}

func (s *state) start() {
	for {
		select {
		case <-s.stopper.ShouldStop():
			return
		case cb := <-s.callbackChan:
			cb()
		default:
			s.handleWriteResponse()
		}
	}
}
func (s *state) handleWriteResponse() {
	s.processCommittedEntry()
}

func (s *state) processCommittedEntry() {
	s.sendEvent(&EventMembershipChangeCommitted{
		Callback: func() {
			select {
			case s.callbackChan <- func() { // Waiting for callbackChan consumption
				time.Sleep(time.Nanosecond)
			}:
			case <-s.stopper.ShouldStop():
			}
		},
	})
}

type Store struct {
	multiraft *MultiRaft
}

func (s *Store) processRaft() {
	for {
		select {
		case e := <-s.multiraft.Events:
			var callback func()
			switch e := e.(type) {
			case *EventMembershipChangeCommitted:
				callback = e.Callback
				if callback != nil {
					callback() // Waiting for callbackChan consumption
				}
			}
		case <-s.multiraft.stopper.ShouldStop():
			return
		}
	}
}

func NewStoreAndState() (*Store, *state) {
	stopper := &Stopper{
		Done: make(chan bool),
	}
	mltrft := &MultiRaft{
		stopper:      stopper,
		Events:       make(chan interface{}),
		callbackChan: make(chan func()),
	}
	st := &state{mltrft}
	s := &Store{mltrft}
	return s, st
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

	s, st := NewStoreAndState()
	go s.processRaft() // G1
	go st.start()      // G2
}
