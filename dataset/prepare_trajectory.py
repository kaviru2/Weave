#!/usr/bin/env python3
"""
dataset/prepare_trajectory.py — Phase 16

Builds multi-turn trajectory training examples from existing split files.
Each example is a conversation of 3–5 (user, assistant) turns where the model
must predict consecutive ground-truth scheduler events.

Seed: partial_trace from splitX
Steps: next N events extracted from splitY.partial_trace[kX:kX+MAX_STEPS]

Two trajectory types per non-timed-out run:
  A — seed=split25, steps from split50
  B — seed=split50, steps from split75

Train/val split: GoKer programs → val, everything else → train.

Usage:
  uv run python dataset/prepare_trajectory.py
  uv run python dataset/prepare_trajectory.py --min-steps 3 --max-steps 5
"""

import os
import json
import glob
import logging
import argparse
import copy
from typing import Any, Dict, List, Optional, Tuple

try:
    from transformers import AutoTokenizer
    _tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-1.5B-Instruct", trust_remote_code=True)
except Exception:
    _tokenizer = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR  = os.path.join(BASE_DIR, "dataset", "output")

SYSTEM_MSG = "You are a code execution simulator."
PREDICT_SUFFIX = (
    "Predict the next scheduler event. What happens next?\n"
    "Respond in JSON only — no markdown fences, no text outside the JSON object:\n"
    '{"event_type":"GoStart|GoBlock|GoUnblock|GoCreate|GoEnd|GoSched",'
    '"goroutine_id":<integer>}'
)


# ── Prompt construction ────────────────────────────────────────────────────────

def _user_turn(program_source: str, partial_trace: List[Dict[str, Any]]) -> str:
    trace_json = json.dumps(partial_trace, indent=2)
    current_state_json = json.dumps(partial_trace[-1], indent=2) if partial_trace else "{}"
    return (
        "You are reasoning about concurrent Go program execution.\n\n"
        "Here is a Go program:\n"
        f"<program>\n{program_source}\n</program>\n\n"
        "Here is a partial execution trace showing goroutine scheduler events so far:\n"
        f"<trace>\n{trace_json}\n</trace>\n\n"
        "The current goroutine states are:\n"
        f"<current_state>\n{current_state_json}\n</current_state>\n\n"
        f"{PREDICT_SUFFIX}"
    )


def _assistant_turn(event: Dict[str, Any]) -> str:
    return json.dumps({
        "event_type": event["event_type"],
        "goroutine_id": int(event["goroutine_id"]),
    })


# ── Token-aware truncation (only applied to the first user turn) ───────────────

def _truncate_first_user_turn(content: str, max_chars: int = 8000) -> str:
    """Trim program and trace sections if the first user turn is too long."""
    if len(content) <= max_chars:
        return content

    # Shorten program to first 30 lines
    import re
    prog_m = re.search(r"(<program>\n)(.*?)(\n</program>)", content, re.DOTALL)
    if prog_m:
        lines = prog_m.group(2).split("\n")
        if len(lines) > 30:
            short = "\n".join(lines[:30]) + "\n... [TRUNCATED] ..."
            content = content[:prog_m.start(2)] + short + content[prog_m.end(2):]

    if len(content) <= max_chars:
        return content

    # Shorten trace to last 8 events
    trace_m = re.search(r"(<trace>\n)(.*?)(\n</trace>)", content, re.DOTALL)
    if trace_m:
        try:
            events = json.loads(trace_m.group(2))
            if len(events) > 8:
                slim = [
                    {"event_id": e.get("event_id"), "event_type": e.get("event_type"),
                     "goroutine_id": e.get("goroutine_id")}
                    for e in events[-8:]
                ]
                short_trace = json.dumps(slim, indent=2)
                content = content[:trace_m.start(2)] + short_trace + content[trace_m.end(2):]
        except Exception:
            pass

    return content


# ── Trajectory builder ─────────────────────────────────────────────────────────

