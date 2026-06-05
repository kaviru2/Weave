#!/usr/bin/env python3
"""
Phase 7 — Distribution Zero-Shot Eval

For each aggregated group (program_id, split_percent) from Phase 6, loads a
representative partial trace (run_index=0), asks Gemini to predict a probability
distribution over the six next-scheduler-event types, and measures calibration
against the empirical distributions.

Key metrics:
  ECE             — mean |predicted[et] - empirical[et]| per event type (lower = better)
  KL divergence   — KL(empirical || predicted)
  Model entropy   — H(predicted); should correlate with program nondeterminism level

Also computes a Phase 4 one-hot baseline ECE for comparison: treating each Phase 4
point-prediction as a degenerate distribution lets us put both evaluations on the
same calibration axis.

Output: eval/results/dist_zero_shot_results.json
Run:    uv run python eval/dist_zero_shot.py
"""

import argparse
import glob
import json
import math
import os
import sys
import time
from collections import defaultdict
from typing import Any, Optional

import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types
from scipy.special import rel_entr

# Load .env so GEMINI_API_KEY and MODEL are available via os.getenv.
load_dotenv()

DATASET_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset", "output")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
AGGREGATED_FILE = os.path.join(DATASET_DIR, "aggregated.json")
OUTPUT_FILE = os.path.join(RESULTS_DIR, "dist_zero_shot_results.json")

# Canonical event type vocabulary — must match tracer/state.go EventType constants.
ALL_EVENT_TYPES = ["GoBlock", "GoCreate", "GoEnd", "GoSched", "GoStart", "GoUnblock"]

# Small constant added to predicted probabilities before log to prevent log(0).
EPSILON = 1e-9


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_aggregated() -> list[dict[str, Any]]:
    """Load aggregated.json produced by Phase 6."""
    with open(AGGREGATED_FILE) as f:
        return json.load(f)


def load_per_run_example(program_id: str, split_percent: int) -> Optional[dict[str, Any]]:
    """Load the first available per-run example for (program_id, split_percent).

    Tries run_index 0..4 in order. Returns None if no file is found (e.g., all
    runs of this program timed out before reaching this split point).
    """
    for run_index in range(5):
        fname = f"{program_id}_run{run_index}_split{split_percent}.json"
        path = os.path.join(DATASET_DIR, fname)
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    return None


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def build_prompt(program_source: str, partial_trace: list[dict[str, Any]]) -> str:
    """Construct the distribution-prediction prompt from a program and its partial trace."""
    trace_json = json.dumps(partial_trace, indent=2)
    current_state_json = json.dumps(partial_trace[-1], indent=2) if partial_trace else "{}"

    return f"""You are reasoning about concurrent Go program execution.

Here is a Go program:
<program>
{program_source}
</program>

Here is a partial execution trace showing goroutine scheduler events so far:
<trace>
{trace_json}
</trace>

The current goroutine states are:
<current_state>
{current_state_json}
</current_state>

Predict the DISTRIBUTION over next scheduler events. All probabilities must sum to 1.0.
Respond ONLY in JSON with exactly these keys — no markdown fences, no text outside the JSON object:
{{"GoBlock": p, "GoCreate": p, "GoEnd": p, "GoSched": p, "GoStart": p, "GoUnblock": p}}"""


# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------


def call_gemini(client: genai.Client, model_name: str, prompt: str, thinking_budget: int = 0) -> str:
    """Call Gemini, returning the raw response text. Retries once on failure."""
    config = genai_types.GenerateContentConfig(
        temperature=0.0,
        max_output_tokens=8192 if thinking_budget != 0 else 256,
        thinking_config=genai_types.ThinkingConfig(thinking_budget=thinking_budget),
    )
    try:
        resp = client.models.generate_content(model=model_name, contents=prompt, config=config)
        return resp.text
    except Exception as first_err:
        time.sleep(2)
        try:
            resp = client.models.generate_content(model=model_name, contents=prompt, config=config)
            return resp.text
        except Exception as second_err:
            raise RuntimeError(f"API call failed after retry: {second_err}") from first_err


# ---------------------------------------------------------------------------
# Parsing and validation
# ---------------------------------------------------------------------------


def parse_distribution(raw: str) -> dict[str, float]:
    """Parse model response into a normalised probability distribution.

    Strips optional markdown fences, validates all six event-type keys are present,
    clamps negative values to 0, and re-normalises if the sum deviates from 1.0.
    """
    text = raw.strip()
    # Strip ```json ... ``` or ``` ... ``` fences if the model added them.
    if text.startswith("```"):
        _, _, rest = text.partition("\n")
        text = rest.rstrip("`").strip()

    data = json.loads(text)

    dist: dict[str, float] = {}
    for et in ALL_EVENT_TYPES:
        dist[et] = max(0.0, float(data.get(et, 0.0)))

    total = sum(dist.values())
    if total <= 0:
        # Degenerate output — fall back to uniform to avoid dividing by zero.
        return {et: 1.0 / len(ALL_EVENT_TYPES) for et in ALL_EVENT_TYPES}
    if abs(total - 1.0) > 0.01:
        dist = {et: v / total for et, v in dist.items()}

    return dist


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def compute_ece(predicted: dict[str, float], empirical: dict[str, float]) -> float:
    """Expected Calibration Error: mean |predicted[et] - empirical[et]| per event type."""
    return float(np.mean([abs(predicted[et] - empirical[et]) for et in ALL_EVENT_TYPES]))


