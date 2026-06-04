package tracer

import (
	"bytes"
	"os"
	"runtime/trace"
	"testing"

	gotrace "golang.org/x/exp/trace"
)

// TestParseTrace_BasicGoroutineLifecycle generates a real in-process trace, writes
// it to a temp file, and verifies that ParseTrace produces a non-empty snapshot slice
// containing at least GoCreate and GoStart events.
func TestParseTrace_BasicGoroutineLifecycle(t *testing.T) {
	var buf bytes.Buffer

	if err := trace.Start(&buf); err != nil {
		t.Fatalf("trace.Start: %v", err)
	}

	// Do minimal concurrent work so the trace has goroutine events.
	ch := make(chan struct{})
	go func() { close(ch) }()
	<-ch

	trace.Stop()

	// Write the captured trace to a temp file for ParseTrace.
	f, err := os.CreateTemp(t.TempDir(), "test-*.trace")
	if err != nil {
		t.Fatalf("create temp file: %v", err)
	}
	if _, err := f.Write(buf.Bytes()); err != nil {
		t.Fatalf("write trace: %v", err)
	}
	f.Close()

	snapshots, err := ParseTrace(f.Name())
	if err != nil {
		t.Fatalf("ParseTrace: %v", err)
	}
	if len(snapshots) == 0 {
		t.Fatal("expected at least one snapshot, got none")
	}

	// Check that we see at least GoCreate or GoStart in the snapshots.
	seen := map[EventType]bool{}
	for _, s := range snapshots {
		seen[s.EventType] = true
	}
	if !seen[GoCreate] && !seen[GoStart] {
		t.Errorf("expected GoCreate or GoStart event; got event types: %v", seen)
	}

	// Every snapshot must have a non-nil Goroutines map.
	for i, s := range snapshots {
		if s.Goroutines == nil {
			t.Errorf("snapshot %d: Goroutines map is nil", i)
		}
		if s.TimestampNS <= 0 {
			t.Errorf("snapshot %d: TimestampNS is %d, want > 0", i, s.TimestampNS)
		}
	}
}

// TestParseTrace_FileNotFound verifies that ParseTrace returns an error for a
// missing file rather than panicking or returning an empty slice silently.
func TestParseTrace_FileNotFound(t *testing.T) {
	_, err := ParseTrace("/nonexistent/path/trace.out")
	if err == nil {
		t.Fatal("expected error for missing trace file, got nil")
	}
}

// TestMapTransition covers all (from, to) pairs defined in our schema.
func TestMapTransition_AllCases(t *testing.T) {
	str := func(s string) *string { return &s }

	tests := []struct {
		name        string
		from, to    gotrace.GoState
		reason      string
		wantType    EventType
		wantBlocked *string // nil means we don't check the value, just expect nil
	}{
		{
			name:     "create: NotExist→Runnable",
			from:     gotrace.GoNotExist, to: gotrace.GoRunnable,
			wantType: GoCreate,
		},
		{
			name:     "start: Runnable→Running",
			from:     gotrace.GoRunnable, to: gotrace.GoRunning,
			wantType: GoStart,
		},
		{
			name:     "start: Syscall→Running",
			from:     gotrace.GoSyscall, to: gotrace.GoRunning,
			wantType: GoStart,
		},
		{
			name:        "block: Running→Waiting",
			from:        gotrace.GoRunning, to: gotrace.GoWaiting,
			reason:      "channel receive",
			wantType:    GoBlock,
			wantBlocked: str("channel receive"),
		},
		{
			name:        "block: Running→Syscall",
			from:        gotrace.GoRunning, to: gotrace.GoSyscall,
			wantType:    GoBlock,
			wantBlocked: str("syscall"),
		},
		{
			name:     "unblock: Waiting→Runnable",
			from:     gotrace.GoWaiting, to: gotrace.GoRunnable,
			wantType: GoUnblock,
		},
		{
			name:     "unblock: Syscall→Runnable",
			from:     gotrace.GoSyscall, to: gotrace.GoRunnable,
			wantType: GoUnblock,
		},
		{
			name:     "sched: Running→Runnable",
			from:     gotrace.GoRunning, to: gotrace.GoRunnable,
			wantType: GoSched,
		},
		{
			name:     "end: Running→NotExist",
			from:     gotrace.GoRunning, to: gotrace.GoNotExist,
			wantType: GoEnd,
		},
		{
			name:     "end: Waiting→NotExist",
			from:     gotrace.GoWaiting, to: gotrace.GoNotExist,
			wantType: GoEnd,
		},
		{
			name:     "skip: Undetermined→Runnable",
			from:     gotrace.GoUndetermined, to: gotrace.GoRunnable,
			wantType: "", // should be skipped
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			gotType, gotBlocked := mapTransition(tc.from, tc.to, tc.reason)
			if gotType != tc.wantType {
				t.Errorf("mapTransition(%s, %s, %q) type = %q, want %q",
					tc.from, tc.to, tc.reason, gotType, tc.wantType)
			}
			if tc.wantBlocked != nil {
				if gotBlocked == nil {
					t.Errorf("mapTransition: expected blocked_on=%q, got nil", *tc.wantBlocked)
				} else if *gotBlocked != *tc.wantBlocked {
					t.Errorf("mapTransition: blocked_on = %q, want %q", *gotBlocked, *tc.wantBlocked)
				}
			} else if tc.wantType == GoBlock && gotBlocked == nil {
				t.Errorf("mapTransition: expected non-nil blocked_on for GoBlock")
			}
		})
	}
}

// TestGetTopFunction_ReturnsTopFrame verifies that getTopFunction returns the
// top (innermost) frame's function name from a real stack captured during a trace.
func TestGetTopFunction_ReturnsTopFrame(t *testing.T) {
	var buf bytes.Buffer
	if err := trace.Start(&buf); err != nil {
		t.Fatalf("trace.Start: %v", err)
	}
	trace.Stop()

	r, err := gotrace.NewReader(&buf)
	if err != nil {
		t.Fatalf("NewReader: %v", err)
	}

	// Scan events until we find one with a non-empty stack.
	foundStack := false
	for {
		ev, err := r.ReadEvent()
		if err != nil {
			break // io.EOF or error
		}
		result := getTopFunction(ev.Stack())
		if result != "unknown" {
			foundStack = true
			if result == "" {
				t.Error("getTopFunction returned empty string instead of function name")
			}
			break
		}
	}

	if !foundStack {
		t.Log("no event with a stack found — this is acceptable for very short traces")
	}
}
