package tracer

import (
	"context"
	"os"
	"testing"
	"time"
)

// TestRunProgram_ProducesTraceFile verifies that running a well-behaved program
// produces a non-empty trace file at the expected path.
func TestRunProgram_ProducesTraceFile(t *testing.T) {
	ctx := context.Background()
	result, err := RunProgram(ctx, "testdata/simple.go", t.TempDir())
	if err != nil {
		t.Fatalf("RunProgram: %v", err)
	}

	if result.TimedOut {
		t.Fatal("expected program to complete, got timeout")
	}
	if result.ExitCode != 0 {
		t.Fatalf("expected exit code 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
	}
	if result.TraceFile == "" {
		t.Fatal("TraceFile path is empty")
	}

	info, err := os.Stat(result.TraceFile)
	if err != nil {
		t.Fatalf("trace file not found at %s: %v", result.TraceFile, err)
	}
	if info.Size() == 0 {
		t.Fatalf("trace file is empty: %s", result.TraceFile)
	}
}

// TestRunProgram_TimedOut verifies that a program that blocks forever is killed
// after the context deadline and RunResult correctly reports TimedOut.
func TestRunProgram_TimedOut(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 500*time.Millisecond)
	defer cancel()

	result, err := RunProgram(ctx, "testdata/infinite.go", t.TempDir())
	if err != nil {
		t.Fatalf("RunProgram: %v", err)
	}

	if !result.TimedOut {
		t.Fatalf("expected TimedOut=true, got exit code %d", result.ExitCode)
	}
	if result.ExitCode != -1 {
		t.Fatalf("expected exit code -1 for timeout, got %d", result.ExitCode)
	}
}

// TestRunProgram_SourceNotFound verifies that a missing source file returns an error
// rather than a RunResult (because it's a setup problem, not a program failure).
func TestRunProgram_SourceNotFound(t *testing.T) {
	ctx := context.Background()
	_, err := RunProgram(ctx, "testdata/does_not_exist.go", t.TempDir())
	if err == nil {
		t.Fatal("expected error for missing source file, got nil")
	}
}
