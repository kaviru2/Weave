# Weave — Literature Sweep (as of 2026-06-22)

Fresh sweep run to stress-test the existing framing and scout a thesis-level reframe.
Extends (does not replace) `related_works.md`. Six axes, parallel web-search subagents.
**Verification note:** titles/authors/dates confirmed via arXiv abstract pages where stated;
2025–2026 IDs (25xx/26xx) are consistent with today's date but should get a final manual check
before any are cited as load-bearing prior work. The Axis 6 sweep ran while the safety
classifier was unavailable — treat its IDs as provisional until re-verified.

Scoop-risk legend: **none** = different problem; **partial** = overlaps on method or domain but
not both; **high** = would directly contest Weave's claim.

---

## Axis 1 — Post-CWM execution world models (primary scoop-risk axis)

| Paper | Venue / date | Scoop | Why |
|---|---|---|---|
| CWM (arXiv:2510.02387) | Meta FAIR, Sep 2025 | none (the thing extended) | Sequential Python only; flags concurrency as open future work; point-state. |
| Execution Tuning / "What I cannot execute…" (2503.05703) | Mar 2025 | none | Single-threaded Python, deterministic point traces. |
| Debugging Code World Models (2602.07672) | Feb 2026 | none | Analyses deterministic CWM failures; treats divergence as error, not legitimate branching. |
| **Towards a Neural Debugger for Python (2603.09951)** | Beck, Gehring, Kossen, Synnaeve — Mar 2026 | **partial** | **Closest framing competitor.** CWM-lineage; explicitly "world model for simulated debugging environments"; forward+inverse execution — but sequential Python, no threads/nondeterminism. |
| Self-Execution Simulation Improves Coding Models (2604.03253) | Maimon et al. — Mar 2026 | partial (method) | Genuinely trains on execution traces (SFT+RL) — but sequential competitive-programming, point traces. The "sequential analog" of Weave. |
| The Double Life of Code World Models (2512.13821) | Sahoo — Dec 2025 | none | Uses predicted traces for backdoor detection; no training, no concurrency. |
| Do Code Semantics Help? (2509.11686) | EMNLP'25 Findings | none | Trace-utility study; sequential. |

Disambiguation traps (NOT competitors): "Defeating Nondeterminism in LLM Inference" (Thinking
Machines, Sep 2025) and Hogwild! Inference / async function-calling — these are *inference-engine*
serving nondeterminism, not *program-execution* nondeterminism.

**Bottom line:** No one has scooped distribution-aware concurrent execution modeling. Every
post-CWM execution paper is sequential/deterministic/point-prediction. Closest = **Neural Debugger
for Python** (same lineage, most likely to extend toward concurrency → *timing* risk, not territory).

---

## Axis 2 — LLMs & concurrency / scheduling / interleavings