def compute_kl(empirical: dict[str, float], predicted: dict[str, float]) -> float:
    """KL(empirical || predicted) in nats. Uses epsilon smoothing on predicted."""
    p = np.array([empirical[et] for et in ALL_EVENT_TYPES])
    q = np.array([predicted[et] + EPSILON for et in ALL_EVENT_TYPES])
    return float(np.sum(rel_entr(p, q)))


def compute_entropy(dist: dict[str, float]) -> float:
    """Shannon entropy in bits."""
    h = 0.0
    for p in dist.values():
        if p > 0:
            h -= p * math.log2(p)
    return h


# ---------------------------------------------------------------------------
# Phase 4 baseline
# ---------------------------------------------------------------------------


def load_phase4_baseline(
    aggregated_by_key: dict[tuple[str, int], dict[str, Any]],
) -> dict[tuple[str, int], list[float]]:
    """Compute per-(program_id, split_percent) ECE values from Phase 4 point predictions.

    Each Phase 4 prediction is treated as a one-hot distribution over the six event
    types, then compared against the empirical distribution from aggregated.json.
    Returns a mapping from group key to the list of per-run ECE values.
    """
    baseline: dict[tuple[str, int], list[float]] = defaultdict(list)
    for path in sorted(glob.glob(os.path.join(RESULTS_DIR, "*_result.json"))):
        if "dist_zero_shot" in os.path.basename(path):
            continue
        try:
            with open(path) as f:
                r = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if r.get("correct_event_type") is None:
            continue  # deadlock or error — skip
        predicted_et = (r.get("predicted") or {}).get("event_type", "")
        if predicted_et not in ALL_EVENT_TYPES:
            continue
        key = (r["program_id"], r["split_percent"])
        if key not in aggregated_by_key:
            continue
        empirical = aggregated_by_key[key]["next_event_distribution"]
        one_hot = {et: (1.0 if et == predicted_et else 0.0) for et in ALL_EVENT_TYPES}
        baseline[key].append(compute_ece(one_hot, empirical))
    return baseline


# ---------------------------------------------------------------------------
# Main eval loop
# ---------------------------------------------------------------------------


