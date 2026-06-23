# Weave — Gap Map (as of 2026-06-22)

Synthesises `lit_sweep_2026-06.md` into (1) where each adjacent subfield stops, (2) the resolved
scoop question, and (3) the unfair-advantage intersections that justify a thesis-level program.

---

## 1. Subfield × what they do × what they ignore × asset we have they don't

| Subfield | What they do | What they assume / ignore | Asset Weave has they don't |
|---|---|---|---|
| **Code/execution world models** (CWM, Execution Tuning, Neural Debugger, Self-Exec-Sim) | Train LLMs to predict program state after each line; world-model-for-debugging framing | **Sequential, deterministic, single valid next-state**; concurrency named as open future work | A concurrent execution corpus + a goroutine-scheduler-event transition model |
| **LLMs for concurrent code** (CONCUR, Jain&Purandare, CIR+CVN) | Generate / verify / comprehend concurrent code | Execution is a *verification obstacle* (model-checking, Petri nets); no learned dynamics | A *learned* transition function over real execution traces |
| **ML/neural concurrency testing** (Q-learning CCT, RL distributed testing, GFuzz/GoPie) | Learn or heuristically guide a *search* over interleavings to surface bugs | Nondeterminism = **search space** to cover; no predictive next-event model | Next-event *prediction* (learns-to-predict, not learns-to-search) |
| **Probabilistic testing** (PCT, POS) | Sample schedules with provable bug-depth bounds | Distribution over schedules is **hand-designed**, never learned/predicted from state | Empirically-derived, state-conditioned next-event distribution |
| **Distributional / calibration training** (Prob-Calib-Trainable, diffuse, RisCoSet, Spiess) | Fine-tune to match a *specified* distribution; calibrate code-correctness confidence | Targets come from a **teacher or designer spec**, or are about output correctness | Soft targets = the *program's own aleatoric nondeterminism* over execution state |
| **World-models-as-environments** (SWE-World, SWE-RM, Neural Debugger, Agentic-WM survey) | Learned surrogate environments/rewards so agents skip real execution | **Deterministic program semantics** (survey says so explicitly) | An L2 simulator with *nondeterministic* transitions + calibrated uncertainty |
| **Learned verification** (Neural Model Checking) | Learn a proof certificate, validate symbolically — sound oracle for reactive/HW systems | Targets temporal properties of (mostly) hardware/reactive systems, not goroutine schedulers | A learned concurrent-execution model that can plug into this template |
| **Neural program execution lineage** (LtE, NPI, IPA-GNN, neural algo reasoning) | Learn to execute programs/algorithms step-by-step | Deterministic sequential code or classical algorithms | Concurrent, nondeterministic scheduler dynamics |
| **CSP/actor RV + tracing** (ACTORCHESTRA, RIARC, Go runtime/trace) | Instrument concurrent systems to get sound causal traces | Traces for *monitoring*, not for *learning*; Go trace hides channel-buffer/mutex-holder | A reason to build an *observability-complete* tracer to make events learnable |

---

## 2. The scoop question — resolved

**Is "distribution-aware concurrent execution modeling" still open as of 2026-06-22? → Yes.**

Closest competing work and the precise daylight:

- **Neural Debugger for Python (2603.09951, Mar 2026)** — closest *framing*. Same CWM lineage,
  explicit "world model for debugging environments," forward+inverse execution.
  *Daylight:* sequential Python only — no goroutines/threads, no interleavings, no distribution over
  next states. One deterministic next-state per step.
- **Self-Execution Simulation (2604.03253, Mar 2026)** — closest *method*. Genuinely trains an LLM on
  execution traces.
  *Daylight:* sequential competitive-programming code, point traces; nondeterminism absent.
- **Probabilistic Calibration Is a Trainable Capability (2605.11845, May 2026)** — closest
  *mechanism*. Hard-target supervision from "repeated sampled completions of the same target
  distribution" = structurally Weave's "many runs → empirical distribution."
  *Daylight:* the target is a **designer-specified** random request, not a program's irreducible
  scheduler nondeterminism; not code/execution-specific.
- **Q-learning Controlled Concurrency Testing (OOPSLA 2020)** — closest *concurrency-learning*.
  *Daylight:* learns a **search policy** to maximise bug coverage, not a **predictive next-event
  distribution**; pre-LLM; not a world model.

**One-sentence reviewer-proof claim:** *No prior work learns a calibrated, state-conditioned
distribution over the next concurrent scheduler event from the empirical nondeterminism of repeated
program runs; the closest neighbours are either sequential/deterministic (Neural Debugger,
Self-Execution Simulation), match a designer-specified rather than process-derived distribution
(Probabilistic Calibration), or learn to search rather than to predict (Q-learning CCT).*

**Caveat — timing risk.** The CWM/Neural-Debugger group is the likely fast follower into
concurrency. The defence is to foreground the two things they cannot trivially add: (a)
nondeterminism-as-training-signal, (b) observability-complete tracing of the causal scheduler state.

---

## 3. Unfair-advantage intersections (open gap × owner asset)

**UA-1 — Nondeterminism-as-signal.** The program's own scheduler stochasticity is the distributional
target. Open (Axis 4) *and* already prototyped (Weave's empirical-distribution pipeline, KL training,
ECE 0.169). Cheapest to push; the conceptual spine of the thesis.

**UA-2 — Observability-complete tracer.** Go's `runtime/trace` hides channel-buffer contents and
mutex-holder identity, making GoUnblock information-theoretically unpredictable (the project's
documented Class-2 limit; 0% GoUnblock accuracy). RV literature (ACTORCHESTRA, RIARC) proves this
causal state must be *instrumented in*. The owner can (a) build custom Go instrumentation and, more
powerfully, (b) build a **Ballerina tracer from scratch** (WSO2 insider access) that exposes
channel/lock state by design. This converts the paper's hardest limitation into the thesis's central
research question: *what must a trace expose for concurrent execution to be learnable?*

**UA-3 — Learned concurrent runtime as an execution-free oracle.** Frame the model as an L2 simulator
with nondeterministic transitions (Agentic-WM survey's explicit gap) and pair it with a cheap
symbolic soundness check (Neural Model Checking template) to make a *defensible* deadlock/leak/
interleaving-prioritization oracle — measured as downstream utility vs GCatch/GFuzz, not just
next-event accuracy. Turns a benchmark number into a tool.

**UA-4 — Ballerina green-field (longer horizon).** Zero academic execution-modeling work on
Ballerina; owner has the only viable path (insider + from-scratch tracer). High novelty, but no
bootstrap corpus → a future-work / late-thesis commitment, not an early result.

---

## 4. What this implies for the direction

The three near-term intersections (UA-1, UA-2, UA-3) compose into a single coherent thesis: a
**calibrated, distributional world model of concurrent execution**, where (UA-2) an
observability-complete tracer supplies the causal state that makes the hard events learnable,
(UA-1) the program's nondeterminism supplies the training signal, and (UA-3) the model pays off as
an execution-free concurrency oracle — with (UA-4) Ballerina as the cross-language generalization
horizon. The ICSE 2027 NIER paper is the first checkpoint (the Go, distribution-aware result + honest
Class-2 limitation that *motivates* UA-2). See `candidates.md` and `north_star.md`.
