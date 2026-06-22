package tracer

// EventType represents the kind of goroutine scheduler event captured in a snapshot.
type EventType string

const (
	GoCreate  EventType = "GoCreate"  // a new goroutine was created
	GoStart   EventType = "GoStart"   // a goroutine began executing on a thread
	GoBlock   EventType = "GoBlock"   // a goroutine blocked (channel, mutex, syscall, etc.)
	GoUnblock EventType = "GoUnblock" // a blocked goroutine became runnable again
	GoEnd     EventType = "GoEnd"     // a goroutine exited
	GoSched   EventType = "GoSched"   // a running goroutine was preempted back to runnable
)

// GoroutineState captures the current state of a single goroutine at a snapshot point.
type GoroutineState struct {
	// Status is one of "running", "runnable", "blocked", or "dead".
	Status string `json:"status"`

	// BlockedOn is the human-readable reason the goroutine is blocked, or nil if not blocked.
	// Examples: "channel receive", "sync.Mutex.Lock", "syscall".
	BlockedOn *string `json:"blocked_on"`

	// LocalsHint is the name of the top stack frame function — the closest we can get
	// to "what is this goroutine doing" without access to local variable state.
	LocalsHint string `json:"locals_hint"`
}

// ChanState records the observable state of one instrumented channel at a snapshot point.
// Populated only when the program uses weave/instrumented.WeaveChan; otherwise empty.
type ChanState struct {
	ID          string   `json:"id"`
	DataQSiz    int      `json:"dataqsiz"`     // buffer capacity; 0 = unbuffered
	QCount      int      `json:"qcount"`       // items currently in buffer
	RecvWaiters []uint64 `json:"recv_waiters"` // goroutine IDs blocked on receive
	SendWaiters []uint64 `json:"send_waiters"` // goroutine IDs blocked on send
}

// MutexState records the observable state of one instrumented mutex at a snapshot point.
// Populated only when the program uses weave/instrumented.WeaveMutex; otherwise empty.
type MutexState struct {
	ID      string   `json:"id"`
	Holder  uint64   `json:"holder"`  // goroutine ID holding the lock; 0 = unlocked
	Waiters []uint64 `json:"waiters"` // goroutine IDs blocked waiting for the lock
}

// StateSnapshot is one point in the concurrent execution trace. It captures which
// scheduler event occurred and the full state of every live goroutine at that moment.
type StateSnapshot struct {
	EventID     int                        `json:"event_id"`
	TimestampNS int64                      `json:"timestamp_ns"`
	EventType   EventType                  `json:"event_type"`
	GoroutineID uint64                     `json:"goroutine_id"` // goroutine that caused this event
	Goroutines  map[string]GoroutineState  `json:"goroutines"`   // keyed by goroutine ID string
	Channels    map[string]ChanState       `json:"channels"`     // populated when using WeaveChan
	Mutexes     map[string]MutexState      `json:"mutexes"`      // populated when using WeaveMutex
}

// RunResult captures the full output of running a single Go program under the tracer.
type RunResult struct {
	TraceFile  string // path where the program was expected to write its trace
	RaceOutput string // combined stderr content (race detector reports go here)
	ExitCode   int    // program exit code; -1 means timed out
	TimedOut   bool   // true if the program was killed due to deadline exceeded
	Stdout     string
	Stderr     string
}
