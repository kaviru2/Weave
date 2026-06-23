#!/usr/bin/env python3
"""Phase 18 — empirical numbers for ICSE Research Track paper.

Analyses 1-3 run from local data only (no API, no GPU).
Analyses 4-5 (McNemar tests) require Gemini + Phase13 CE eval files and
will run automatically once those files exist.

Usage:
    uv run python eval/phase18_analysis.py
    uv run python eval/phase18_analysis.py --skip-mcnemar
"""

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import stats
from scipy.stats import bootstrap, binomtest
from statsmodels.stats.contingency_tables import mcnemar as sm_mcnemar

REPO = Path(__file__).parent.parent
RESULTS = REPO / "eval" / "results"
DATA = REPO / "dataset" / "output"

TRAJ_EVAL   = RESULTS / "eval_results_traj_accuracy.json"
GEMINI_EVAL = RESULTS / "gemini_goker_gemini-3_5-flash.json"
P13_EVAL    = RESULTS / "eval_phase13_ce.json"
TRAIN_FILE  = DATA / "train_trajectory.jsonl"
VAL_FILE    = DATA / "val_point_dups.jsonl"

EVENT_TYPES = ["GoBlock", "GoCreate", "GoEnd", "GoSched", "GoStart", "GoUnblock"]


# ── 1. Majority-class baseline ────────────────────────────────────────────────

def majority_class_baseline():
    print("\n=== 1. Majority-Class Baseline ===")
    d = json.loads(TRAJ_EVAL.read_text())
    counts = Counter()
    for ex in d["per_example"]:
        gt = json.loads(ex["ground_truth"]).get("event_type")
        if gt:
            counts[gt] += 1
    total = sum(counts.values())
    majority = counts.most_common(1)[0]
    baseline_acc = majority[1] / total
    print(f"Val set event distribution ({total} examples):")
    for et, c in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {et:12s}: {c:4d}  ({c/total*100:.1f}%)")
    print(f"\nMajority class: {majority[0]} ({majority[1]}/{total} = {baseline_acc*100:.1f}%)")
    print(f"Traj model accuracy: {d['accuracy']*100:.1f}%")
    print(f"Gap over majority baseline: +{(d['accuracy'] - baseline_acc)*100:.1f} pp")
    return {
        "majority_class": majority[0],
        "majority_count": majority[1],
        "total": total,
        "majority_baseline_acc": baseline_acc,
        "traj_acc": d["accuracy"],
        "gap_pp": d["accuracy"] - baseline_acc,
        "val_distribution": dict(counts),
    }


# ── 2. Training frequency analysis ───────────────────────────────────────────

def training_frequency():
    print("\n=== 2. Training Data Frequency Analysis ===")
    train_counts = Counter()
    total_steps = 0
    with open(TRAIN_FILE) as f:
        for line in f:
            ex = json.loads(line)
            for msg in ex.get("messages", []):
                if msg["role"] == "assistant":
                    try:
                        et = json.loads(msg["content"]).get("event_type")
                        if et:
                            train_counts[et] += 1
                            total_steps += 1
                    except Exception:
                        pass

    val_counts = Counter()
    with open(VAL_FILE) as f:
        for line in f:
            ex = json.loads(line)
            for msg in ex.get("messages", []):
                if msg["role"] == "assistant":
                    try:
                        et = json.loads(msg["content"]).get("event_type")
                        if et:
                            val_counts[et] += 1
                    except Exception:
                        pass
    val_total = sum(val_counts.values())

    print(f"Training steps total: {total_steps}")
    print(f"\n{'Event':<12} {'Train #':>8} {'Train %':>8} {'Val #':>8} {'Val %':>8} {'Ratio':>8}")
    print("-" * 60)
    results = {}
    for et in sorted(EVENT_TYPES):
        tc = train_counts.get(et, 0)
        vc = val_counts.get(et, 0)
        tp = tc / total_steps * 100 if total_steps else 0
        vp = vc / val_total * 100 if val_total else 0
        ratio = tp / vp if vp > 0 else float("inf")
        print(f"{et:<12} {tc:>8} {tp:>7.1f}% {vc:>8} {vp:>7.1f}% {ratio:>7.2f}x")
        results[et] = {"train_count": tc, "train_pct": tp, "val_count": vc, "val_pct": vp, "ratio": ratio}

    print("\nUnderrepresented events (train% < val%):")
    for et, v in results.items():
        if v["train_pct"] < v["val_pct"]:
            print(f"  {et}: train {v['train_pct']:.1f}% vs val {v['val_pct']:.1f}%  ({v['ratio']:.2f}x)")

    return {"total_train_steps": total_steps, "by_event": results}


