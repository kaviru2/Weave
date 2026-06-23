# Phase 20 — Observability-Complete Tracer: Feasibility Spike (2026-06-22)

Read-only spike for the thesis-core RQ1: *is the GoUnblock 0% ceiling an observability limit
(fixable by exposing causal scheduler state) rather than a data or capacity limit?* This note
records what the current tracer captures, what it cannot, and the three engineering paths to close
the gap — with a recommendation.

## What the current tracer captures (verified)

- `tracer/parser.go` consumes `golang.org/x/exp/trace` `EventStateTransition` events for goroutines.
- Each `StateSnapshot` (`tracer/state.go`) has per-goroutine `status` + `blocked_on` + `locals_hint`,
  but **`Channels` and `Mutexes` are hardcoded empty** (`parser.go:71-72`). Comment is explicit:
  *"go tool trace doesn't expose channel/mutex addresses."*
- `blocked_on` comes from `st.Reason`. Distinct values actually present across 1,827 trace files:

  | reason | count | what it tells us |
  |---|---|---|
  | `chan receive` | 42,390 | a goroutine is blocked receiving — but **not on which channel** |
  | `sleep` | 29,156 | timer wait |
  | `sync` | 13,996 | blocked on a sync primitive (mutex/waitgroup) — **not which, not the holder** |
  | `system goroutine wait` | 8,485 | runtime-internal |
  | `select` | 6,949 | blocked in a select — **not which cases / channels** |
  | `syscall` | 5,484 | syscall |
  | `chan send` | 5,423 | blocked sending — **not on which channel, buffer full?** |
  | `sync.(*Cond).Wait` | 13 | condvar wait |

## The exact missing information (why GoUnblock is unpredictable)

Predicting GoUnblock(g) requires knowing the *causal* event: another goroutine sends to / closes the
channel g awaits, or unlocks the mutex g awaits. The trace gives the **kind** of wait but not:

1. **Channel identity** — which `hchan` g is blocked on, so it can be linked to the goroutine about
   to send on that same channel.
2. **Channel buffer state** — `qcount` / `dataqsiz` (is a buffered send about to succeed?).
3. **Waiter queues** — `recvq` / `sendq` (who is parked on this channel).
4. **Mutex holder identity** — which goroutine currently holds the lock g is waiting for.

Without (1)–(4), GoUnblock is information-theoretically unpredictable from the trace — matching the
project's documented 0% GoUnblock accuracy. **RQ1's premise is confirmed by the data**, not just
asserted. Note: `blocked_on` *is* already in the snapshot JSON the model sees, so the cheap
"Class-3" add-blocked_on idea is largely already in place — the missing piece is *cross-goroutine
channel/mutex linkage*, which no amount of prompt-formatting recovers.

## Three engineering paths to expose the causal state

| Option | Mechanism | Fidelity | Cost / risk | Platform |
|---|---|---|---|---|
| **A. Wrapper/shim library (corpus-controlled)** | Replace `chan T`/`sync.Mutex` in the test programs with instrumented wrapper types that log {channel id, qcount, dataqsiz, waiters} and {mutex holder goid} on every op into a side trace; merge with the scheduler trace by (timestamp, goid). | High for the primitives we wrap | **Lowest.** Pure Go, no toolchain fork. Risk: rewrites program source (model trains on instrumented text) and may perturb scheduling — must show bug class preserved. | macOS + Linux |
| **B. Go runtime fork** | Patch `runtime/chan.go` + lock paths to emit richer trace events natively. | Highest, unperturbed source | **Highest.** Maintain a custom Go toolchain on RunPod; rebuild per Go version. | Linux (RunPod) |
| **C. eBPF / uprobes** | Attach uprobes to `runtime.chansend`/`chanrecv`/`lock`/`unlock`, read `hchan` fields from args. | High, unperturbed source | **Medium.** No source change, no fork, but fragile across Go versions/inlining; needs root. | **Linux only** (not the Mac) |

## Recommendation

**Stage A → C, defer B.**

1. **Build Option A first** as the controlled RQ1 experiment. It is the cheapest, runs on the Mac for
   development, fully fills the empty `Channels`/`Mutexes` maps, and gives a clean A/B: retrain the
   model on traces *with* vs *without* the channel/mutex state and measure GoUnblock recovery. If
   GoUnblock goes 0% → positive only with the state, the thesis claim is proven with one experiment.
   Estimated: instrumentation library + corpus regen + 1–2 retrain cycles (~$6–15 RunPod).
2. **Follow with Option C** only if reviewers would object to instrumented source — uprobes give the
   same state on *unmodified* programs (run on RunPod/Linux). Validates that A's result isn't a
   source-perturbation artifact.
3. **Defer Option B** unless A and C both prove insufficient; the runtime fork is the strongest claim
   but the worst cost/maintenance ratio for a thesis timeline.

## Risks to watch
- **Scheduling perturbation (Option A):** wrappers add work on the hot path → different interleavings.
  Mitigate by comparing event-type distributions and bug reproduction (deadlock/leak still fires)
  before vs after instrumentation.
- **Select blocks:** wrapping `select` over wrapped channels is the hardest case — prototype it early
  (it is also where the select-block Proposition lives, so high value).
- **Corpus scope:** start the prototype on 2–3 GoKer programs spanning chan-receive, chan-send, and
  mutex waits; only scale after the A/B signal is clear.

## Immediate next action (proposed)
Prototype Option A on a small GoKer subset: define instrumented `WeaveChan[T]` / `WeaveMutex` types,
emit identity+buffer+holder events, merge into the snapshot `Channels`/`Mutexes` maps, and confirm a
blocked goroutine can now be linked to its imminent unblocker. Then a single retrain to read the RQ1
signal. (Awaiting go-ahead on the approach before writing code.)
