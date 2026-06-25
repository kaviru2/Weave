// WEAVE_META
// outcome: blocking
// concurrency_pattern: channel
// goroutine_count: 1
// expected_nondeterminism: medium
// description: Auto-extracted GoBench bug kernel moby_4395 (blocking)

/*
 * Project: moby
 * Issue or PR  : https://github.com/moby/moby/pull/4395
 * Buggy version: 6d6ec5e0051ad081be3d71e20b39a25c711b4bc3
 * fix commit-id: d3a6ee1e55a53ee54b91ffb6c53ba674768cf9de
 * Flaky: 100/100
 * Description:
 *   The anonyous goroutine could be waiting on sending to
 * the channel which might never be drained.
 */

package main

import (
	"errors"
	"testing"

	"os"
	"runtime/trace"
)

func Go(f func() error) chan error {
	ch := make(chan error)
	go func() {
		ch <- f() // G2
	}()
	return ch
}

///
/// G1				G2
/// Go()
/// return ch
/// 				ch <- f()
/// ----------G2 leak-------------
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

	Go(func() error { // G1
		return errors.New("")
	})
}