# ── 3. GoStart/GoBlock confusion analysis ────────────────────────────────────

def confusion_analysis():
    print("\n=== 3. GoStart/GoBlock Confusion Analysis ===")
    d = json.loads(TRAJ_EVAL.read_text())

    # Print full confusion matrix
    confusion = d.get("confusion", {})
    print("Confusion matrix (rows=ground truth, cols=predicted):")
    pred_types = sorted({p for row in confusion.values() for p in row})
    header = f"{'GT \\ Pred':<12}" + "".join(f"{p:>12}" for p in pred_types)
    print(header)
    for gt in sorted(confusion.keys()):
        row = confusion[gt]
        total_gt = sum(row.values())
        line = f"{gt:<12}" + "".join(f"{row.get(p, 0):>12}" for p in pred_types)
        print(line)

    # Isolate GoStart↔GoBlock confusions
    gs_pred_gb = confusion.get("GoStart", {}).get("GoBlock", 0)
    gb_pred_gs = confusion.get("GoBlock", {}).get("GoStart", 0)
    print(f"\nGoStart predicted as GoBlock: {gs_pred_gb}")
    print(f"GoBlock predicted as GoStart: {gb_pred_gs}")
    print(f"Total GoStart/GoBlock confusion pairs: {gs_pred_gb + gb_pred_gs}")

    # Analyse preceding event context for confused examples
    confused = []
    for ex in d["per_example"]:
        try:
            gt = json.loads(ex["ground_truth"]).get("event_type")
            pred_raw = ex.get("prediction", "{}")
            pred = json.loads(pred_raw).get("event_type") if pred_raw else None
        except Exception:
            continue
        if (gt == "GoStart" and pred == "GoBlock") or (gt == "GoBlock" and pred == "GoStart"):
            confused.append(ex)

    print(f"\nAnalysing {len(confused)} confused examples for preceding event context...")
    prior_event_counts = Counter()
    for ex in confused:
        # Extract last event from partial trace in user message
        try:
            user_msg = next(
                m["content"] for m in json.loads(
                    open(VAL_FILE).read().split('\n')[ex["index"]]
                ).get("messages", []) if m["role"] == "user"
            )
            # Find last event_type in trace JSON
            matches = re.findall(r'"event_type"\s*:\s*"(\w+)"', user_msg)
            if matches:
                prior_event_counts[matches[-1]] += 1
            else:
                prior_event_counts["unknown"] += 1
        except Exception:
            prior_event_counts["parse_error"] += 1

    if prior_event_counts:
        total_confused = len(confused)
        print(f"Preceding event type in confused examples:")
        for evt, cnt in sorted(prior_event_counts.items(), key=lambda x: -x[1]):
            print(f"  {evt:<14}: {cnt:3d} ({cnt/total_confused*100:.1f}%)")

    return {
        "gs_pred_gb": gs_pred_gb,
        "gb_pred_gs": gb_pred_gs,
        "total_confused": gs_pred_gb + gb_pred_gs,
        "prior_event_in_confusion": dict(prior_event_counts),
    }


# ── 4+5. McNemar tests ────────────────────────────────────────────────────────

