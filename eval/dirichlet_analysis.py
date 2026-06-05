#!/usr/bin/env python3
"""
Phase 8 — Dirichlet-Categorical Analysis

Analyses Phase 7 model predictions and Phase 6 empirical distributions to produce
the three key paper findings:

  1. ECE improvement — distribution+thinking reduces calibration error vs point-prediction
  2. Entropy-nondeterminism correlation — Spearman rho between model entropy and
     nondeterminism level (with thinking budget)
  3. Anomaly detection — KL(predicted || uniform) as an unsupervised bug signal;
     does it separate success from buggy (leak/race) programs?

Also produces:
  - Leak/deadlock distribution signatures: P(GoBlock) and P(GoUnblock) in empirical
    data by outcome class and trace depth
  - Model entropy vs trace depth (25/50/75%) — does seeing more trace reduce uncertainty?

No API calls. Pure analysis of existing result files.

Output: eval/results/dirichlet_analysis.json
Run:    uv run python eval/dirichlet_analysis.py
"""

import json
import math
import os
import sys
from collections import defaultdict
from typing import Any, Optional

import numpy as np
from scipy import stats

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

EVAL_DIR = os.path.dirname(__file__)
RESULTS_DIR = os.path.join(EVAL_DIR, "results")
DATASET_DIR = os.path.join(EVAL_DIR, "..", "dataset", "output")

THINKING_RESULTS = os.path.join(RESULTS_DIR, "dist_zero_shot_thinking1024_results.json")
BASELINE_RESULTS = os.path.join(RESULTS_DIR, "dist_zero_shot_results.json")
AGGREGATED_FILE = os.path.join(DATASET_DIR, "aggregated.json")
OUTPUT_FILE = os.path.join(RESULTS_DIR, "dirichlet_analysis.json")

ALL_EVENT_TYPES = ["GoBlock", "GoCreate", "GoEnd", "GoSched", "GoStart", "GoUnblock"]
EPSILON = 1e-9

# Ordinal encoding for nondeterminism levels used in Spearman correlation.
ND_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_results(path: str) -> list[dict[str, Any]]:
    """Load Phase 7 dist_zero_shot results JSON."""
    with open(path) as f:
        return json.load(f)


def load_aggregated() -> list[dict[str, Any]]:
    """Load Phase 6 aggregated.json."""
    with open(AGGREGATED_FILE) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Core metrics
# ---------------------------------------------------------------------------


def kl_from_uniform(dist: dict[str, float]) -> float:
    """KL(dist || uniform) in nats — measures how far the distribution is from uniform.

    High value: model is confident (concentrated mass).
    Low value: model is uncertain (close to uniform).
    Uses EPSILON smoothing to handle zero-probability mass.
    """
    n = len(ALL_EVENT_TYPES)
    uniform = 1.0 / n
    total = 0.0
    for et in ALL_EVENT_TYPES:
        p = dist.get(et, 0.0) + EPSILON
        total += p * math.log(p / uniform)
    return total


def entropy_bits(dist: dict[str, float]) -> float:
    """Shannon entropy in bits."""
    h = 0.0
    for p in dist.values():
        if p > 0:
            h -= p * math.log2(p)
    return h


def cohens_d(a: list[float], b: list[float]) -> float:
    """Cohen's d effect size between two groups."""
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    mean_diff = np.mean(a) - np.mean(b)
    pooled_std = math.sqrt((np.var(a, ddof=1) + np.var(b, ddof=1)) / 2)
    if pooled_std == 0:
        return float("nan")
    return float(mean_diff / pooled_std)


# ---------------------------------------------------------------------------
# Analysis 1 — Anomaly scores
# ---------------------------------------------------------------------------