def build_trajectory(
    program_source: str,
    seed_trace: List[Dict[str, Any]],
    step_events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Returns a single multi-turn messages dict.
    Each (user, assistant) pair extends the trace by one event.
    """
    messages = [{"role": "system", "content": SYSTEM_MSG}]
    current_trace = list(seed_trace)

    for i, event in enumerate(step_events):
        user_content = _user_turn(program_source, current_trace)
        # Only truncate the first user turn (the heaviest one — program + full seed trace)
        if i == 0:
            user_content = _truncate_first_user_turn(user_content)

        messages.append({"role": "user", "content": user_content})
        messages.append({"role": "assistant", "content": _assistant_turn(event)})

        # Extend the trace with the ground-truth event for the next turn
        current_trace = current_trace + [event]

    return {"messages": messages}


# ── File loading ───────────────────────────────────────────────────────────────

def _load(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


# ── Main ───────────────────────────────────────────────────────────────────────

def main(min_steps: int = 3, max_steps: int = 5) -> None:
    logging.info(f"Building trajectory dataset (min={min_steps}, max={max_steps} steps)...")

    train_items: List[Dict] = []
    val_items:   List[Dict] = []

    skipped = 0
    built   = 0

    for f25 in sorted(glob.glob(os.path.join(DATA_DIR, "*_run*_split25.json"))):
        stem = f25[:-len("_split25.json")]
        f50  = stem + "_split50.json"
        f75  = stem + "_split75.json"

        d25 = _load(f25)
        d50 = _load(f50)
        d75 = _load(f75)

        if not d25 or not d50 or not d75:
            skipped += 1
            continue

        # Skip timed-out runs (deadlocks have no valid next events)
        if d25.get("timed_out") or d50.get("timed_out") or d75.get("timed_out"):
            skipped += 1
            continue

        program_id     = d25["program_id"]
        program_source = d25["program_source"]
        is_val         = program_id.startswith("goker_")
        dest            = val_items if is_val else train_items

        k25 = len(d25["partial_trace"])
        k50 = len(d50["partial_trace"])

        # Trajectory A: seed = split25, steps from split50
        steps_a = d50["partial_trace"][k25 : k25 + max_steps]
        if len(steps_a) >= min_steps:
            traj = build_trajectory(program_source, d25["partial_trace"], steps_a)
            traj["program_id"]          = program_id
            traj["trajectory_type"]     = "A_25to50"
            traj["concurrency_pattern"] = d25["concurrency_pattern"]
            traj["nondeterminism"]      = d25["nondeterminism"]
            traj["n_steps"]             = len(steps_a)
            dest.append(traj)
            built += 1

        # Trajectory B: seed = split50, steps from split75
        steps_b = d75["partial_trace"][k50 : k50 + max_steps]
        if len(steps_b) >= min_steps:
            traj = build_trajectory(program_source, d50["partial_trace"], steps_b)
            traj["program_id"]          = program_id
            traj["trajectory_type"]     = "B_50to75"
            traj["concurrency_pattern"] = d50["concurrency_pattern"]
            traj["nondeterminism"]      = d50["nondeterminism"]
            traj["n_steps"]             = len(steps_b)
            dest.append(traj)
            built += 1

    # Write output
    out_train = os.path.join(DATA_DIR, "train_trajectory.jsonl")
    out_val   = os.path.join(DATA_DIR, "val_trajectory.jsonl")

    for path, items in [(out_train, train_items), (out_val, val_items)]:
        with open(path, "w") as f:
            for item in items:
                f.write(json.dumps(item) + "\n")
        logging.info(f"Wrote {len(items)} trajectories → {path}")

    logging.info(
        f"Done. Built={built}  (train={len(train_items)}, val={len(val_items)})  skipped={skipped}"
    )

    # Quick sanity check: show turn counts
    if train_items:
        sample = train_items[0]
        turns  = len([m for m in sample["messages"] if m["role"] == "assistant"])
        logging.info(
            f"Sample trajectory: program={sample['program_id']} "
            f"steps={sample['n_steps']} assistant_turns={turns}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-steps", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=5)
    args = parser.parse_args()
    main(args.min_steps, args.max_steps)
