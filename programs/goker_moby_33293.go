// WEAVE_META
// outcome: blocking
// concurrency_pattern: channel
// goroutine_count: 1
// expected_nondeterminism: medium
// description: Auto-extracted GoBench bug kernel moby_33293 (blocking)

/*
 * Project: moby
 * Issue or PR  : https://github.com/moby/moby/pull/33293
 * Buggy version: 4921171587c09d0fcd8086a62a25813332f44112
 * fix commit-id:
 * Flaky: 100/100
 */
package main

import (
	"errors"
	"math/rand"

	"os"
	"runtime/trace"
)

func MayReturnError() error {
	if rand.Int31n(2) >= 1 {
		return errors.New("Error")
	}
	return nil
}
func containerWait() <-chan error {
	errC := make(chan error)
	err := MayReturnError()
	if err != nil {
		errC <- err /// Block here
		return errC
	}
	return errC
}

///
/// G1
/// containerWait()
/// errC <- err
/// ---------G1 leak---------------
///

func main() {
	if tf := os.Getenv("WEAVE_TRACE_FILE"); tf != "" {
		f, err := os.Create(tf)
		if err == nil {
			if err := trace.Start(f); err == nil {
				defer func() { trace.Stop(); f.Close() }()
			}
		}
	}

	go func() { // G1
		err := containerWait()
		if err != nil {
			return
		}
	}()
}