def run_eval(thinking_budget: int = 0) -> None:
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        print("ERROR: GEMINI_API_KEY is not set", file=sys.stderr)
        sys.exit(1)
    model_name = os.getenv("MODEL", "gemini-3.5-flash")

    # Output to a separate file when thinking is enabled so both runs are preserved.
    if thinking_budget != 0:
        label = "auto" if thinking_budget == -1 else str(thinking_budget)
        output_file = os.path.join(RESULTS_DIR, f"dist_zero_shot_thinking{label}_results.json")
    else:
        output_file = OUTPUT_FILE

    client = genai.Client(api_key=api_key)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    aggregated = load_aggregated()
    aggregated_by_key = {(r["program_id"], r["split_percent"]): r for r in aggregated}
    total = len(aggregated)
    thinking_label = f"thinking_budget={thinking_budget}" if thinking_budget != 0 else "thinking disabled"
    print(f"Loaded {total} aggregated groups — model: {model_name} — {thinking_label}")

    results: list[dict[str, Any]] = []
    errors = 0

    for i, group in enumerate(aggregated, 1):
        program_id = group["program_id"]
        split_percent = group["split_percent"]
        empirical = group["next_event_distribution"]
        empirical_h = compute_entropy(empirical)

        example = load_per_run_example(program_id, split_percent)
        if example is None:
            print(f"  [{i:2d}/{total}] SKIP {program_id} split={split_percent}% — no per-run example found")
            errors += 1
            results.append({
                "program_id": program_id,
                "split_percent": split_percent,
                "concurrency_pattern": group["concurrency_pattern"],
                "nondeterminism": group["nondeterminism"],
                "full_outcome": group["full_outcome"],
                "empirical_distribution": empirical,
                "predicted_distribution": None,
                "ece": None,
                "kl_divergence": None,
                "model_entropy": None,
                "empirical_entropy": round(empirical_h, 6),
                "raw_response": None,
                "error": "no per-run example found",
            })
            continue

        prompt = build_prompt(example["program_source"], example["partial_trace"])

        raw = ""
        error_msg: Optional[str] = None
        predicted: Optional[dict[str, float]] = None

        try:
            raw = call_gemini(client, model_name, prompt, thinking_budget)
            predicted = parse_distribution(raw)
        except Exception as exc:
            error_msg = str(exc)
            errors += 1

        ece = kl = model_h = None
        if predicted is not None:
            ece = compute_ece(predicted, empirical)
            kl = compute_kl(empirical, predicted)
            model_h = compute_entropy(predicted)

        results.append({
            "program_id": program_id,
            "split_percent": split_percent,
            "concurrency_pattern": group["concurrency_pattern"],
            "nondeterminism": group["nondeterminism"],
            "full_outcome": group["full_outcome"],
            "empirical_distribution": empirical,
            "predicted_distribution": predicted,
            "ece": round(ece, 6) if ece is not None else None,
            "kl_divergence": round(kl, 6) if kl is not None else None,
            "model_entropy": round(model_h, 6) if model_h is not None else None,
            "empirical_entropy": round(empirical_h, 6),
            "raw_response": raw,
            "error": error_msg,
        })

        if error_msg is None:
            print(
                f"  [{i:2d}/{total}] {program_id:30s} split={split_percent:3d}%  "
                f"ECE={ece:.3f}  KL={kl:.3f}  "
                f"H(pred)={model_h:.2f}b  H(emp)={empirical_h:.2f}b"
            )
        else:
            print(
                f"  [{i:2d}/{total}] {program_id:30s} split={split_percent:3d}%  "
                f"ERROR: {error_msg[:80]}"
            )

    # Write all results.
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults written to {output_file}")

    # --- Summary ---
    scored = [r for r in results if r["ece"] is not None]
    print(f"\n{'='*65}")
    print("=== Phase 7: Distribution Zero-Shot Eval — Summary ===")
    print(f"{'='*65}")
    print(f"  Total groups : {total}")
    print(f"  Scored       : {len(scored)}")
    print(f"  Errors       : {errors}")

    if not scored:
        print("  No scored results — check errors above.")
        return

    mean_ece_p7 = float(np.mean([r["ece"] for r in scored]))
    mean_kl = float(np.mean([r["kl_divergence"] for r in scored]))

    # Phase 4 baseline comparison.
    p4_baseline = load_phase4_baseline(aggregated_by_key)
    p4_all_eces = [ece for eces in p4_baseline.values() for ece in eces]
    mean_ece_p4 = float(np.mean(p4_all_eces)) if p4_all_eces else None

    print(f"\nECE — mean |predicted[et] - empirical[et]| averaged over 6 event types")
    print(f"  (lower is better; baseline uses Phase 4 one-hot point predictions)")
    print(f"  Phase 7 distribution prediction  : {mean_ece_p7:.4f}")
    if mean_ece_p4 is not None:
        delta = mean_ece_p7 - mean_ece_p4
        direction = "worse" if delta > 0 else "better"
        print(f"  Phase 4 one-hot baseline         : {mean_ece_p4:.4f}")
        print(f"  Delta (Phase 7 - Phase 4)        : {delta:+.4f}  ({direction})")
    else:
        print(f"  Phase 4 baseline                 : (not available — run eval/zero_shot.go first)")

    print(f"\nKL divergence KL(empirical || predicted) — mean: {mean_kl:.4f} nats")

    print(f"\nModel entropy vs nondeterminism level:")
    nd_pairs: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for r in scored:
        nd_pairs[r["nondeterminism"]].append((r["model_entropy"], r["empirical_entropy"]))
    for nd in ["high", "medium", "low", "none"]:
        if nd not in nd_pairs:
            continue
        vals = nd_pairs[nd]
        m_model = float(np.mean([v[0] for v in vals]))
        m_emp = float(np.mean([v[1] for v in vals]))
        print(f"  {nd:6s} : model H={m_model:.3f} bits  empirical H={m_emp:.3f} bits  (n={len(vals)})")

    # Key claim: model entropy should be monotonically increasing with nondeterminism level.
    nd_order = ["none", "low", "medium", "high"]
    nd_present = [nd for nd in nd_order if nd in nd_pairs]
    mean_h = {nd: float(np.mean([v[0] for v in nd_pairs[nd]])) for nd in nd_present}
    monotone = all(
        mean_h[nd_present[i]] <= mean_h[nd_present[i + 1]]
        for i in range(len(nd_present) - 1)
    )
    print(f"\n  KEY CLAIM: model entropy increases with nondeterminism level? {monotone}")

    print(f"\nKL divergence by nondeterminism level:")
    kl_by_nd: dict[str, list[float]] = defaultdict(list)
    for r in scored:
        kl_by_nd[r["nondeterminism"]].append(r["kl_divergence"])
    for nd in ["high", "medium", "low", "none"]:
        if nd not in kl_by_nd:
            continue
        vals = kl_by_nd[nd]
        print(f"  {nd:6s} : KL={float(np.mean(vals)):.4f} nats  (n={len(vals)})")

    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 7 — Distribution Zero-Shot Eval")
    parser.add_argument(
        "--thinking-budget",
        type=int,
        default=0,
        metavar="N",
        help="Gemini thinking budget in tokens (0=disabled, -1=auto). Default: 0",
    )
    args = parser.parse_args()
    run_eval(thinking_budget=args.thinking_budget)
