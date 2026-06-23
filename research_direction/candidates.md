# Weave — Candidate North-Stars (as of 2026-06-22)

Four thesis-level directions, each scored on: gap filled, why-now, what it reuses, new work +
compute (moderate budget: low hundreds of $ RunPod, WSO2 later), scoop risk, and the falsifiable
first result. Recommendation at the end. Decision requires owner sign-off.

---

## A. Sharpen the current direction (distribution-aware concurrent CWM, Go-only)

- **Gap filled:** concurrent + distributional execution modeling for Go. Already validated.
- **Why now:** results locked; lowest risk; NIER-ready.
- **Reuses:** everything (tracer, corpus, traj model, KL pipeline, McNemar analysis).
- **New work/compute:** Phase 19 stratified retrain (~$2–4) + free select-block Proposition.
- **Scoop risk:** low on novelty, but **thin for a thesis** — one benchmark result on 130 programs;
  reviewers can call it "CWM but Go." Timing risk from Neural-Debugger lineage.
- **Falsifiable first result:** stratified retrain lifts GoEnd/GoSched off 0% and overall > 40.1%.
- **Verdict:** necessary as the *checkpoint*, insufficient as the *north-star*.

## B. Observability-complete concurrent execution modeling (the tracer IS the contribution)

- **Gap filled:** *what must an execution trace expose for concurrent next-event prediction to be
  learnable?* Directly attacks the Class-2 information-theoretic limit (GoUnblock 0%) that Go's
  runtime makes unfixable. No competitor touches this — RV literature only instruments for monitoring.
- **Why now:** Weave has *quantified* the blind spot (per-event 0% on GoUnblock with a causal
  explanation); the fix is an instrumentation + retrain loop, not a research gamble.
- **Reuses:** tracer architecture, training/eval pipeline, GoKer harness, per-event analysis.
- **New work/compute:** build custom Go instrumentation exposing channel-buffer + mutex-holder state
  at unblock time; regenerate traces; retrain; measure GoUnblock recovery. ~2–4 RunPod cycles
  (~$10–30). Engineering-heavy on the tracer side (the real cost is time, not GPU).
- **Scoop risk:** very low; green-field. Strong information-theoretic framing ("data limit vs
  observability limit vs semantic limit" taxonomy already exists in the project).
- **Falsifiable first result:** GoUnblock accuracy goes from 0% → meaningfully positive *only* when
  the trace exposes channel/lock state, and stays ~0% without it — a clean controlled experiment
  proving the limit is observability, not capacity or data.
- **Verdict:** the strongest *single* thesis core. Converts the biggest limitation into the
  central claim. Naturally bridges to Ballerina (UA-4).

## C. Learned concurrent runtime as an execution-free oracle (downstream utility)

- **Gap filled:** a *calibrated, distributional* L2 simulator with nondeterministic transitions used
  as a concurrency-bug / interleaving-prioritization oracle — the Agentic-WM survey's explicit
  deterministic-semantics gap, made useful via the Neural-Model-Checking (learned + symbolic check)
  template.
- **Why now:** "execution-free, calibrated feedback for agents" is hot (SWE-World, SWE-RM) and all
  sequential — the concurrent oracle is open.
- **Reuses:** traj model, rollout/coherence harness (10.48 steps), uncertainty/ECE, GoKer/GoBench.
- **New work/compute:** define a downstream task (deadlock/leak detection or interleaving ranking),
  build an eval vs GCatch/GFuzz, optionally add a symbolic soundness check. ~1–3 cycles (~$10–20)
  + harness engineering.
- **Scoop risk:** low on the concurrent specialization; medium that "oracle utility" is hard to win
  decisively against mature symbolic tools.
- **Falsifiable first result:** the model flags select-block leaks / deadlocks at a useful
  precision-recall *without running the program*, competitive with or complementary to a search tool
  on a held-out GoKer subset.
- **Verdict:** the strongest *payoff* chapter; weaker as a standalone spine. Best paired with B.

## D. Cross-language CSP world model (Go → Ballerina), tracer-first

- **Gap filled:** generalization of learned concurrent execution across CSP/actor languages;
  Ballerina is academically untouched.
- **Why now:** owner's WSO2 insider access + ability to build a tracer that is observability-complete
  *by design* (no legacy runtime constraint).
- **Reuses:** conceptual framework, event taxonomy, training recipe.
- **New work/compute:** build a Ballerina tracer + corpus from scratch; the heaviest engineering
  lift; no bootstrap data. Real spend is months of tooling, modest GPU.
- **Scoop risk:** lowest of all; but highest execution risk and longest horizon.
- **Falsifiable first result:** a Ballerina trace corpus + a model that predicts strand scheduler
  events, showing transfer from the Go-trained model.
- **Verdict:** the right *late-thesis horizon* and the cleanest novelty, but premature as the opening
  move — needs B's instrumentation lessons first.

---

## Recommendation

**Adopt B as the thesis core, with A as the published checkpoint and C as the payoff chapter; D is
the closing horizon.** This composition (UA-1 + UA-2 + UA-3, then UA-4) is a single coherent arc:

> A calibrated, **distributional world model of concurrent execution**, where an
> **observability-complete tracer** supplies the causal state that makes the hard scheduler events
> learnable, the program's **nondeterminism** supplies the training signal, the model pays off as an
> **execution-free concurrency oracle**, and **Ballerina** is the cross-language generalization.

Rationale: B turns the project's documented worst limitation (GoUnblock 0%, information-theoretic)
into a falsifiable controlled experiment and the central question, is fully asset-matched, has
essentially no scoop risk, and fits the moderate budget (cost is tracer engineering, not GPU). A is
already in hand and gives the Oct 2026 NIER checkpoint. C converts the model into a tool. D banks the
cleanest long-horizon novelty once B's instrumentation is proven.

Full RQ formulation + phased roadmap in `north_star.md` (**draft pending owner sign-off**).
