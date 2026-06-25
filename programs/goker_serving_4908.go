// WEAVE_META
// outcome: nonblocking
// concurrency_pattern: channel
// goroutine_count: 3
// expected_nondeterminism: medium
// description: Auto-extracted GoBench bug kernel serving_4908 (nonblocking)

package main

import (
	"sync"

	"os"
	"runtime/trace"
)

type TestingT interface {
	Logf(string, ...interface{})
}

type WriteSyncer interface {
	Write()
}

type CheckedEntry struct {
	ErrorOutput WriteSyncer
	cores       []Core
}

func (ce *CheckedEntry) Write() {
	for i := range ce.cores {
		ce.cores[i].Write()
	}
}

type testingWriter struct {
	t TestingT
}

func newTestingWriter(t TestingT) testingWriter {
	return testingWriter{t: t}
}

func (w testingWriter) Write() {
	w.t.Logf("%s", "1")
}

type Logger struct {
	core Core
}

func (log *Logger) clone() *Logger {
	copy := *log
	return &copy
}

func (log *Logger) Check() *CheckedEntry {
	ent := &CheckedEntry{}
	ent.cores = append(ent.cores, log.core)
	return ent
}

func NewLogger(t TestingT) *Logger {
	writer := newTestingWriter(t)
	return New(NewCore(writer))
}

func New(core Core) *Logger {
	return &Logger{
		core: core,
	}
}

type Core interface {
	Write()
}

type ioCore struct {
	out WriteSyncer
}

func (c *ioCore) Write() {
	c.out.Write()
}

func NewCore(ws WriteSyncer) Core {
	return &ioCore{
		out: ws,
	}
}

type fakeT struct{}

func (fakeT) Logf(format string, args ...interface{}) {}

func testing_TestLogger() *SugaredLogger {
	return NewLogger(fakeT{}).Sugar()
}

func (log *Logger) Sugar() *SugaredLogger {
	return &SugaredLogger{log.clone()}
}

type SugaredLogger struct {
	base *Logger
}

func (s *SugaredLogger) log() {
	ce := s.base.Check()
	ce.Write()
}

func (s *SugaredLogger) Info(args ...interface{}) {
	s.log()
}

type revisionWatcher struct {
	logger *SugaredLogger
}

func newRevisionWatcher(logger *SugaredLogger) *revisionWatcher {
	return &revisionWatcher{
		logger: logger,
	}
}

func (rw *revisionWatcher) runWithTickCh() {
	rw.checkDests()
}

func (rw *revisionWatcher) checkDests() {
	go func() {
		rw.logger.Info("1")
	}()
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
	wg.Add(1)
	go func() {
		defer wg.Done()
		rw := newRevisionWatcher(testing_TestLogger())
		var _wg sync.WaitGroup
		_wg.Add(1)
		go func() {
			rw.runWithTickCh()
			_wg.Done()
		}()
		_wg.Wait()
	}()
	wg.Wait()
}
