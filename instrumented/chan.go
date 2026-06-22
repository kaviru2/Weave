package instrumented

import "sync"

// WeaveChan is an instrumented channel wrapper. It behaves exactly like a Go channel
// of the given capacity but emits trace.Log events (category "weave-sync") on every
// blocking operation so the tracer can link GoUnblock events to their causal channel.
//
// Prototype limitations:
//   - select over WeaveChan is not supported; use Recv/Send methods directly.
//   - qcount tracking is approximate for buffered channels: a check-then-act race can
//     produce a spurious chan_send_block or chan_recv_block event. Acceptable for the
//     A/B training-signal experiment.
type WeaveChan[T any] struct {
	id       string
	ch       chan T
	dataqsiz int

	mu     sync.Mutex
	qcount int // approximate items in buffer (always 0 for unbuffered)
}

// NewChan creates an instrumented channel with the given buffer capacity (0 = unbuffered).
func NewChan[T any](capacity int) *WeaveChan[T] {
	id := newID("ch")
	wc := &WeaveChan[T]{
		id:       id,
		ch:       make(chan T, capacity),
		dataqsiz: capacity,
	}
	emit(SyncPayload{Kind: "chan_create", ChanID: id, DataQSiz: capacity, GoID: curGoid()})
	return wc
}

// Send sends v on the channel. Emits chan_send_block before blocking (unbuffered or
// buffer full) and chan_send_done after the value is accepted by the runtime.
func (wc *WeaveChan[T]) Send(v T) {
	gid := curGoid()

	wc.mu.Lock()
	willBlock := wc.dataqsiz == 0 || wc.qcount >= wc.dataqsiz
	qbefore := wc.qcount
	wc.mu.Unlock()

	if willBlock {
		emit(SyncPayload{Kind: "chan_send_block", ChanID: wc.id, QCount: qbefore, DataQSiz: wc.dataqsiz, GoID: gid})
	}

	wc.ch <- v

	wc.mu.Lock()
	if wc.dataqsiz > 0 {
		wc.qcount++
	}
	qafter := wc.qcount
	wc.mu.Unlock()

	emit(SyncPayload{Kind: "chan_send_done", ChanID: wc.id, QCount: qafter, DataQSiz: wc.dataqsiz, GoID: gid})
}

// Recv receives a value from the channel. Emits chan_recv_block before blocking
// and chan_recv_done after the value is received.
// Returns (zero, false) when the channel is closed and drained.
func (wc *WeaveChan[T]) Recv() (T, bool) {
	gid := curGoid()

	wc.mu.Lock()
	willBlock := wc.qcount == 0
	qbefore := wc.qcount
	wc.mu.Unlock()

	if willBlock {
		emit(SyncPayload{Kind: "chan_recv_block", ChanID: wc.id, QCount: qbefore, DataQSiz: wc.dataqsiz, GoID: gid})
	}

	v, ok := <-wc.ch

	wc.mu.Lock()
	if wc.dataqsiz > 0 && wc.qcount > 0 {
		wc.qcount--
	}
	qafter := wc.qcount
	wc.mu.Unlock()

	emit(SyncPayload{Kind: "chan_recv_done", ChanID: wc.id, QCount: qafter, DataQSiz: wc.dataqsiz, GoID: gid})
	return v, ok
}

// Close closes the underlying channel and emits a chan_close event.
func (wc *WeaveChan[T]) Close() {
	emit(SyncPayload{Kind: "chan_close", ChanID: wc.id, GoID: curGoid()})
	close(wc.ch)
}