def compute_anomaly_scores(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add anomaly_score = KL(predicted || uniform) to each scored record."""
    enriched = []
    for r in results:
        rec = dict(r)
        if r.get("predicted_distribution") is not None:
            rec["anomaly_score"] = round(kl_from_uniform(r["predicted_distribution"]), 6)
        else:
            rec["anomaly_score"] = None
        enriched.append(rec)
    return enriched


def analysis_anomaly_by_outcome(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Mean anomaly score (KL(pred||uniform)) grouped by full_outcome.

    Returns a dict with per-outcome statistics and a success vs buggy comparison.
    """
    by_outcome: dict[str, list[float]] = defaultdict(list)
    for r in records:
        if r.get("anomaly_score") is not None:
            by_outcome[r["full_outcome"]].append(r["anomaly_score"])

    per_outcome: dict[str, dict[str, float]] = {}
    for outcome, vals in sorted(by_outcome.items()):
        per_outcome[outcome] = {
            "mean": round(float(np.mean(vals)), 4),
            "std": round(float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0, 4),
            "n": len(vals),
        }

    # Buggy = leak + race; success = success.
    success_vals = by_outcome.get("success", [])
    buggy_vals = by_outcome.get("leak", []) + by_outcome.get("race", [])

    comparison: dict[str, Any] = {}
    if success_vals and buggy_vals:
        t_stat, p_val = stats.ttest_ind(success_vals, buggy_vals, equal_var=False)
        comparison = {
            "success_mean": round(float(np.mean(success_vals)), 4),
            "buggy_mean": round(float(np.mean(buggy_vals)), 4),
            "cohens_d": round(cohens_d(success_vals, buggy_vals), 4),
            "t_statistic": round(float(t_stat), 4),
            "p_value": round(float(p_val), 4),
            "n_success": len(success_vals),
            "n_buggy": len(buggy_vals),
        }

    return {"by_outcome": per_outcome, "success_vs_buggy": comparison}


# ---------------------------------------------------------------------------
# Analysis 2 — Leak/deadlock distribution signature
# ---------------------------------------------------------------------------


def analysis_leak_signature(
    aggregated: list[dict[str, Any]],
) -> dict[str, Any]:
    """P(GoBlock) and P(GoUnblock) in empirical distributions, by outcome × split_percent.

    Checks the reframed collapse claim: leak programs show P(GoUnblock)=0 consistently,
    and P(GoBlock) trends higher vs success programs.
    """
    # Collect per-record values: {outcome: {split_percent: [P(GoBlock), ...]}}
    goblock_by: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    gounblock_by: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))

    for rec in aggregated:
        outcome = rec["full_outcome"]
        sp = rec["split_percent"]
        d = rec["next_event_distribution"]
        goblock_by[outcome][sp].append(d["GoBlock"])
        gounblock_by[outcome][sp].append(d["GoUnblock"])

    # Summarise
    signature: dict[str, Any] = {}
    for outcome in sorted(goblock_by.keys()):
        signature[outcome] = {}
        for sp in sorted(goblock_by[outcome].keys()):
            gb_vals = goblock_by[outcome][sp]
            gu_vals = gounblock_by[outcome][sp]
            signature[outcome][sp] = {
                "mean_P_GoBlock": round(float(np.mean(gb_vals)), 4),
                "mean_P_GoUnblock": round(float(np.mean(gu_vals)), 4),
                "all_GoUnblock_zero": all(v == 0.0 for v in gu_vals),
                "n": len(gb_vals),
            }

    # Spearman: split_percent vs P(GoBlock), separately for leak/race vs success.
    def _spearman_depth_goblock(outcome_list: list[str]) -> dict[str, float]:
        sp_vals, pb_vals = [], []
        for rec in aggregated:
            if rec["full_outcome"] in outcome_list:
                sp_vals.append(rec["split_percent"])
                pb_vals.append(rec["next_event_distribution"]["GoBlock"])
        if len(sp_vals) < 3:
            return {"rho": float("nan"), "p_value": float("nan"), "n": len(sp_vals)}
        rho, pval = stats.spearmanr(sp_vals, pb_vals)
        return {"rho": round(float(rho), 4), "p_value": round(float(pval), 4), "n": len(sp_vals)}

    return {
        "by_outcome_split": signature,
        "spearman_depth_vs_goblock": {
            "leak_race": _spearman_depth_goblock(["leak", "race"]),
            "success": _spearman_depth_goblock(["success"]),
        },
    }


