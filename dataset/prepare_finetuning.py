#!/usr/bin/env python3
"""
dataset/prepare_finetuning.py

Processes Weave's aggregated execution trace dataset and outputs training/validation
JSONL files in HuggingFace Chat Template (messages) format.

Supports two distinct SFT target strategies:
  1. dist: Targets are explicit JSON probability distributions over event types.
  2. point: Targets are individual point predictions (event_type & goroutine_id)
     duplicated proportionally to their empirical occurrence. This allows standard
     cross-entropy next-token prediction to approximate the target distribution.

Verifies and splits programs into 80% train / 20% validation, stratified by pattern.
"""

import os
import json
import random
import glob
import logging
from collections import defaultdict
from typing import Any, Dict, List, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# File paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_DIR = os.path.join(BASE_DIR, "dataset", "output")
AGGREGATED_FILE = os.path.join(DATASET_DIR, "aggregated.json")

# Categories for stratification
ALL_EVENT_TYPES = ["GoBlock", "GoCreate", "GoEnd", "GoSched", "GoStart", "GoUnblock"]


def load_aggregated_dataset() -> List[Dict[str, Any]]:
    """Loads the aggregated dataset JSON."""
    if not os.path.exists(AGGREGATED_FILE):
        raise FileNotFoundError(f"Aggregated file not found at: {AGGREGATED_FILE}. Run aggregate.py first.")
    with open(AGGREGATED_FILE, "r") as f:
        return json.load(f)


def build_prompts(
    group: Dict[str, Any]
) -> Tuple[str, str, List[Tuple[Dict[str, Any], int]]]:
    """
    Finds and loads per-run example files for a group to extract source,
    partial trace structure, and next event targets.
    Returns:
        (program_source, partial_trace_json, next_events_list)
    """
    program_id = group["program_id"]
    split_percent = group["split_percent"]

    # Locate available run files
    pattern = os.path.join(DATASET_DIR, f"{program_id}_run*_split{split_percent}.json")
    run_files = glob.glob(pattern)

    if not run_files:
        # Check if it was a deadlock/timeout run (stored under run*_deadlock.json)
        pattern_deadlock = os.path.join(DATASET_DIR, f"{program_id}_run*_deadlock.json")
        run_files = glob.glob(pattern_deadlock)

    if not run_files:
        raise RuntimeError(f"No run files found for {program_id} split {split_percent}")

    # Read program source and partial trace from the first available run file
    with open(run_files[0], "r") as f:
        sample_data = json.load(f)
    
    program_source = sample_data["program_source"]
    partial_trace = sample_data["partial_trace"]

    # Gather targets from all active runs in this group
    next_events = []
    for rf in run_files:
        with open(rf, "r") as f:
            data = json.load(f)
        if data.get("timed_out"):
            # Deadlocks/timeouts have no valid next event
            continue
        if data.get("next_event"):
            next_events.append((data["next_event"], data["run_index"]))

    return program_source, partial_trace, next_events


def format_dist_chat_message(
    program_source: str, 
    partial_trace: List[Dict[str, Any]], 
    distribution: Dict[str, float]
) -> Dict[str, Any]:
    """Formats an SFT example for Explicit Distribution target (KL loss)."""
    trace_json = json.dumps(partial_trace, indent=2)
    current_state_json = json.dumps(partial_trace[-1], indent=2) if partial_trace else "{}"

    user_content = f"""You are reasoning about concurrent Go program execution.

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

    assistant_content = json.dumps(distribution)

    return {
        "messages": [
            {"role": "system", "content": "You are a code execution simulator."},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_content}
        ]
    }


def format_point_chat_message(
    program_source: str, 
    partial_trace: List[Dict[str, Any]], 
    next_event: Dict[str, Any]
) -> Dict[str, Any]:
    """Formats an SFT example for point-prediction targets (duplication)."""
    trace_json = json.dumps(partial_trace, indent=2)
    current_state_json = json.dumps(partial_trace[-1], indent=2) if partial_trace else "{}"

    user_content = f"""You are reasoning about concurrent Go program execution.

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

Predict the next scheduler event. What happens next?
Respond in JSON only — no markdown fences, no text outside the JSON object:
{{"event_type":"GoStart|GoBlock|GoUnblock|GoCreate|GoEnd|GoSched","goroutine_id":<integer>,"reasoning":"<brief explanation>","confidence":"high|medium|low"}}"""

    assistant_content = json.dumps({
        "event_type": next_event["event_type"],
        "goroutine_id": int(next_event["goroutine_id"])
    })

    return {
        "messages": [
            {"role": "system", "content": "You are a code execution simulator."},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_content}
        ]
    }


def split_programs(aggregated: List[Dict[str, Any]], seed: int = 42) -> Tuple[set, set]:
    """Splits program IDs into 80% train / 20% validation, stratified by pattern."""
    # Group programs by pattern
    pattern_to_progs = defaultdict(set)
    for group in aggregated:
        pattern_to_progs[group["concurrency_pattern"]].add(group["program_id"])

    train_progs = set()
    val_progs = set()

    random.seed(seed)

    for pattern, progs in sorted(pattern_to_progs.items()):
        prog_list = sorted(list(progs))
        random.shuffle(prog_list)
        
        split_idx = max(1, int(len(prog_list) * 0.8))
        train_chunk = prog_list[:split_idx]
        val_chunk = prog_list[split_idx:]
        
        train_progs.update(train_chunk)
        val_progs.update(val_chunk)
        
        logging.info(f"Pattern '{pattern}' split: {len(train_chunk)} train, {len(val_chunk)} val. Programs: {prog_list}")

    return train_progs, val_progs


def main():
    """Main execution function."""
    logging.info("Starting SFT dataset preparation...")
    try:
        aggregated = load_aggregated_dataset()
    except Exception as e:
        logging.error(f"Failed to load dataset: {e}")
        return

    # Train / Val Stratified split
    train_progs, val_progs = split_programs(aggregated)
    logging.info(f"Total split summary: {len(train_progs)} training programs, {len(val_progs)} validation programs.")

    train_dist_items = []
    val_dist_items = []
    
    train_point_items = []
    val_point_items = []

    for idx, group in enumerate(aggregated, 1):
        program_id = group["program_id"]
        split_percent = group["split_percent"]
        dist = group["next_event_distribution"]
        is_train = program_id in train_progs

        try:
            source, partial_trace, next_events = build_prompts(group)
        except Exception as e:
            logging.warning(f"Skipping group ({program_id}, {split_percent}%): {e}")
            continue

        # 1. Dist mode SFT format
        dist_msg = format_dist_chat_message(source, partial_trace, dist)
        if is_train:
            train_dist_items.append(dist_msg)
        else:
            val_dist_items.append(dist_msg)

        # 2. Point mode SFT format (Frequency Duplication)
        for next_evt, run_idx in next_events:
            point_msg = format_point_chat_message(source, partial_trace, next_evt)
            if is_train:
                train_point_items.append(point_msg)
            else:
                val_point_items.append(point_msg)

    # Write output files
    files_to_write = [
        ("train_dist.jsonl", train_dist_items),
        ("val_dist.jsonl", val_dist_items),
        ("train_point_dups.jsonl", train_point_items),
        ("val_point_dups.jsonl", val_point_items)
    ]

    for fname, data_list in files_to_write:
        out_path = os.path.join(DATASET_DIR, fname)
        with open(out_path, "w") as f:
            for item in data_list:
                f.write(json.dumps(item) + "\n")
        logging.info(f"Wrote {len(data_list)} examples to {out_path}")

    logging.info("SFT dataset preparation complete!")


if __name__ == "__main__":
    main()
