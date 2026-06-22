// demo_phase20 runs the two Phase-20 instrumented programs and prints selected
// snapshots to confirm that Channels and Mutexes maps are now populated.
//
// Usage:
//
//	go run ./cmd/demo_phase20/
//
// The program confirms the RQ1 experimental prerequisite: once a program uses
// WeaveChan/WeaveMutex, every GoBlock/GoUnblock event on a channel has the
// blocked goroutine listed in RecvWaiters or SendWaiters, providing the causal
// linkage the base model could never infer from the scheduler trace alone.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
	"weave/tracer"
)

func main() {
	tmpDir, err := os.MkdirTemp("", "weave-phase20-*")
	if err != nil {
		fatalf("mktemp: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	demos := []struct {
		dir  string
		name string
	}{
		{"programs/instrumented/01_chan", "01_chan (unbuffered channel)"},
		{"programs/instrumented/03_mutex", "03_mutex (mutex contention)"},
	}

	for _, d := range demos {
		fmt.Printf("\n═══ %s ═══\n", d.name)
		runDemo(d.dir, d.name, tmpDir)
	}
}

func runDemo(programDir, name, tmpDir string) {
	safe := filepath.Base(programDir)
	traceFile := filepath.Join(tmpDir, safe+".trace")

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	res, err := tracer.RunDir(ctx, programDir, tmpDir, map[string]string{
		"WEAVE_TRACE_FILE": traceFile,
	})
	if err != nil {
		fatalf("run %s: %v", name, err)
	}
	if res.TimedOut {
		fmt.Println("  [timed out — deadlock program, expected]")
		return
	}

	// ParseTrace now handles EventLog("weave-sync") inline — no separate merge step.
	snapshots, err := tracer.ParseTrace(traceFile)
	if err != nil {
		fatalf("parse trace %s: %v", name, err)
	}

	populated := 0
	goUnblockWithLink := 0
	totalUnblock := 0

	for _, s := range snapshots {
		if len(s.Channels)+len(s.Mutexes) > 0 {
			populated++
		}
		if s.EventType == tracer.GoUnblock {
			totalUnblock++
			if hasWaiterFor(s, s.GoroutineID) {
				goUnblockWithLink++
			}
		}
	}

	fmt.Printf("  snapshots total:              %d\n", len(snapshots))
	fmt.Printf("  snapshots with sync state:    %d / %d\n", populated, len(snapshots))
	fmt.Printf("  GoUnblock events:             %d\n", totalUnblock)
	fmt.Printf("  GoUnblock with causal link:   %d / %d\n", goUnblockWithLink, totalUnblock)

	// Print first snapshot that has a waiter visible.
	for _, s := range snapshots {
		for _, ch := range s.Channels {
			if len(ch.RecvWaiters)+len(ch.SendWaiters) > 0 {
				fmt.Printf("\n  Example — %s at event %d (goroutine %d):\n",
					s.EventType, s.EventID, s.GoroutineID)
				printJSON("    channels", s.Channels)
				printJSON("    mutexes", s.Mutexes)
				return
			}
		}
		for _, mx := range s.Mutexes {
			if mx.Holder != 0 || len(mx.Waiters) > 0 {
				fmt.Printf("\n  Example — %s at event %d (goroutine %d):\n",
					s.EventType, s.EventID, s.GoroutineID)
				printJSON("    channels", s.Channels)
				printJSON("    mutexes", s.Mutexes)
				return
			}
		}
	}
	fmt.Println("  (no snapshot with active waiters found — may need longer trace)")
}

func hasWaiterFor(s tracer.StateSnapshot, goid uint64) bool {
	for _, ch := range s.Channels {
		for _, w := range ch.RecvWaiters {
			if w == goid {
				return true
			}
		}
		for _, w := range ch.SendWaiters {
			if w == goid {
				return true
			}
		}
	}
	for _, mx := range s.Mutexes {
		for _, w := range mx.Waiters {
			if w == goid {
				return true
			}
		}
	}
	return false
}

func printJSON(label string, v any) {
	b, _ := json.MarshalIndent(v, "      ", "  ")
	fmt.Printf("  %s: %s\n", label, b)
}

func fatalf(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "demo_phase20: "+format+"\n", args...)
	os.Exit(1)
}