| Paper | Venue / date | Scoop | Why |
|---|---|---|---|
| CONCUR (2603.03683) | Mar 2026 | none | Concurrent *code generation* benchmark, judged by model checking. Its premise (execution can't cover all interleavings) is the gap Weave fills with a learned distribution. |
| Jain & Purandare (2501.14326) | Jan 2025 | none (known baseline) | Zero-shot comprehension/verification across memory models; models fail to produce valid relaxed-memory traces → motivates a *trained* execution model. |
| CIR+CVN, LLM→Petri-net (2604.09318) | Apr 2026 | none | Neuro-symbolic generate→verify; LLM does translation, Petri net does execution reasoning. |
| Self-Execution Simulation (2604.03253) | Mar 2026 | partial | (see Axis 1) Sequential analog. |
| Data Race Detection w/ LLMs (DRB-ML, 2308.07505) | 2023 | none | Static race *classification*, OpenMP. |
| Go-UT-Bench (2511.10868) | Nov 2025 | none | Go unit-test generation; corroborates Go concurrency is hard for LLMs. |

**Bottom line:** Concurrency-LLM work splits into generation (CONCUR), verification (CIR+CVN), and
zero-shot comprehension/classification (Jain&Purandare, DRB-ML) — none models concurrent execution
dynamics as a learned transition function. Sharpest contrasts to draw: Weave vs Self-Execution
Simulation (concurrent+distributional vs sequential+point); Weave vs Jain&Purandare (trained
transition model vs zero-shot that demonstrably fails to produce valid interleavings).

---

## Axis 3 — ML / neural-guided concurrency testing & scheduling

| Paper | Venue / date | Scoop | Why |
|---|---|---|---|
| **Learning-based Controlled Concurrency Testing (Q-learning)** — Mukherjee et al. | OOPSLA 2020 | **partial (closest concept)** | Learns Q-values to bias *which interleaving to try next* — but to maximise bug-search coverage, not to predict a next-event distribution. Learns-to-search, not learns-to-predict. |
| Reward Augmentation in RL for Testing Distributed Systems (2409.02137) | Sep 2024 | none/partial | Engineered exploration rewards; no learned scheduling distribution. |
| GoPie (ASE'23) | 2023 | none | Confirmed directional constraint search, *not* RL. Pure schedule search. |
| Deep Learning Concurrency Bug Detection+Localization (2508.20911) | Aug 2025 | none | GNN over code-property graph; static classification, no execution. |
| PCT (ASPLOS'10) / POS (CAV'18) | 2010 / 2018 | none | *Probabilistic* over schedules but distribution is **hand-designed** for coverage, never learned/predicted. Formalises "nondeterminism as sampled search space" — the framing Weave argues against. |

**Bottom line:** No one learns a distribution over scheduler events as a predictive training target
from empirical run nondeterminism. Closest = **Q-learning CCT (OOPSLA'20)** — must be explicitly
distinguished (learns-to-search vs learns-to-predict-distribution). The whole field treats
nondeterminism as a search space or a hazard, never a learnable target.

---

## Axis 4 — Distributional / calibrated training for code

| Paper | Venue / date | Scoop | Why |
|---|---|---|---|
| **Probabilistic Calibration Is a Trainable Capability in LMs (2605.11845)** | May 2026 | **partial→high (closest mechanism)** | Hard-target = "repeated sampled completions from the same target distribution" — structurally identical move. BUT target is a *designer-specified* random request, not a process's irreducible nondeterminism; not code/execution-specific. |
| RisCoSet — UQ for code generation (2605.12201) | ICML 2026 | partial | Uses execution + repeated sampling, but conformal coverage over *output correctness*, not transition-distribution training. |
| Token-Level Uncertainty-Aware Objective (2503.16511) | Mar 2025 | none | Soft targets from *model's own epistemic* uncertainty (MC-dropout), not the program's aleatoric nondeterminism. |
| Localized Calibrated Uncertainty in Code LMs (2512.24560) | Dec 2024 | none/partial | Code-specific calibration successor to Spiess, but targets correctness labels, not execution dynamics. |
| Forcing Diffuse Distributions (2404.10859) | 2024 | none (anchor) | Hand-specified target distribution. |
| Spiess et al., Calibration & Correctness of LMs for Code | ICSE'25 | none (anchor) | Code-calibration baseline; no distribution training. |
| Beyond Reproducibility: Token Probs Expose LLM Nondeterminism (2601.06118) | Jan 2026 | none (terminology trap) | *GPU/inference* nondeterminism — opposite sense. Disambiguate explicitly in paper. |

**Bottom line:** "Empirical-nondeterminism-of-a-concurrent-program-as-distributional-target" appears
novel. The defensible novelty is the *conjunction*: (1) target = aleatoric nondeterminism of the
program itself (not teacher, not spec), (2) over concurrent execution next-state, (3) trained via
KL, (4) framed for bug-detection calibration. Pre-empt reviewers by contrasting 2605.11845
(spec-target vs process-target) and disambiguating 2601.06118.

---

## Axis 5 — World models as learned environments / downstream framings

| Paper | Venue / date | Role | Note |
|---|---|---|---|
| Neural Debugger for Python (2603.09951) | Mar 2026 | framing-enabler + closest | Explicit "world model for debugging environments"; sequential. Same group most likely to go concurrent. |
| **SWE-World (2602.03419)** | Feb 2026 | competitor on generic framing | Learned surrogate environment predicting execution outcomes for SE agents (Docker-free). Sequential/deterministic — concurrent niche open. |
| SWE-RM (2512.21919) | Dec 2025 | framing-enabler | 30B execution-free *reward* model for SE agents; validates "execution-free + calibrated" is valued. Not a behaviour model. |
| **Agentic World Modeling survey (2604.22748)** | 2026 | framing vocabulary + stated gap | Taxonomy L1 Predictor / L2 Simulator / L3 Evolver; explicitly assumes *deterministic* program semantics → Weave = L2 Simulator with nondeterministic transitions. |
| **Neural Model Checking (2410.23790)** | NeurIPS 2024 | methodological template | Learned artifact + symbolic SAT soundness check → sound verification oracle. Template for a *defensible* Weave-as-oracle claim. |
| WebDreamer (OpenReview) | 2025 | precedent | LLM as world model for model-based planning (web agents). |

Adjacent (concurrency oracles stay symbolic, NOT learned): Runtime Verification of Concurrent
Systems (2507.04830); SHB-based concurrency-bug fixing (2604.05753).

**Bottom line:** Strongest thesis-scale framing = "a learned, distributional model of a concurrent
runtime used as an execution oracle." Two concrete payoffs: (1) interleaving/schedule prioritization
without running the program (L2 simulator with nondeterministic transitions — the survey's explicit
gap); (2) learned concurrency verification oracle (Neural Model Checking template: learned model +
cheap symbolic soundness check). The concurrent niche is essentially unoccupied; the SE-agent
"learned environment" space is contested but entirely sequential/deterministic. Risk = timing.

---

## Axis 6 — Neural program execution + CSP / Ballerina

**Learning-to-execute lineage (Weave's ancestry):** Learning to Execute (Zaremba & Sutskever,
1410.4615, 2014) → Neural Turing Machines (1410.5401) → Neural Programmer-Interpreters (1511.06279,
ICLR'16) → IPA-GNN (2010.12621, NeurIPS'20) → Static Prediction of Runtime Errors via learned
execution (2203.03771, ICLR'23) → neural algorithmic reasoning revival (Veličković et al.;
CLRS) 2024–2026. All **deterministic/sequential or algorithmic** — concurrent scheduling unworked.
IPA-GNN's structure-visible-vs-hidden tension mirrors Weave's GoCreate (source-visible) vs GoUnblock
(trace-hidden) split.

**Ballerina — genuinely green-field:** No peer-reviewed academic work on Ballerina execution
modeling / tracing / ML. Only vendor docs (concurrency model: workers/strands, compile-time
deadlock/race detection; built-in OpenTelemetry tracing) and James Clark's design essays. Real
novelty claim, but *no bootstrap corpus/benchmark* → must be framed as a future-work commitment, and
the owner's WSO2 insider access + build-tracer-from-scratch is the only viable path.

**CSP/actor execution + observability precedent:**
- ACTORCHESTRA (2603.17909, ICST'26) — Erlang/OTP runtime verification; causality tokens injected
  to reconstruct multi-actor causal traces → proves causal "who-unblocked-whom" needs *deliberate
  instrumentation*, exactly Go's GoUnblock blind spot.
- RIARC (2406.19904, ECOOP'24) — sound decentralized trace instrumentation for reactive/actor
  systems → formalises how hard a trustworthy concurrent trace is.
- Concurrency-Agnostic Debugging Protocol (1706.00363, 2017) — one representation spanning threads/
  actors/CSP/STM → the abstraction a Go→Ballerina port would need.
- Go `runtime/trace` + "More powerful Go execution traces" (go.dev, 2024) — primary-source
  confirmation the tracer records unblock *events* but not channel-buffer contents or mutex-holder
  identity → the information-theoretic basis of the GoUnblock limit.

**Bottom line:** (i) Weave is a legitimate descendant of learning-to-execute, occupying the unworked
concurrent-scheduler corner. (ii) Ballerina/CSP extension is genuinely open but empirically
un-bootstrapped — future-work, not a demonstrated result. (iii) The observability-complete-tracer
idea has indirect precedent: the RV community shows channel/lock causality must be instrumented in,
which both validates the GoUnblock claim and gives a citable engineering blueprint.

---

## Cross-axis verdict

1. **Core idea unscooped** as of 2026-06-22 across all six axes.
2. **Must-position-against (closest):** Neural Debugger for Python (2603.09951) and Self-Execution
   Simulation (2604.03253) on execution-WM; Probabilistic Calibration is Trainable (2605.11845) on
   the distributional-target mechanism; Q-learning CCT (OOPSLA'20) on learned scheduling;
   SWE-World (2602.03419) on learned-environment-for-agents.
3. **Primary risk is timing, not territory** — the CWM/Neural-Debugger lineage is the likely fast
   follower into concurrency. Move the concurrent + nondeterminism-as-signal claims to the front.
4. **Three unfair-advantage intersections** (open gap × owner asset): nondeterminism-as-signal;
   observability-complete tracer (Go instrumentation + Ballerina from scratch); learned concurrent
   runtime as an execution-free oracle (Neural Model Checking template).
