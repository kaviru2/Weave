// WEAVE_META
// outcome: race
// concurrency_pattern: channel
// goroutine_count: 3
// expected_nondeterminism: medium
// description: Human-written GoBench bug kernel etcd_4876 (race)

package main

import (
	"os"
	"runtime/trace"
	"sync"
		"time"
)

var ProgressReportInterval = 10 * time.Second

type Watcher interface {
	Watch()
}
type ServerStream interface{}

type Watch_WatchServer interface {
	Send()
	ServerStream
}
type watchWatchServer struct {
	ServerStream
}

func (x *watchWatchServer) Send() {}

type WatchServer interface {
	Watch(Watch_WatchServer)
}

type serverWatchStream struct{}

func (sws *serverWatchStream) sendLoop() {
	_ = time.NewTicker(ProgressReportInterval)
}

type watchServer struct{}

func (ws *watchServer) Watch(stream Watch_WatchServer) {
	sws := serverWatchStream{}
	go sws.sendLoop()
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

	var wg sync.WaitGroup
	wg.Add(3)
	go func() {
		defer wg.Done()
		w := &watchServer{}
		go func() {
			defer wg.Done()
			testInterval := 3 * time.Second
			ProgressReportInterval = testInterval
		}()
		go func() {
			defer wg.Done()
			w.Watch(&watchWatchServer{})
		}()
	}()
	wg.Wait()
}
