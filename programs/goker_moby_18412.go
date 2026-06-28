// WEAVE_META
// outcome: nonblocking
// concurrency_pattern: channel
// goroutine_count: 1
// expected_nondeterminism: medium
// description: Auto-extracted GoBench bug kernel moby_18412 (nonblocking)

package main

import (
	"bytes"
	"errors"
	"fmt"
	"os/exec"
	"time"

	"os"
	"runtime/trace"
)

func RunCommandWithOutputForDuration(cmd *exec.Cmd, duration time.Duration) (output string, exitCode int, timedOut bool, err error) {
	var outputBuffer bytes.Buffer
	if cmd.Stdout != nil {
		err = errors.New("cmd.Stdout already set")
		return
	}
	cmd.Stdout = &outputBuffer

	if cmd.Stderr != nil {
		err = errors.New("cmd.Stderr already set")
		return
	}
	cmd.Stderr = &outputBuffer

	done := make(chan error)

	// Start the command in the main thread..
	err = cmd.Start()
	if err != nil {
		err = fmt.Errorf("Fail to start command %v : %v", cmd, err)
	}

	go func() {
		// And wait for it to exit in the goroutine :)
		exitErr := cmd.Wait()
		exitCode = 1
		done <- exitErr
	}()

	select {
	case <-time.After(duration):
		killErr := cmd.Process.Kill()
		if killErr != nil {
			fmt.Printf("failed to kill (pid=%d): %v\n", cmd.Process.Pid, killErr)
		}
		timedOut = true
		break
	case err = <-done:
		break
	}
	output = outputBuffer.String()
	return
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

	cmd := exec.Command("sh", "-c", "ls")
	out, exitCode, timedOut, err := RunCommandWithOutputForDuration(cmd, 1*time.Millisecond)
	if exitCode != 0 || !timedOut || err != nil {
		_ = fmt.Sprintf("%v", out)
	}
	time.Sleep(100 * time.Millisecond)
}
