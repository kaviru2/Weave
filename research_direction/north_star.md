# Weave — Research North-Star (COMMITTED 2026-06-22)

**Owner sign-off: 2026-06-22.** Direction = **Candidate B core** (observability-complete,
distributional concurrent execution world model) with A as the NIER checkpoint, C as the payoff,
D as the horizon. Sequencing decision: **start the Phase 20 tracer feasibility spike now, in
parallel with the NIER checkpoint** (de-risk the main engineering unknown early). See
`candidates.md` for the trade-off analysis and `gap_map.md` for the scoop resolution.

---

## Thesis statement

> Concurrent program execution can be modeled as a **calibrated, distributional world model** — a
> learned, state-conditioned distribution over the next scheduler event — and the limits of such a
> model are governed not by data or model capacity but by **what the execution trace makes
> observable**. By building tracers that expose the causal scheduler state (channel buffers, lock
> holders) and by training against the **empirical nondeterminism** of repeated runs, we obtain a
> concurrent execution model that is coherent over multi-step rollout, well-calibrated, and useful
> as an **execution-free oracle** for concurrency bugs — across CSP-style languages (Go, Ballerina).

## Main research question

**MRQ.** *Can we learn a calibrated, distributional world model of concurrent program execution that
predicts the distribution over next scheduler events under nondeterministic interleaving — and what
must an execution trace expose for the hard events to become learnable?*

## Sub-questions (each maps to a phase + a falsifiable test)

- **RQ1 — Observability (the thesis core).** Is the accuracy ceiling on hard events (GoUnblock)
  an *observability* limit rather than a data or capacity limit? *Test:* exposing channel-buffer /
  mutex-holder state in the trace lifts GoUnblock from ~0% to positive, while it stays ~0% under
  matched data/compute without that state. → **Phase 20**.
- **RQ2 — Nondeterminism-as-signal & calibration.** Does training against empirical multi-run
  next-event distributions yield better calibration (lower ECE) and a more useful bug-detection
  signal than point training? *Test:* KL-trained vs CE-trained ECE + downstream abstention/detection
  AUC. → partly done (ECE 0.169); extend in **Phase 21**.
- **RQ3 — Coherence / rollout.** Can the model sustain coherent multi-step concurrent rollouts, and
  what training drives it? *Test:* mean survival steps + rollout event-distribution match to real
  tracer runs. → largely answered (10.48 steps, Phase 17 format effect); strengthen the rollout
  metric against real runs. → **Phase 19/21**.
- **RQ4 — Downstream oracle utility.** Can the learned model serve as an execution-free concurrency
  oracle (deadlock/leak detection, interleaving prioritization), optionally paired with a symbolic
  soundness check, competitively with search-based tools? *Test:* precision/recall on a held-out
  GoKer subset vs GCatch/GFuzz, no program execution at inference. → **Phase 21/22**.
- **RQ5 — Cross-language generalization.** Does the approach transfer from Go to another CSP/actor
  language (Ballerina), and does an observability-complete tracer built from scratch make the hard
  events learnable by design? *Test:* a Ballerina trace corpus + strand-event prediction with
  transfer from the Go model. → **Phase 23 (horizon)**.

## Phased roadmap (sized to moderate budget)

| Phase | RQ | Work | New compute | Output |
|---|---|---|---|---|
| **19** (checkpoint) | RQ2, RQ3 | Stratified-sampling retrain (Class-1; add hook to `prepare_trajectory.py`) + formal select-block **Proposition** (free) + rollout-vs-real-tracer metric | ~$2–6 | Lift GoEnd/GoSched off 0%, > 40.1%; theorem; stronger coherence claim — **feeds the NIER paper** |
| **20** (thesis core) | RQ1 | Build Go instrumentation exposing channel-buffer + mutex-holder state at unblock; regenerate traces; retrain; measure GoUnblock recovery (controlled: with vs without state) | ~$10–30 | The observability result — converts the Class-2 limitation into the central finding |
| **21** (payoff) | RQ2, RQ4 | Define downstream oracle task; eval vs GCatch/GFuzz; optional symbolic soundness check (Neural-Model-Checking template) | ~$10–20 | "Learned concurrent runtime as an execution-free oracle" |
| **22** (consolidation) | RQ4 | Scale corpus / GoBench coverage; calibration-driven abstention for bug triage | moderate | Robust tool-grade evaluation |
| **23** (horizon) | RQ5 | Ballerina tracer from scratch (WSO2); strand-event corpus; cross-language transfer | WSO2 + modest GPU | Cross-language CSP world model |

## How the NIER paper fits as the first checkpoint

The **ICSE 2027 NIER paper (deadline Fri 23 Oct 2026)** reports the *Candidate A* result — the Go,
distribution-aware concurrent execution model: 40.1% next-event accuracy, 10.48 survival steps,
McNemar p=0.016, GoCreate +24pp, ECE 0.169, the select-block Proposition — and frames its three-class
limitation taxonomy (data / observability / semantic) as the bridge to the thesis. Specifically, the
paper's **Future Plans** section becomes the public statement of RQ1 (observability-complete tracing,
Phase 20) and RQ5 (Ballerina, Phase 23). Phase 19 strengthens the checkpoint; Phases 20–23 are the
thesis the checkpoint points at. The NIER paper is honest emerging-results; the thesis is the program.

## Positioning guardrails (from the sweep)

1. Foreground **concurrency + nondeterminism-as-signal** early — these are what the
   CWM/Neural-Debugger fast-followers cannot trivially add. Timing risk is real.
2. Explicitly contrast: Neural Debugger for Python (sequential), Self-Execution Simulation
   (sequential/point), Probabilistic Calibration (spec-target not process-target), Q-learning CCT
   (learns-to-search not -predict), SWE-World (deterministic environment).
3. Disambiguate "nondeterminism": *program-execution* nondeterminism (ours) ≠ *LLM-inference* GPU
   nondeterminism (2601.06118) ≠ inference-engine batch nondeterminism (Thinking Machines).
4. Be honest about Ballerina: clean novelty, but a future-work commitment with no bootstrap corpus.

## Open decisions for the owner
- **Sign off on B-core** (vs A-only / C-led / D-first).
- Confirm Phase 20 tracer scope: custom Go `runtime`/eBPF instrumentation vs source-to-source
  rewrite (feasibility spike needed — this is the main engineering risk).
- Confirm whether the NIER checkpoint ships *before* or *concurrently with* starting Phase 20.
