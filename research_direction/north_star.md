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
| **21** (payoff) | RQ1+RQ2 | Full corpus instrumentation (37 programs); rebuild trajectory dataset (970 train, 308 enriched); retrain Qwen3-8B; gap evals on 798 GoKer + rollout | ~$15 | **COMPLETE.** 49.7% in-dist, GoUnblock 0%→11.4%, 19.64 mean rollout steps |
| **22** (scale + baselines) | RQ2+RQ4 | **Dataset scale-up**: instrument GoReal 82 programs → ~2–3× training data. Add stronger neural execution baselines (not just zero-shot commercial APIs). Calibration-driven abstention for bug triage. | ~$20–40 | Larger corpus; reviewer-grade baseline comparison; downstream oracle utility |
| **23** (CWM warm-start) | RQ3 | Fine-tune `facebook/cwm-sft` (32B, QLoRA on A40) on Go execution traces; measure Python→Go transfer vs. training from scratch on Qwen3-8B. Contingent on Phase 22 dataset being ready. | ~$10–20 on A40 | Validates (or rules out) transfer from sequential CWM pre-training to concurrent Go execution |
| **24** (horizon) | RQ5 | Ballerina tracer from scratch (WSO2); strand-event corpus; cross-language transfer from Go model | WSO2 + modest GPU | Cross-language CSP world model — **deprioritized; post-thesis** |

> **Phase 22 priority note (added 2026-06-25):** Phase 22 directly addresses the two primary reviewer concerns raised against the Research Track submission: (1) *toy dataset* — GoReal 82 programs are production bugs from 9 open-source systems; instrumenting them with WeaveChan/WeaveMutex and generating traces would roughly triple the training corpus. (2) *weak baselines* — adding a comparison against a neural execution model (not just zero-shot commercial LLM) strengthens the experimental section. Phase 23 (Meta CWM warm-start) is medium priority contingent on Phase 22; Phase 24 (Ballerina) is deprioritized until Phase 22/23 are complete.

## How the Research Track paper fits as the first checkpoint

**Updated 2026-06-25: Pivoted from NIER → ICSE 2027 Research Track (abstract registered 2026-06-23, paper deadline Mon 30 Jun 2026 AoE).**

The **Research Track paper** (`ICSE 2027_Templates/weave-research/main.tex`) reports the full result:
40.1% next-event accuracy (trajectory vs. CE, McNemar p=0.016), 19.64 mean rollout steps,
GoUnblock 0%→11.4% via WeaveChan/WeaveMutex, three-class limitation taxonomy.
The paper's Discussion/Conclusion frames Phase 22 (dataset scale, stronger baselines) as explicit
future work, making the reviewer concern a publicly-acknowledged open problem rather than a weakness.
Phases 22–24 are the thesis programme the paper points at.

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
