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
import copy
from collections import defaultdict
from typing import Any, Dict, List, Tuple

try:
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-1.5B-Instruct", trust_remote_code=True)
except Exception as e:
    tokenizer = None

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


def smart_truncate_messages(messages: List[Dict[str, str]], max_tokens: int = 4000) -> List[Dict[str, str]]:
    """Smartly shrinks the program and trace sections so the prompt fits under max_tokens."""
    if not tokenizer:
        return messages
    
    msgs = copy.deepcopy(messages)
    prompt = tokenizer.apply_chat_template(msgs, tokenize=False)
    tokens = tokenizer(prompt)["input_ids"]
    if len(tokens) <= max_tokens:
        return msgs

    user_content = msgs[1]["content"]

    # 1. Truncate Trace to last 10 events and cap string size
    try:
        trace_start = user_content.index("<trace>\n") + len("<trace>\n")
        trace_end = user_content.index("\n</trace>")
        trace_str = user_content[trace_start:trace_end]
        
        trace_json = json.loads(trace_str)
        if len(trace_json) > 10:
            trace_json = trace_json[-10:]
            
        # If trace is still huge, remove goroutines block from all but last event
        trace_str = json.dumps(trace_json, indent=2)
        if len(trace_str) > 8000:
            for i in range(len(trace_json) - 1):
                if "goroutines" in trace_json[i]:
                    trace_json[i]["goroutines"] = "... [TRUNCATED FOR LENGTH] ..."
            trace_str = json.dumps(trace_json, indent=2)
            
            if len(trace_str) > 8000:
                trace_str = trace_str[:4000] + "\n... [TRUNCATED TRACE] ...\n" + trace_str[-4000:]
                
        user_content = user_content[:trace_start] + trace_str + user_content[trace_end:]
        msgs[1]["content"] = user_content
            
    except Exception:
        pass

    prompt = tokenizer.apply_chat_template(msgs, tokenize=False)
    tokens = tokenizer(prompt)["input_ids"]
    if len(tokens) <= max_tokens:
        return msgs

    # 2. Truncate Current State
    try:
        state_start = user_content.index("<current_state>\n") + len("<current_state>\n")
        state_end = user_content.index("\n</current_state>")
        state_str = user_content[state_start:state_end]
        
        if len(state_str) > 1000:
            state_str = state_str[:1000] + "\n... [TRUNCATED STATE] ..."
            user_content = user_content[:state_start] + state_str + user_content[state_end:]
            msgs[1]["content"] = user_content
            
    except Exception:
        pass

    prompt = tokenizer.apply_chat_template(msgs, tokenize=False)
    tokens = tokenizer(prompt)["input_ids"]
    if len(tokens) <= max_tokens:
        return msgs

    # 3. Truncate Program iteratively
    try:
        prog_start = user_content.index("<program>\n") + len("<program>\n")
        prog_end = user_content.index("\n</program>")
        prog_str = user_content[prog_start:prog_end]
        
        # We will use a safe static length to guarantee it fits. 4000 tokens is ~12,000 characters total.
        # If the tokens are still > max_tokens, the program is the largest block remaining.
        if len(prog_str) > 2000:
            prog_str = prog_str[:1000] + "\n... [TRUNCATED] ...\n" + prog_str[-1000:]
            user_content = user_content[:prog_start] + prog_str + user_content[prog_end:]
            msgs[1]["content"] = user_content
            
            prompt = tokenizer.apply_chat_template(msgs, tokenize=False)
            tokens = tokenizer(prompt)["input_ids"]
            
            if len(tokens) > max_tokens:
                # Still too big, truncate even more aggressively
                prog_end_new = user_content.index("\n</program>")
                prog_str_new = user_content[prog_start:prog_end_new]
                prog_str_new = prog_str_new[:500] + "\n... [TRUNCATED] ...\n"
                user_content = user_content[:prog_start] + prog_str_new + user_content[prog_end_new:]
                msgs[1]["content"] = user_content
    except Exception:
        pass

    return msgs


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

    messages = [
        {"role": "system", "content": "You are a code execution simulator."},
        {"role": "user", "content": user_content},
        {"role": "assistant", "content": assistant_content}
    ]

    return {"messages": smart_truncate_messages(messages)}


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

    messages = [
        {"role": "system", "content": "You are a code execution simulator."},
        {"role": "user", "content": user_content},
        {"role": "assistant", "content": assistant_content}
    ]

    return {"messages": smart_truncate_messages(messages)}


def split_programs(aggregated: List[Dict[str, Any]], seed: int = 42) -> Tuple[set, set]:
    """Splits program IDs by holding out all GoKer programs for evaluation,
    and using hand-crafted and generated programs for training."""
    train_progs = set()
    val_progs = set()

    for group in aggregated:
        prog_id = group["program_id"]
        if prog_id.startswith("goker_"):
            val_progs.add(prog_id)
        else:
            train_progs.add(prog_id)

    # Log split counts by pattern
    train_patterns = defaultdict(set)
    val_patterns = defaultdict(set)
    for group in aggregated:
        prog_id = group["program_id"]
        pat = group["concurrency_pattern"]
        if prog_id in train_progs:
            train_patterns[pat].add(prog_id)
        else:
            val_patterns[pat].add(prog_id)

    logging.info("--- SPLIT BY PATTERN ---")
    for pat in sorted(set(list(train_patterns.keys()) + list(val_patterns.keys()))):
        num_train = len(train_patterns[pat])
        num_val = len(val_patterns[pat])
        logging.info(f"Pattern '{pat}': {num_train} train, {num_val} val (held-out GoKer)")

    return train_progs, val_progs


def main():
    """Main execution function."""
    logging.info("Starting SFT dataset preparation...")
    try:
        aggregated = load_aggregated_dataset()
    except Exception as e:
        logging.error(f"Failed to load dataset: {e}")
        return

    # Train / Val GoKer held-out split
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
        dist_msg["concurrency_pattern"] = group["concurrency_pattern"]
        dist_msg["nondeterminism"] = group["nondeterminism"]
        if is_train:
            train_dist_items.append(dist_msg)
        else:
            val_dist_items.append(dist_msg)

        # 2. Point mode SFT format (Frequency Duplication)
        for next_evt, run_idx in next_events:
            point_msg = format_point_chat_message(source, partial_trace, next_evt)
            point_msg["concurrency_pattern"] = group["concurrency_pattern"]
            point_msg["nondeterminism"] = group["nondeterminism"]
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

    os.makedirs(os.path.join(DATASET_DIR, "kaggle_upload"), exist_ok=True)

    for fname, data_list in files_to_write:
        # Write to primary output directory
        out_path = os.path.join(DATASET_DIR, fname)
        with open(out_path, "w") as f:
            for item in data_list:
                f.write(json.dumps(item) + "\n")
        logging.info(f"Wrote {len(data_list)} examples to {out_path}")

        # Sync to kaggle_upload directory
        kaggle_out_path = os.path.join(DATASET_DIR, "kaggle_upload", fname)
        with open(kaggle_out_path, "w") as f:
            for item in data_list:
                f.write(json.dumps(item) + "\n")
        logging.info(f"Synced {len(data_list)} examples to {kaggle_out_path}")

    logging.info("SFT dataset preparation complete!")


if __name__ == "__main__":
    main()
