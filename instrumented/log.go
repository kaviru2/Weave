// Package instrumented provides WeaveChan and WeaveMutex — thin wrappers around
// Go's built-in channel and sync.Mutex that embed synchronisation state into the
// standard runtime/trace scheduler trace via trace.Log calls.
//
// Because log events are written into the same trace file as goroutine scheduler
// events, they share the runtime monotonic clock and can be parsed in sequence by
// tracer.ParseTrace without any clock-synchronisation step.
//
// The JSON payload in each log message mirrors the sidecarEvent fields in
// tracer/sync_merge.go. Category is always "weave-sync".
package instrumented

import (
	"context"
	"encoding/json"
	"runtime"
	"runtime/trace"
	"sync/atomic"
)

// SyncPayload is the JSON body embedded in each trace.Log call.
// It is re-parsed by tracer.ParseTrace when it encounters EventLog events
// with category "weave-sync".
type SyncPayload struct {
	Kind     string `json:"kind"`
	ChanID   string `json:"chan_id,omitempty"`
	MutexID  string `json:"mutex_id,omitempty"`
	GoID     uint64 `json:"goid"`
	QCount   int    `json:"qcount,omitempty"`
	DataQSiz int    `json:"dataqsiz,omitempty"`
	Holder   uint64 `json:"holder,omitempty"`
}

const logCategory = "weave-sync"

// logBg is a permanent background context used for all trace.Log calls.
// Using context.Background() means the log events are not associated with any
// task, which is fine — we only need the timestamp and the message payload.
var logBg = context.Background()

var idSeq atomic.Uint64

func emit(p SyncPayload) {
	b, err := json.Marshal(p)
	if err != nil {
		return
	}
	trace.Log(logBg, logCategory, string(b))
}

func newID(prefix string) string {
	n := idSeq.Add(1)
	digits := [20]byte{}
	i := 20
	for n > 0 {
		i--
		digits[i] = byte('0' + n%10)
		n /= 10
	}
	for 20-i < 4 {
		i--
		digits[i] = '0'
	}
	return prefix + "_" + string(digits[i:])
}

// curGoid reads the current goroutine ID from the runtime stack header.
// This is O(stack capture) — acceptable for prototype instrumentation.
func curGoid() uint64 {
	var buf [32]byte
	n := runtime.Stack(buf[:], false)
	// First line: "goroutine NNN [running]:\n"
	var id uint64
	i := 10 // skip "goroutine "
	for ; i < n && buf[i] >= '0' && buf[i] <= '9'; i++ {
		id = id*10 + uint64(buf[i]-'0')
	}
	return id
}
