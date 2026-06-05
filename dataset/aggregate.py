#!/usr/bin/env python3
"""
Phase 6 — Dataset Aggregation

Reads per-run eval examples from dataset/output/*.json (212 examples), groups by
(program_id, split_percent), and computes empirical next-event distributions +
Dirichlet posteriors. Outputs dataset/output/aggregated.json.

Key approximation: "same split_percent" is used as a proxy for "same trace prefix
family" across runs. Partial traces across runs are not identical (concurrent programs
are nondeterministic), so this groups structurally similar prefix lengths, not
byte-identical prefixes. Acknowledged as an approximation in the paper.
"""

import json
import math
import os
import sys
from collections import defaultdict
from typing import Any

DATASET_DIR = os.path.join(os.path.dirname(__file__), "output")
OUTPUT_FILE = os.path.join(DATASET_DIR, "aggregated.json")

# Canonical event type vocabulary — must match tracer/state.go EventType constants
ALL_EVENT_TYPES = ["GoBlock", "GoCreate", "GoEnd", "GoSched", "GoStart", "GoUnblock"]

# Jeffreys prior for Dirichlet — principled for small samples (K=6 categories)
JEFFREYS_ALPHA = 0.5


def load_examples(dataset_dir: str) -> list[dict[str, Any]]:
    """Load all per-run JSON examples, skipping directories and aggregated output."""
    examples = []
    for fname in sorted(os.listdir(dataset_dir)):
        if not fname.endswith(".json") or fname == "aggregated.json":
            continue
        path = os.path.join(dataset_dir, fname)
        with open(path) as f:
            try:
                examples.append(json.load(f))
            except json.JSONDecodeError as e:
                print(f"  WARNING: skipping {fname}: {e}", file=sys.stderr)
    return examples


def empirical_distribution(counts: dict[str, int]) -> dict[str, float]:
    """Normalise raw counts to a probability distribution over ALL_EVENT_TYPES."""
    total = sum(counts.values())
    if total == 0:
        # Uniform fallback — should not happen if group has at least one next_event
        n = len(ALL_EVENT_TYPES)
        return {k: 1.0 / n for k in ALL_EVENT_TYPES}
    return {k: counts.get(k, 0) / total for k in ALL_EVENT_TYPES}


def dirichlet_posterior(counts: dict[str, int], alpha: float = JEFFREYS_ALPHA) -> dict[str, float]:
    """Compute Dirichlet posterior parameters: alpha_post[k] = alpha + observed_count[k]."""
    return {k: alpha + counts.get(k, 0) for k in ALL_EVENT_TYPES}


def entropy(dist: dict[str, float]) -> float:
    """Shannon entropy in bits."""
    h = 0.0
    for p in dist.values():
        if p > 0:
            h -= p * math.log2(p)
    return h


