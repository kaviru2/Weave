// WEAVE_META
// outcome: race
// concurrency_pattern: select
// goroutine_count: 3
// expected_nondeterminism: medium
// description: Human-written GoBench bug kernel kubernetes_70892 (race)

package main

import (
	"os"
	"runtime/trace"
	"context"
	"sync"
	)

type HostPriorityList []int

type DoWorkPieceFunc func(piece int)

func ParallelizeUntil(ctx context.Context, workers, pieces int, doWorkPiece DoWorkPieceFunc) {
	var stop <-chan struct{}
	if ctx != nil {
		stop = ctx.Done()
	}

	toProcess := make(chan int, pieces)
	for i := 0; i < pieces; i++ {
		toProcess <- i
	}
	close(toProcess)

	if pieces < workers {
		workers = pieces
	}

	wg := sync.WaitGroup{}
	wg.Add(workers)
	for i := 0; i < workers; i++ {
		go func() {
			defer wg.Done()
			for piece := range toProcess {
				select {
				case <-stop:
					return
				default:
					doWorkPiece(piece)
				}
			}
		}()
	}
	wg.Wait()
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

	priorityConfigs := append([]int{}, 1, 2, 3)
	results := make([]HostPriorityList, len(priorityConfigs), len(priorityConfigs))

	for i := range priorityConfigs {
		results[i] = make(HostPriorityList, 2)
	}
	processNode := func(index int) {
		for i := range priorityConfigs {
			if results[i][0] != 4 {
				results[i] = HostPriorityList{7, 8, 9}
			}
		}
	}
	ParallelizeUntil(context.Background(), 2, 2, processNode)
}
