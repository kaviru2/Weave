package tracer

import (
	"fmt"
	"io"
	"os"
	"strconv"

	gotrace "golang.org/x/exp/trace"
)

// ParseTrace reads a Go execution trace file produced by runtime/trace and returns
// a slice of StateSnapshots — one per significant goroutine scheduler event.
// Each snapshot contains the full state of every live goroutine at that moment.
func ParseTrace(traceFile string) ([]StateSnapshot, error) {
	f, err := os.Open(traceFile)
	if err != nil {
		return nil, fmt.Errorf("open trace file: %w", err)
	}
	defer f.Close()

	r, err := gotrace.NewReader(f)
	if err != nil {
		return nil, fmt.Errorf("create trace reader: %w", err)
	}

	// goroutines tracks the current state of every live goroutine.
	goroutines := make(map[uint64]GoroutineState)
	var snapshots []StateSnapshot
	eventID := 0

	for {
		ev, err := r.ReadEvent()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, fmt.Errorf("read event: %w", err)
		}

		if ev.Kind() != gotrace.EventStateTransition {
			continue
		}

		st := ev.StateTransition()
		if st.Resource.Kind != gotrace.ResourceGoroutine {
			continue
		}

		goid := uint64(st.Resource.Goroutine())
		from, to := st.Goroutine()

		evType, blockedOn := mapTransition(from, to, st.Reason)

		localsHint := getTopFunction(ev.Stack())

		// Always update the live state map, even for transitions we don't emit snapshots for.
		updateGoroutineState(goroutines, goid, to, blockedOn, localsHint)

		if evType == "" {
			// Transition is not one we emit snapshots for (e.g. GoUndetermined → any).
			continue
		}

		snapshots = append(snapshots, StateSnapshot{
			EventID:     eventID,
			TimestampNS: int64(ev.Time()),
			EventType:   evType,
			GoroutineID: goid,
			Goroutines:  copyGoroutines(goroutines),
			Channels:    map[string]any{},
			Mutexes:     map[string]any{},
		})
		eventID++
	}

	return snapshots, nil
}

// mapTransition maps a (from, to) goroutine state pair to our EventType schema.
// Returns ("", nil) for transitions we don't capture (runtime internals, undetermined).
// The second return value is the blocked_on reason, only set for GoBlock events.
func mapTransition(from, to gotrace.GoState, reason string) (EventType, *string) {
	// Skip transitions from undetermined — goroutine was alive before tracing started.
	if from == gotrace.GoUndetermined {
		return "", nil
	}

	switch {
	case from == gotrace.GoNotExist && to == gotrace.GoRunnable:
		return GoCreate, nil

	case from == gotrace.GoRunnable && to == gotrace.GoRunning:
		return GoStart, nil

	// Syscall exit back to running counts as resuming execution.
	case from == gotrace.GoSyscall && to == gotrace.GoRunning:
		return GoStart, nil

	case from == gotrace.GoRunning && to == gotrace.GoWaiting:
		r := reason
		return GoBlock, &r

	// Entering a syscall is a blocking event from the goroutine's perspective.
	case from == gotrace.GoRunning && to == gotrace.GoSyscall:
		r := "syscall"
		return GoBlock, &r

	case from == gotrace.GoWaiting && to == gotrace.GoRunnable:
		return GoUnblock, nil

	// Syscall goroutine becoming runnable (e.g. async preemption during syscall).
	case from == gotrace.GoSyscall && to == gotrace.GoRunnable:
		return GoUnblock, nil

	case from == gotrace.GoRunning && to == gotrace.GoRunnable:
		return GoSched, nil

	case to == gotrace.GoNotExist:
		return GoEnd, nil

	default:
		return "", nil
	}
}

// updateGoroutineState updates the live goroutine state map after a transition.
// Goroutines that transition to GoNotExist are removed from the map.
func updateGoroutineState(goroutines map[uint64]GoroutineState, id uint64, to gotrace.GoState, blockedOn *string, localsHint string) {
	if to == gotrace.GoNotExist {
		delete(goroutines, id)
		return
	}
	goroutines[id] = GoroutineState{
		Status:     goStateToStatus(to),
		BlockedOn:  blockedOn,
		LocalsHint: localsHint,
	}
}

// goStateToStatus converts a Go runtime goroutine state to our status string.
func goStateToStatus(s gotrace.GoState) string {
	switch s {
	case gotrace.GoRunning, gotrace.GoSyscall:
		return "running"
	case gotrace.GoRunnable:
		return "runnable"
	case gotrace.GoWaiting:
		return "blocked"
	default:
		return "dead"
	}
}

// getTopFunction returns the name of the top (innermost) stack frame function,
// which is used as the locals_hint in GoroutineState.
// Returns "unknown" if no frames are available.
func getTopFunction(s gotrace.Stack) string {
	for frame := range s.Frames() {
		return frame.Func
	}
	return "unknown"
}

// copyGoroutines produces a snapshot copy of the live goroutine state map,
// converting uint64 goroutine IDs to string keys for JSON serialisation.
func copyGoroutines(goroutines map[uint64]GoroutineState) map[string]GoroutineState {
	result := make(map[string]GoroutineState, len(goroutines))
	for id, state := range goroutines {
		result[strconv.FormatUint(id, 10)] = state
	}
	return result
}