def aggregate(examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group examples and compute distributions. Returns aggregated records."""
    # Group by (program_id, split_percent)
    groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for ex in examples:
        if ex.get("next_event") is None:
            # Deadlocked programs have no next event — skip from distribution
            continue
        key = (ex["program_id"], ex["split_percent"])
        groups[key].append(ex)

    aggregated = []
    for (program_id, split_percent), group in sorted(groups.items()):
        # Count observed next_event types across all runs in this group
        counts: dict[str, int] = defaultdict(int)
        for ex in group:
            etype = ex["next_event"].get("event_type", "")
            if etype in ALL_EVENT_TYPES:
                counts[etype] += 1

        # Derive metadata from first example in group (stable across runs)
        first = group[0]
        run_count = len(group)

        emp_dist = empirical_distribution(counts)
        dir_post = dirichlet_posterior(counts)

        aggregated.append({
            "program_id": program_id,
            "split_percent": split_percent,
            "concurrency_pattern": first.get("concurrency_pattern", "unknown"),
            "nondeterminism": first.get("nondeterminism", "unknown"),
            "full_outcome": first.get("full_outcome", "unknown"),
            "run_count": run_count,
            "observed_counts": dict(counts),
            "next_event_distribution": emp_dist,
            "dirichlet_posterior": dir_post,
        })

    return aggregated


def print_exploratory_analysis(aggregated: list[dict[str, Any]]) -> None:
    """Print per-group distributions; highlight distribution collapse in deadlock programs."""
    print("\n" + "=" * 70)
    print("EXPLORATORY ANALYSIS — Empirical Next-Event Distributions")
    print("=" * 70)

    # Group by outcome for summary sections
    by_outcome: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in aggregated:
        by_outcome[rec["full_outcome"]].append(rec)

    # --- Distribution collapse check: deadlock programs ---
    print("\n--- DEADLOCK / TIMEOUT PROGRAMS (expect P(GoBlock) → 1) ---")
    deadlock_records = by_outcome.get("deadlock", []) + by_outcome.get("leak", [])
    if not deadlock_records:
        print("  (no deadlock/leak programs in aggregated set)")
    for rec in sorted(deadlock_records, key=lambda r: (r["program_id"], r["split_percent"])):
        d = rec["next_event_distribution"]
        h = entropy(d)
        top = max(d, key=d.get)
        print(
            f"  {rec['program_id']:30s}  split={rec['split_percent']:3d}%  "
            f"P(GoBlock)={d['GoBlock']:.2f}  P(GoUnblock)={d['GoUnblock']:.2f}  "
            f"top={top}  H={h:.2f} bits  n={rec['run_count']}"
        )

    # --- High-nondeterminism programs ---
    print("\n--- HIGH-NONDETERMINISM PROGRAMS (expect high entropy) ---")
    high_nd = [r for r in aggregated if r["nondeterminism"] == "high"]
    if not high_nd:
        print("  (none)")
    for rec in sorted(high_nd, key=lambda r: (r["program_id"], r["split_percent"])):
        d = rec["next_event_distribution"]
        h = entropy(d)
        top = max(d, key=d.get)
        print(
            f"  {rec['program_id']:30s}  split={rec['split_percent']:3d}%  "
            f"top={top}({d[top]:.2f})  H={h:.2f} bits  n={rec['run_count']}"
        )

    # --- Low-nondeterminism programs ---
    print("\n--- LOW/NONE-NONDETERMINISM PROGRAMS (expect low entropy / deterministic) ---")
    low_nd = [r for r in aggregated if r["nondeterminism"] in ("low", "none")]
    if not low_nd:
        print("  (none)")
    for rec in sorted(low_nd, key=lambda r: (r["program_id"], r["split_percent"])):
        d = rec["next_event_distribution"]
        h = entropy(d)
        top = max(d, key=d.get)
        print(
            f"  {rec['program_id']:30s}  split={rec['split_percent']:3d}%  "
            f"top={top}({d[top]:.2f})  H={h:.2f} bits  n={rec['run_count']}"
        )

    # --- Summary statistics ---
    print("\n--- SUMMARY ---")
    all_h = [entropy(r["next_event_distribution"]) for r in aggregated]
    nd_groups: dict[str, list[float]] = defaultdict(list)
    for r in aggregated:
        nd_groups[r["nondeterminism"]].append(entropy(r["next_event_distribution"]))

    print(f"  Total aggregated groups : {len(aggregated)}")
    print(f"  Mean entropy (all)      : {sum(all_h)/len(all_h):.3f} bits")
    for nd_level, hs in sorted(nd_groups.items()):
        print(f"  Mean entropy ({nd_level:6s})  : {sum(hs)/len(hs):.3f} bits  (n={len(hs)})")

    # Key claim check
    print("\n  KEY CLAIM CHECK — deadlock distribution collapse:")
    deadlock_goblocks = [
        r["next_event_distribution"]["GoBlock"]
        for r in aggregated
        if r["full_outcome"] in ("deadlock", "leak")
    ]
    success_goblocks = [
        r["next_event_distribution"]["GoBlock"]
        for r in aggregated
        if r["full_outcome"] == "success"
    ]
    if deadlock_goblocks:
        print(f"    Mean P(GoBlock) | deadlock/leak : {sum(deadlock_goblocks)/len(deadlock_goblocks):.3f}")
    if success_goblocks:
        print(f"    Mean P(GoBlock) | success       : {sum(success_goblocks)/len(success_goblocks):.3f}")
    claim_supported = (
        deadlock_goblocks
        and success_goblocks
        and (sum(deadlock_goblocks) / len(deadlock_goblocks))
        > (sum(success_goblocks) / len(success_goblocks))
    )
    print(f"    Distribution collapse claim supported: {claim_supported}")
    print()


def main() -> None:
    print(f"Loading examples from {DATASET_DIR} ...")
    examples = load_examples(DATASET_DIR)
    print(f"  Loaded {len(examples)} per-run examples")

    # Count how many have no next_event (deadlocked runs)
    no_next = sum(1 for ex in examples if ex.get("next_event") is None)
    print(f"  Examples with no next_event (deadlock/timeout): {no_next}")
    print(f"  Examples with next_event (scored):              {len(examples) - no_next}")

    print("\nAggregating by (program_id, split_percent) ...")
    aggregated = aggregate(examples)
    print(f"  Produced {len(aggregated)} aggregated groups")

    print_exploratory_analysis(aggregated)

    print(f"Writing {OUTPUT_FILE} ...")
    with open(OUTPUT_FILE, "w") as f:
        json.dump(aggregated, f, indent=2)
    print(f"  Done — {len(aggregated)} records written")


if __name__ == "__main__":
    main()
