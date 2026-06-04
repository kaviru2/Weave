package tracer

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// RunProgram compiles and executes a Go source file with runtime tracing and the race
// detector enabled. It passes the trace output path via the WEAVE_TRACE_FILE environment
// variable — the program is expected to honour this variable by calling runtime/trace.Start.
//
// The function first builds the binary into outputDir, then runs it. Building separately
// means that context cancellation kills the actual program binary (not a go-run wrapper),
// so timeouts work correctly for deadlocked programs.
//
// The provided context controls the execution deadline. When the context is cancelled
// (e.g. due to a timeout), the process is killed and RunResult.TimedOut is set to true.
// This is the expected behaviour for deadlocked programs.
func RunProgram(ctx context.Context, sourceFile, outputDir string) (*RunResult, error) {
	if err := os.MkdirAll(outputDir, 0o755); err != nil {
		return nil, fmt.Errorf("create output dir %s: %w", outputDir, err)
	}

	base := filepath.Base(sourceFile)
	name := strings.TrimSuffix(base, filepath.Ext(base))
	traceFile := filepath.Join(outputDir, name+".trace")
	binaryPath := filepath.Join(outputDir, name)

	// Build the binary first (outside the deadline context — build errors are setup errors,
	// not program errors). Race detector is enabled at build time.
	buildCmd := exec.Command("go", "build", "-race", "-o", binaryPath, sourceFile)
	if out, err := buildCmd.CombinedOutput(); err != nil {
		return nil, fmt.Errorf("build %s: %w\n%s", sourceFile, err, strings.TrimSpace(string(out)))
	}

	// Run the compiled binary under the caller's context so deadlock timeouts fire correctly.
	cmd := exec.CommandContext(ctx, binaryPath)
	cmd.Env = append(os.Environ(), "WEAVE_TRACE_FILE="+traceFile)

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	runErr := cmd.Run()

	exitCode := 0
	timedOut := false

	if runErr != nil {
		if ctx.Err() != nil {
			// Context was cancelled or deadline exceeded — treat as timeout.
			timedOut = true
			exitCode = -1
		} else if exitErr, ok := runErr.(*exec.ExitError); ok {
			// Program exited with a non-zero code (e.g. deadlock detected by runtime,
			// race detected, or explicit os.Exit). This is expected for some test programs.
			exitCode = exitErr.ExitCode()
		} else {
			return nil, fmt.Errorf("run %s: %w", sourceFile, runErr)
		}
	}

	return &RunResult{
		TraceFile:  traceFile,
		RaceOutput: stderr.String(),
		ExitCode:   exitCode,
		TimedOut:   timedOut,
		Stdout:     stdout.String(),
		Stderr:     stderr.String(),
	}, nil
}