# ---------------------------------------------------------------------------
# Analysis 3 — Entropy vs trace depth
# ---------------------------------------------------------------------------


def analysis_entropy_vs_depth(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Model entropy and empirical entropy grouped by split_percent (25/50/75).

    Checks whether model entropy decreases as trace deepens (model grows more
    confident with more observed context).
    """
    model_h_by_depth: dict[int, list[float]] = defaultdict(list)
    emp_h_by_depth: dict[int, list[float]] = defaultdict(list)

    # Also stratify by nondeterminism level.
    model_h_by_nd_depth: dict[str, dict[int, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for r in records:
        if r.get("model_entropy") is None:
            continue
        sp = r["split_percent"]
        model_h_by_depth[sp].append(r["model_entropy"])
        emp_h_by_depth[sp].append(r["empirical_entropy"])
        model_h_by_nd_depth[r["nondeterminism"]][sp].append(r["model_entropy"])

    # Overall summary by depth.
    depth_summary: dict[int, dict[str, float]] = {}
    for sp in sorted(model_h_by_depth.keys()):
        mh = model_h_by_depth[sp]
        eh = emp_h_by_depth[sp]
        depth_summary[sp] = {
            "mean_model_entropy": round(float(np.mean(mh)), 4),
            "mean_empirical_entropy": round(float(np.mean(eh)), 4),
            "n": len(mh),
        }

    # Monotonicity check: does model entropy decrease as depth increases?
    depths = sorted(depth_summary.keys())
    model_h_seq = [depth_summary[d]["mean_model_entropy"] for d in depths]
    monotone_decreasing = all(
        model_h_seq[i] >= model_h_seq[i + 1] for i in range(len(model_h_seq) - 1)
    )

    # Spearman: split_percent vs model_entropy (should be negative if model grows more confident).
    all_sp = [r["split_percent"] for r in records if r.get("model_entropy") is not None]
    all_mh = [r["model_entropy"] for r in records if r.get("model_entropy") is not None]
    rho, pval = stats.spearmanr(all_sp, all_mh) if len(all_sp) >= 3 else (float("nan"), float("nan"))

    # Nondeterminism × depth breakdown.
    nd_depth: dict[str, dict[int, float]] = {}
    for nd, depth_map in sorted(model_h_by_nd_depth.items()):
        nd_depth[nd] = {
            sp: round(float(np.mean(vals)), 4)
            for sp, vals in sorted(depth_map.items())
        }

    return {
        "by_depth": depth_summary,
        "monotone_decreasing": monotone_decreasing,
        "spearman_depth_vs_model_entropy": {
            "rho": round(float(rho), 4),
            "p_value": round(float(pval), 4),
            "n": len(all_sp),
        },
        "by_nondeterminism_and_depth": nd_depth,
    }


# ---------------------------------------------------------------------------
# Paper Finding 2 — Spearman entropy-nondeterminism correlation
# ---------------------------------------------------------------------------


def compute_spearman_nd_entropy(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Spearman rho between nondeterminism ordinal rank and model entropy."""
    pairs = [
        (ND_RANK[r["nondeterminism"]], r["model_entropy"])
        for r in records
        if r.get("model_entropy") is not None and r["nondeterminism"] in ND_RANK
    ]
    if len(pairs) < 3:
        return {"rho": float("nan"), "p_value": float("nan"), "n": len(pairs)}
    nd_ranks, entropies = zip(*pairs)
    rho, pval = stats.spearmanr(nd_ranks, entropies)
    return {
        "rho": round(float(rho), 4),
        "p_value": round(float(pval), 4),
        "n": len(pairs),
    }


# ---------------------------------------------------------------------------
# Paper Finding 1 — ECE recomputation for comparison table
# ---------------------------------------------------------------------------


def ece_from_results(results: list[dict[str, Any]]) -> Optional[float]:
    """Mean ECE from a Phase 7 results list (thinking or baseline)."""
    vals = [r["ece"] for r in results if r.get("ece") is not None]
    return round(float(np.mean(vals)), 4) if vals else None


def compute_phase4_ece(aggregated: list[dict[str, Any]]) -> Optional[float]:
    """Recompute Phase 4 point-prediction ECE by treating each prediction as one-hot.

    Scans *_result.json files in RESULTS_DIR (excluding dist_zero_shot variants),
    matches them to empirical distributions from aggregated.json, and computes
    mean |one_hot[et] - empirical[et]| per event type.
    """
    import glob
    aggregated_by_key = {(r["program_id"], r["split_percent"]): r for r in aggregated}
    eces: list[float] = []
    for path in sorted(glob.glob(os.path.join(RESULTS_DIR, "*_result.json"))):
        if "dist_zero_shot" in os.path.basename(path):
            continue
        try:
            with open(path) as f:
                r = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        predicted_et = (r.get("predicted") or {}).get("event_type", "")
        if predicted_et not in ALL_EVENT_TYPES:
            continue
        key = (r["program_id"], r["split_percent"])
        if key not in aggregated_by_key:
            continue
        empirical = aggregated_by_key[key]["next_event_distribution"]
        one_hot = {et: (1.0 if et == predicted_et else 0.0) for et in ALL_EVENT_TYPES}
        eces.append(float(np.mean([abs(one_hot[et] - empirical[et]) for et in ALL_EVENT_TYPES])))
    return round(float(np.mean(eces)), 4) if eces else None


# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------


def _sep(char: str = "=", width: int = 65) -> str:
    return char * width


def print_three_paper_findings(
    thinking_records: list[dict[str, Any]],
    baseline_records: list[dict[str, Any]],
    aggregated: list[dict[str, Any]],
    anomaly_analysis: dict[str, Any],
    spearman_nd: dict[str, Any],
    ece_p4: Optional[float] = None,
) -> None:
    """Print the three key paper findings in a clean summary."""
    print()
    print(_sep())
    print("=== THREE KEY PAPER FINDINGS ===")
    print(_sep())

    # --- Finding 1: ECE improvement ---
    ece_thinking = ece_from_results(thinking_records)
    ece_base_p7 = ece_from_results(baseline_records)

    print()
    print("FINDING 1 — Distribution framing reduces calibration error")
    print(f"  Phase 4 point-prediction ECE  : {ece_p4 if ece_p4 is not None else 'N/A'}")
    print(f"  Phase 7 no-thinking ECE       : {ece_base_p7 if ece_base_p7 is not None else 'N/A'}")
    print(f"  Phase 7 thinking=1024 ECE     : {ece_thinking if ece_thinking is not None else 'N/A'}")
    if ece_p4 and ece_thinking:
        delta = ece_thinking - ece_p4
        pct = 100 * abs(delta) / ece_p4
        direction = "improvement" if delta < 0 else "regression"
        print(f"  Delta (thinking - P4 baseline): {delta:+.4f}  ({pct:.1f}% {direction})")

    # --- Finding 2: Entropy-nondeterminism correlation ---
    print()
    print("FINDING 2 — Model entropy tracks nondeterminism level")
    print(f"  Spearman rho (nondeterminism rank vs model entropy, thinking=1024):")
    print(f"    rho={spearman_nd['rho']:.3f}  p={spearman_nd['p_value']:.3f}  n={spearman_nd['n']}")
    if abs(spearman_nd["rho"]) >= 0.4:
        print(f"    => Moderate-to-strong positive correlation (|rho| >= 0.4): claim SUPPORTED")
    elif abs(spearman_nd["rho"]) >= 0.2:
        print(f"    => Weak positive correlation (|rho| < 0.4): claim PARTIALLY supported")
    else:
        print(f"    => No meaningful correlation: claim NOT supported by this metric")

    # --- Finding 3: Anomaly detection ---
    print()
    print("FINDING 3 — Anomaly scores as unsupervised bug signal")
    comp = anomaly_analysis.get("success_vs_buggy", {})
    if comp:
        print(
            f"  Mean KL(pred||uniform) — success: {comp['success_mean']:.4f}  "
            f"buggy (leak+race): {comp['buggy_mean']:.4f}"
        )
        print(
            f"  Cohen's d: {comp['cohens_d']:.3f}  "
            f"t={comp['t_statistic']:.3f}  p={comp['p_value']:.3f}  "
            f"(n_success={comp['n_success']}, n_buggy={comp['n_buggy']})"
        )
        d = abs(comp["cohens_d"])
        if not math.isnan(d):
            if d >= 0.8:
                print(f"    => Large effect size (|d| >= 0.8): anomaly detection claim SUPPORTED")
            elif d >= 0.5:
                print(f"    => Medium effect size (|d| >= 0.5): anomaly detection claim PARTIALLY supported")
            elif d >= 0.2:
                print(f"    => Small effect size (|d| >= 0.2): weak signal")
            else:
                print(f"    => Negligible effect size: anomaly detection claim NOT supported")
        if comp["p_value"] < 0.05:
            print(f"    => Statistically significant (p < 0.05)")
        else:
            print(f"    => Not statistically significant (p >= 0.05)")
    else:
        print("  (insufficient buggy/success split for comparison)")
    print()


# ---------------------------------------------------------------------------
# Print intermediate analysis results
# ---------------------------------------------------------------------------


def print_anomaly_analysis(anomaly_analysis: dict[str, Any]) -> None:
    print(_sep("-"))
    print("ANOMALY SCORES — KL(predicted || uniform) by outcome")
    print(_sep("-"))
    for outcome, stats_d in sorted(anomaly_analysis["by_outcome"].items()):
        print(
            f"  {outcome:10s} : mean={stats_d['mean']:.4f}  "
            f"std={stats_d['std']:.4f}  n={stats_d['n']}"
        )
    comp = anomaly_analysis.get("success_vs_buggy", {})
    if comp:
        print(
            f"\n  Success vs buggy (leak+race): "
            f"Cohen's d={comp['cohens_d']:.3f}  p={comp['p_value']:.3f}"
        )


def print_leak_signature(sig: dict[str, Any]) -> None:
    print()
    print(_sep("-"))
    print("DISTRIBUTION SIGNATURES — P(GoBlock) and P(GoUnblock) by outcome × depth")
    print(_sep("-"))
    for outcome, depth_map in sorted(sig["by_outcome_split"].items()):
        print(f"\n  [{outcome}]")
        for sp in sorted(depth_map.keys()):
            entry = depth_map[sp]
            unblock_str = "(ALL ZERO)" if entry["all_GoUnblock_zero"] else ""
            print(
                f"    split={sp:3d}%  P(GoBlock)={entry['mean_P_GoBlock']:.3f}  "
                f"P(GoUnblock)={entry['mean_P_GoUnblock']:.3f}  {unblock_str}  n={entry['n']}"
            )

    print("\n  Spearman rho (split_percent vs P(GoBlock)):")
    for group, result in sorted(sig["spearman_depth_vs_goblock"].items()):
        print(
            f"    {group:12s} : rho={result['rho']:.3f}  "
            f"p={result['p_value']:.3f}  n={result['n']}"
        )


def print_entropy_vs_depth(depth_analysis: dict[str, Any]) -> None:
    print()
    print(_sep("-"))
    print("MODEL ENTROPY vs TRACE DEPTH")
    print(_sep("-"))
    for sp, entry in sorted(depth_analysis["by_depth"].items()):
        print(
            f"  split={sp:3d}%  "
            f"model H={entry['mean_model_entropy']:.3f} bits  "
            f"empirical H={entry['mean_empirical_entropy']:.3f} bits  "
            f"n={entry['n']}"
        )
    print(
        f"\n  Monotone decreasing (more trace → lower entropy): "
        f"{depth_analysis['monotone_decreasing']}"
    )
    sp_rho = depth_analysis["spearman_depth_vs_model_entropy"]
    print(
        f"  Spearman rho (depth vs model entropy): "
        f"rho={sp_rho['rho']:.3f}  p={sp_rho['p_value']:.3f}  n={sp_rho['n']}"
    )

    print("\n  Model entropy by nondeterminism level and depth (mean bits):")
    nd_depth = depth_analysis["by_nondeterminism_and_depth"]
    header = "  {:8s}".format("nd\\split") + "".join(f"  {sp:5d}%" for sp in [25, 50, 75])
    print(header)
    for nd in ["high", "medium", "low", "none"]:
        if nd not in nd_depth:
            continue
        row = f"  {nd:8s}"
        for sp in [25, 50, 75]:
            val = nd_depth[nd].get(sp)
            row += f"  {val:.3f} " if val is not None else "    N/A"
        print(row)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    # Check required files exist.
    missing = [
        p for p in [THINKING_RESULTS, BASELINE_RESULTS, AGGREGATED_FILE]
        if not os.path.exists(p)
    ]
    if missing:
        for p in missing:
            print(f"ERROR: required file not found: {p}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading Phase 7 thinking results : {THINKING_RESULTS}")
    thinking_records = load_results(THINKING_RESULTS)
    print(f"  {len(thinking_records)} records")

    print(f"Loading Phase 7 baseline results : {BASELINE_RESULTS}")
    baseline_records = load_results(BASELINE_RESULTS)
    print(f"  {len(baseline_records)} records")

    print(f"Loading Phase 6 aggregated data  : {AGGREGATED_FILE}")
    aggregated = load_aggregated()
    print(f"  {len(aggregated)} aggregated groups")

    # Enrich thinking records with anomaly scores.
    thinking_records = compute_anomaly_scores(thinking_records)
    scored = [r for r in thinking_records if r.get("anomaly_score") is not None]
    print(f"\n  Scored (thinking=1024) : {len(scored)} / {len(thinking_records)}")

    # Run analyses.
    print("\n" + _sep())
    print("=== Phase 8: Dirichlet-Categorical Analysis ===")
    print(_sep())

    anomaly_analysis = analysis_anomaly_by_outcome(scored)
    print_anomaly_analysis(anomaly_analysis)

    leak_sig = analysis_leak_signature(aggregated)
    print_leak_signature(leak_sig)

    depth_analysis = analysis_entropy_vs_depth(scored)
    print_entropy_vs_depth(depth_analysis)

    spearman_nd = compute_spearman_nd_entropy(scored)
    print()
    print(_sep("-"))
    print("ENTROPY-NONDETERMINISM CORRELATION (thinking=1024)")
    print(_sep("-"))
    print(
        f"  Spearman rho={spearman_nd['rho']:.3f}  "
        f"p={spearman_nd['p_value']:.3f}  n={spearman_nd['n']}"
    )

    ece_p4 = compute_phase4_ece(aggregated)
    print_three_paper_findings(
        thinking_records, baseline_records, aggregated, anomaly_analysis, spearman_nd, ece_p4
    )

    # Write output JSON.
    os.makedirs(RESULTS_DIR, exist_ok=True)
    output = {
        "phase": 8,
        "inputs": {
            "thinking_results": THINKING_RESULTS,
            "baseline_results": BASELINE_RESULTS,
            "aggregated": AGGREGATED_FILE,
        },
        "anomaly_scores_by_outcome": anomaly_analysis,
        "leak_distribution_signature": leak_sig,
        "entropy_vs_depth": depth_analysis,
        "spearman_nd_entropy": spearman_nd,
        "ece_comparison": {
            "phase4_one_hot": ece_p4,
            "phase7_no_thinking": ece_from_results(baseline_records),
            "phase7_thinking1024": ece_from_results(thinking_records),
        },
        "per_record": [
            {
                "program_id": r["program_id"],
                "split_percent": r["split_percent"],
                "concurrency_pattern": r["concurrency_pattern"],
                "nondeterminism": r["nondeterminism"],
                "full_outcome": r["full_outcome"],
                "anomaly_score": r.get("anomaly_score"),
                "ece": r.get("ece"),
                "kl_divergence": r.get("kl_divergence"),
                "model_entropy": r.get("model_entropy"),
                "empirical_entropy": r.get("empirical_entropy"),
            }
            for r in thinking_records
        ],
    }
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Results written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
