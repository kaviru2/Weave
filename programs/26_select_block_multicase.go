// WEAVE_META
// outcome: leak
// concurrency_pattern: select
// goroutine_count: 2
// expected_nondeterminism: none
// description: goroutine blocks in a select with four cases across distinct channel types; all conditions are structurally unreachable, confirming P(GoUnblock)=0 for multi-case select-block leaks.

package main

import (
	"fmt"
	"os"
	"runtime/trace"
	"time"
)

func main() {
	if tf := os.Getenv("WEAVE_TRACE_FILE"); tf != "" {
		f, err := os.Create(tf)
		if err == nil {
			if err := trace.Start(f); err == nil {
				defer func() { trace.Stop(); f.Close() }()
			}
		}
	}

	intCh := make(chan int)
	strCh := make(chan string)
	byteCh := make(chan []byte)
	errCh := make(chan error)

	// Goroutine blocks in a select with four cases across different channel types.
	// None of the channels are ever sent to — all cases are structurally unreachable.
	// GoUnblock is therefore impossible at any trace depth: the goroutine enters
	// GoWaiting immediately and stays there.
	go func() {
		select {
		case v := <-intCh:
			fmt.Println("int:", v)
		case s := <-strCh:
			fmt.Println("string:", s)
		case b := <-byteCh:
			fmt.Println("bytes:", b)
		case err := <-errCh:
			fmt.Println("error:", err)
		}
	}()

	// Sleep so the trace captures the goroutine in GoWaiting before main exits.
	time.Sleep(50 * time.Millisecond)
}