def mcnemar_test(name_a, matches_a, name_b, matches_b):
    """Paired McNemar test between two models on the same examples."""
    assert len(matches_a) == len(matches_b), "Must have same number of examples"
    n = len(matches_a)
    # Contingency: b01 = A wrong B right, b10 = A right B wrong
    b01 = sum(1 for a, b in zip(matches_a, matches_b) if not a and b)
    b10 = sum(1 for a, b in zip(matches_a, matches_b) if a and not b)
    b11 = sum(1 for a, b in zip(matches_a, matches_b) if a and b)
    b00 = sum(1 for a, b in zip(matches_a, matches_b) if not a and not b)

    # McNemar's exact test
    table = np.array([[b11, b10], [b01, b00]])
    result = sm_mcnemar(table, exact=True)

    # Bootstrap CI on accuracy difference
    acc_a = sum(matches_a) / n
    acc_b = sum(matches_b) / n
    diffs = np.array(matches_a, dtype=float) - np.array(matches_b, dtype=float)

    def mean_diff(x, axis):
        return np.mean(x, axis=axis)

    bs = bootstrap((diffs,), mean_diff, n_resamples=10000, confidence_level=0.95, random_state=42)
    ci_low, ci_high = bs.confidence_interval

    print(f"\n  {name_a} ({acc_a*100:.1f}%) vs {name_b} ({acc_b*100:.1f}%)")
    print(f"  Contingency: both_correct={b11}, A_only={b10}, B_only={b01}, neither={b00}")
    print(f"  McNemar p-value: {result.pvalue:.4f} {'✅ significant' if result.pvalue < 0.05 else '❌ not significant'} (α=0.05)")
    print(f"  Accuracy difference: {(acc_a-acc_b)*100:+.1f} pp")
    print(f"  95% bootstrap CI: [{ci_low*100:+.2f}, {ci_high*100:+.2f}] pp")

    return {
        "acc_a": float(acc_a), "acc_b": float(acc_b),
        "diff_pp": float(acc_a - acc_b),
        "mcnemar_pvalue": float(result.pvalue),
        "significant": bool(result.pvalue < 0.05),
        "ci_95": [float(ci_low), float(ci_high)],
        "b11": int(b11), "b10": int(b10), "b01": int(b01), "b00": int(b00),
    }


def run_mcnemar_tests():
    print("\n=== 4+5. McNemar Statistical Significance Tests ===")
    results = {}

    traj_d = json.loads(TRAJ_EVAL.read_text())
    traj_matches = [ex["match"] for ex in traj_d["per_example"]]

    # vs Gemini
    if GEMINI_EVAL.exists():
        g = json.loads(GEMINI_EVAL.read_text())
        g_matches = [ex["match"] for ex in g["per_example"]]
        results["traj_vs_gemini"] = mcnemar_test(
            "Traj model (40.1%)", traj_matches,
            "Gemini 3.5 Flash", g_matches,
        )
    else:
        print(f"\n  Skipping traj vs Gemini — {GEMINI_EVAL} not found")

    # vs Phase 13 CE
    if P13_EVAL.exists():
        p = json.loads(P13_EVAL.read_text())
        p_matches = [ex["match"] for ex in p["per_example"]]
        results["traj_vs_phase13"] = mcnemar_test(
            "Traj model (40.1%)", traj_matches,
            "Phase 13 CE (36.2%)", p_matches,
        )
    else:
        print(f"\n  Skipping traj vs Phase13 CE — {P13_EVAL} not found")

    return results


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-mcnemar", action="store_true")
    args = parser.parse_args()

    all_results = {}
    all_results["majority_baseline"]    = majority_class_baseline()
    all_results["training_frequency"]   = training_frequency()
    all_results["confusion_analysis"]   = confusion_analysis()

    if not args.skip_mcnemar:
        all_results["mcnemar"] = run_mcnemar_tests()

    out = RESULTS / "phase18_numbers.json"
    out.write_text(json.dumps(all_results, indent=2))
    print(f"\n✅  All results saved to {out}")


if __name__ == "__main__":
    main()
