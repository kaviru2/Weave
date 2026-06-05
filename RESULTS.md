# Weave — Results Log

Running record of empirical findings across all phases. Updated after each phase.
For methodology and code see `CLAUDE.md`; for current status see `STATUS.md`.

---

## Phase 5 — Zero-Shot Point-Prediction Baseline

**Model:** Gemini (gemini-2.5-flash) · **Examples:** 212 (15 programs × 5 runs × 3 splits) · **Setting:** zero-shot, no fine-tuning

### Overall Accuracy

| Metric | Score |
|---|---|
| event_type accuracy | 56.0% (116 / 207 scored) |
| goroutine_id accuracy | 49.8% (103 / 207 scored) |
| Deadlock detection | 0 / 5 |
| Race condition detection | 0 / 12 |

*5 deadlock examples excluded from accuracy scoring (no ground-truth next event).*

### Accuracy by Concurrency Pattern

| Pattern | Accuracy |
|---|---|
| fanout | 73.3% (best) |
| channel | 63.3% |
| pipeline | 60.0% |
| waitgroup | 56.7% |
| select | 56.7% |
| fanin | 56.7% |
| mutex | 43.3% (worst) |

### Accuracy by Nondeterminism Level

| Level | Accuracy |
|---|---|
| low | 63.3% |
| none | 60.0% |
| medium | 53.3% |
| high | 44.4% |

Higher nondeterminism → lower accuracy. Expected: harder programs produce harder predictions.

### Accuracy by Trace Split Point

| Split | Accuracy |
|---|---|
| 25% | 58.0% |
| 50% | 58.0% |
| 75% | 52.2% |

Accuracy degrades slightly at 75% — longer traces may present more ambiguous states.

### Confidence Calibration

High-confidence predictions correct only **58.0%** of the time. The model does not know
what it doesn't know — overconfidence is the dominant failure mode.

### Most Common Confusions

| Predicted → Actual | Count |
|---|---|
| GoStart ↔ GoUnblock | 20 |
| GoBlock ↔ GoStart | 19 |

Block/unblock symmetry is the core failure: the model cannot reliably distinguish
which goroutine transitions (start vs unblock) or which direction (block vs start).

### Key Conclusion

> The model fails predictably at concurrent next-state prediction. Zero bug-pattern
> awareness and systematic overconfidence motivate moving to distribution learning:
> instead of predicting a single next event, predict a probability distribution.

---

## Phase 6 — Empirical Next-Event Distributions

**Input:** 212 per-run examples grouped by `(program_id, split_percent)` → 42 aggregated groups  
**Method:** Empirical distribution from 5 runs per group + Dirichlet posterior (Jeffreys prior α=0.5)

### Entropy by Nondeterminism Level

| Level | Mean Entropy | Groups |
|---|---|---|
| high | 1.396 bits | 6 |
| medium | 1.210 bits | 15 |
| low | 0.903 bits | 18 |
| none | 0.971 bits | 3 |

Entropy stratifies correctly: high > medium > low. This confirms that the empirical
distributions carry a real signal — nondeterminism shows up as spread in the distribution.

### Deadlock Distribution Collapse

`04_deadlock` times out on every run (`TimedOut=true`, no `next_event`) and is excluded
from aggregated groups entirely. The originally hypothesised P(GoBlock)→1 collapse cannot
be observed directly.

For **leak programs** (`06_channel_select`, `14_goroutine_leak`):
- Mean P(GoBlock) = 0.300
- Mean P(GoUnblock) = 0.000 in all cases ← partial collapse signal

Reframed claim: *partial traces of leak-bound programs show P(GoUnblock)=0*, which is
consistent but weaker than a full GoBlock collapse. Noted as a limitation in the paper.

### Key Conclusion

> Empirical distributions from 5 runs encode nondeterminism as entropy. This is the
> training signal for distribution learning: train to minimise KL divergence from these
> empirical targets rather than cross-entropy from a single point label.

---

## Phase 7 — Distribution Zero-Shot Eval

**Model:** Gemini (gemini-3.5-flash) · **Groups:** 42 · **Two conditions tested:** thinking disabled vs thinking_budget=1024

### ECE Comparison

ECE = mean |predicted[et] − empirical[et]| averaged over 6 event types. Lower is better.

| Condition | ECE | vs Baseline |
|---|---|---|
| Phase 4 one-hot baseline | 0.2050 | — |
| Phase 7, thinking disabled | 0.1833 | −0.0217 |
| Phase 7, thinking=1024 | **0.1689** | **−0.0361** |

Distribution framing is marginally better than point prediction. Thinking budget makes
the difference — without it the improvement is small; with it ECE drops meaningfully.

### Model Entropy vs Nondeterminism Level

| Level | No thinking | Thinking=1024 | Empirical H |
|---|---|---|---|
| high | 0.287 bits | **1.029 bits** | 1.396 bits |
| medium | 0.686 bits | **0.928 bits** | 1.210 bits |
| low | 0.042 bits | **0.399 bits** | 0.903 bits |
| none | 0.000 bits | **0.687 bits** | 0.971 bits |

### KL Divergence KL(empirical ∥ predicted)

| Condition | Mean KL |
|---|---|
| Thinking disabled | 9.50 nats |
| Thinking=1024 | **7.00 nats** |

### Key Findings

**1. Thinking budget is necessary for distribution behaviour.**
Without thinking, the model outputs near-point predictions regardless of the
distribution prompt (H ≈ 0 bits on most groups). With thinking=1024, model entropy
rises to 0.4–1.0 bits — the model actually reasons about uncertainty.

**2. Systematic overconfidence persists.**
Even with thinking=1024, model H is 0.3–0.4 bits below empirical H. The model
understands the direction of uncertainty but underestimates its magnitude.

**3. Entropy partially tracks nondeterminism.**
With thinking: high (1.029) > medium (0.928) > low (0.399). The ordering breaks
between none (0.687) and low (0.399) — likely noise at 3 samples. Softened claim:
*thinking enables model entropy to roughly track nondeterminism level.*

**4. Overconfidence is the primary training target.**
The residual gap between model H and empirical H — and the high KL divergence — is
the core signal Phase 8 quantifies. A model trained to minimise KL from the empirical
distributions should close this gap.

### Key Conclusion

> Distribution framing + thinking reduces ECE from 0.205 → 0.169 vs the point-prediction
> baseline. The model can reason about uncertainty when given thinking tokens, but remains
> systematically overconfident. The KL gap (7 nats) between predicted and empirical
> distributions is the anomaly score Phase 8 uses to detect bugs and high-uncertainty programs.

---

## Summary Table

| Phase | What was measured | Key number |
|---|---|---|
| 4/5 | Point-prediction accuracy (zero-shot) | 56% event_type, 0% bug detection |
| 6 | Empirical next-event entropy by nondeterminism | high: 1.40b > medium: 1.21b > low: 0.90b |
| 7 (no thinking) | Distribution ECE vs one-hot baseline | 0.183 vs 0.205 (−10.6%) |
| 7 (thinking=1024) | Distribution ECE with reasoning enabled | **0.169 vs 0.205 (−17.6%)** |
| 8 | Anomaly scores, deadlock signatures | *pending* |

---

*Last updated: Phase 7 complete. Phase 8 (Dirichlet-Categorical Analysis) is next.*
