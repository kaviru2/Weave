#!/usr/bin/env python3
"""
eval/simulation_rollout.py

Autoregressive trajectory simulator ("Dreamer") that evaluates the model's capacity
to simulate concurrent Go execution traces without violating Go scheduler invariants.

Methodology:
  1. Loads a program and a starting trace prefix (e.g., 25% or 50% split).
  2. Initializes a symbolic scheduler FSM to track goroutine states (runnable, running, blocked, dead).
  3. Autoregressively queries the model for next-event transitions using temperature sampling.
  4. At each step, checks if the model's action violates Go scheduler invariants.
  5. Measures "Survival Steps" (number of valid simulation steps before first invariant violation).

Run:
  uv run python eval/simulation_rollout.py --program 01_simple_channel --split 25 --steps 10 --temp 0.7
  uv run python eval/simulation_rollout.py --program 01_simple_channel --split 25 --steps 10 --backend lora
"""

import os
import re
import sys
import json
import random
import argparse
import logging
from typing import Any, Dict, List, Tuple, Optional

from dotenv import load_dotenv

# Gemini imports — only used when --backend gemini (default)
try:
    from google import genai
    from google.genai import types as genai_types
    _GEMINI_AVAILABLE = True
except ImportError:
    _GEMINI_AVAILABLE = False

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_DIR = os.path.join(BASE_DIR, "dataset", "output")
RESULTS_DIR = os.path.join(BASE_DIR, "eval", "results")

ALL_EVENT_TYPES = ["GoBlock", "GoCreate", "GoEnd", "GoSched", "GoStart", "GoUnblock"]

# ── LoRA backend state (lazy-loaded) ───────────────────────────────────────
_lora_model     = None
_lora_tokenizer = None
_LORA_ADAPTER   = os.path.join(BASE_DIR, "dataset", "output", "lora_adapter")
_LORA_BASE      = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
_LORA_MAX_TOKENS = 512   # CPU constraint; bump to 1024 if running on GPU


def _load_lora_model():
    """Lazy-load the fine-tuned LoRA model. Called once on first --backend lora request."""
    global _lora_model, _lora_tokenizer
    if _lora_model is not None:
        return

    import torch
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    logging.info(f"Loading LoRA model: {_LORA_BASE}")
    _lora_tokenizer = AutoTokenizer.from_pretrained(_LORA_BASE, trust_remote_code=True)
    base = AutoModelForCausalLM.from_pretrained(
        _LORA_BASE,
        dtype=torch.float16,   # newer transformers: dtype not torch_dtype
        trust_remote_code=True,
    )
    _lora_model = PeftModel.from_pretrained(base, _LORA_ADAPTER)
    _lora_model = _lora_model.to(torch.device("cpu"))
    _lora_model.eval()
    logging.info("LoRA model ready.")


def _smart_truncate_for_lora(prompt_messages, max_tokens=_LORA_MAX_TOKENS):
    """
    Restructure the prompt to fit within max_tokens.
    Keeps: program header (first 20 lines) + last 3 trace events +
           current state + prediction request.
    This is the same strategy used in inference_check.py.
    """
    system_msg   = prompt_messages[0]
    user_content = prompt_messages[1]["content"] if len(prompt_messages) > 1 else ""

    prog_match  = re.search(r"<program>(.*?)</program>",             user_content, re.DOTALL)
    trace_match = re.search(r"<trace>(.*?)</trace>",                 user_content, re.DOTALL)
    state_match = re.search(r"<current_state>(.*?)</current_state>", user_content, re.DOTALL)

    if prog_match:
        prog_head = "\n".join(prog_match.group(1).strip().split("\n")[:20])
    else:
        prog_head = ""

    if trace_match:
        try:
            events = json.loads(trace_match.group(1).strip())
            slim   = [
                {"event_id": ev.get("event_id"), "event_type": ev.get("event_type"),
                 "goroutine_id": ev.get("goroutine_id")}
                for ev in events[-5:]
            ]
            trace_short = json.dumps(slim, indent=2)
        except (json.JSONDecodeError, TypeError):
            trace_short = ""
    else:
        trace_short = ""

    state_text = state_match.group(1).strip() if state_match else ""
    tail = user_content[state_match.end():].strip() if state_match else (
        'Predict the next scheduler event. What happens next?\n'
        'Respond in JSON only — no markdown fences, no text outside the JSON object:\n'
        '{"event_type":"GoStart|GoBlock|GoUnblock|GoCreate|GoEnd|GoSched",'
        '"goroutine_id":<integer>,"reasoning":"<brief explanation>","confidence":"high|medium|low"}'
    )

    new_user = (
        "You are reasoning about concurrent Go program execution.\n\n"
        "Here is a Go program (header):\n"
        f"<program>\n{prog_head}\n</program>\n\n"
        "Here is the end of the partial execution trace (event types and goroutines only):\n"
        f"<trace>\n{trace_short}\n</trace>\n\n"
        "The current goroutine states are:\n"
        f"<current_state>\n{state_text}\n</current_state>\n\n"
        f"{tail}"
    )

    reconstructed = [system_msg, {"role": "user", "content": new_user}]
    prompt = _lora_tokenizer.apply_chat_template(
        reconstructed, tokenize=False, add_generation_prompt=True,
    )
    return _lora_tokenizer(
        prompt, return_tensors="pt",
        truncation=True, max_length=max_tokens,
        truncation_side="left",
    )


class SchedulerFSM:
    """
    Symbolic State Tracker representing the Go scheduler.
    Valid states per goroutine: 'runnable', 'running', 'blocked', 'dead'.
    """
    def __init__(self, initial_goroutines: Dict[str, Dict[str, Any]]):
        # Maps goroutine_id (int) to state (str)
        self.states: Dict[int, str] = {}
        for gid_str, info in initial_goroutines.items():
            gid = int(gid_str)
            status = info.get("status", "").lower()
            if "running" in status:
                self.states[gid] = "running"
            elif "runnable" in status:
                self.states[gid] = "runnable"
            elif "blocked" in status:
                self.states[gid] = "blocked"
            elif "dead" in status:
                self.states[gid] = "dead"
            else:
                self.states[gid] = "runnable"  # default fallback

    def get_snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Returns the current state dictionary formatted for trace snapshots."""
        snapshot = {}
        for gid, state in self.states.items():
            if state != "dead":
                snapshot[str(gid)] = {
                    "status": state,
                    "blocked_on": "chan receive" if state == "blocked" else None,
                    "locals_hint": "unknown"
                }
        return snapshot

    def check_and_apply(self, event_type: str, goroutine_id: int) -> Tuple[bool, Optional[str]]:
        """
        Validates if the transition is allowed in the Go scheduler.
        If valid, mutates the FSM state and returns (True, None).
        If invalid, returns (False, error_reason).
        """
        current_state = self.states.get(goroutine_id, "dead")

        if event_type == "GoCreate":
            # Can only create a new or dead goroutine
            if current_state != "dead":
                return False, f"Cannot create goroutine {goroutine_id} because it is already in state: {current_state}"
            self.states[goroutine_id] = "runnable"
            return True, None

        elif event_type == "GoStart":
            # Must be runnable to start running
            if current_state != "runnable":
                return False, f"Cannot start goroutine {goroutine_id} because it is in state: {current_state} (expected runnable)"
            
            # Go scheduler runtime invariant: only one running goroutine on a thread/P.
            # Here we enforce that a started goroutine becomes 'running'.
            self.states[goroutine_id] = "running"
            return True, None

        elif event_type == "GoBlock":
            # Must be running to block
            if current_state != "running":
                return False, f"Cannot block goroutine {goroutine_id} because it is in state: {current_state} (expected running)"
            self.states[goroutine_id] = "blocked"
            return True, None

        elif event_type == "GoUnblock":
            # Must be blocked to unblock
            if current_state != "blocked":
                return False, f"Cannot unblock goroutine {goroutine_id} because it is in state: {current_state} (expected blocked)"
            self.states[goroutine_id] = "runnable"
            return True, None

        elif event_type == "GoSched":
            # Must be running to yield / yield scheduler
            if current_state != "running":
                return False, f"Cannot yield goroutine {goroutine_id} because it is in state: {current_state} (expected running)"
            self.states[goroutine_id] = "runnable"
            return True, None

        elif event_type == "GoEnd":
            # Must be running to terminate
            if current_state != "running":
                return False, f"Cannot terminate goroutine {goroutine_id} because it is in state: {current_state} (expected running)"
            self.states[goroutine_id] = "dead"
            return True, None

        return False, f"Unknown event type: {event_type}"


def build_prompt(program_source: str, partial_trace: List[Dict[str, Any]]) -> str:
    """Constructs the prompt for autoregressive point prediction."""
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

Predict the next scheduler event. What happens next?
Respond in JSON only — no markdown fences, no text outside the JSON object:
{{"event_type":"GoStart|GoBlock|GoUnblock|GoCreate|GoEnd|GoSched","goroutine_id":<integer>,"reasoning":"<brief explanation>","confidence":"high|medium|low"}}"""


def call_gemini(client, model_name: str, prompt: str, temp: float) -> str:
    """Queries Gemini API for next event transition."""
    config = genai_types.GenerateContentConfig(
        temperature=temp,
        max_output_tokens=512,
        thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
    )
    resp = client.models.generate_content(model=model_name, contents=prompt, config=config)
    return resp.text


def call_lora_model(prompt_messages: List[Dict[str, str]], temp: float) -> str:
    """Queries the fine-tuned LoRA adapter for next event transition."""
    import torch
    _load_lora_model()

    inputs = _smart_truncate_for_lora(prompt_messages).to(next(_lora_model.parameters()).device)
    do_sample = temp > 0.0

    with torch.no_grad():
        output_ids = _lora_model.generate(
            **inputs,
            max_new_tokens=60,
            do_sample=do_sample,
            temperature=temp if do_sample else 1.0,
            pad_token_id=_lora_tokenizer.eos_token_id,
        )

    new_tokens = output_ids[0][inputs["input_ids"].shape[1]:]
    return _lora_tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


def parse_response(raw: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """Cleans markdown syntax and decodes predicted event type and goroutine ID."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if len(lines) >= 2:
            text = "\n".join(lines[1:])
        text = text.rstrip("`").strip()

    try:
        data = json.loads(text)
        event_type = data.get("event_type")
        goroutine_id = data.get("goroutine_id")
        reasoning = data.get("reasoning", "")
        if event_type in ALL_EVENT_TYPES and isinstance(goroutine_id, (int, float)):
            return event_type, int(goroutine_id), reasoning
    except Exception:
        pass
    return None, None, None


def load_initial_trajectory(program_id: str, split_percent: int) -> Dict[str, Any]:
    """Loads a representative partial trace from dataset output."""
    for run in range(5):
        fname = f"{program_id}_run{run}_split{split_percent}.json"
        path = os.path.join(DATASET_DIR, fname)
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    raise FileNotFoundError(f"Could not find run file for {program_id} split {split_percent}")


def run_simulation(
    program_id: str,
    split_percent: int,
    max_steps: int,
    temp: float,
    model_name: str,
    backend: str = "gemini",
) -> Dict[str, Any]:
    """Executes the simulation loop, checking FSM states and survival metrics."""
    client = None
    if backend == "gemini":
        if not _GEMINI_AVAILABLE:
            logging.error("google-genai package not installed. Install it or use --backend lora.")
            sys.exit(1)
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            logging.error("GEMINI_API_KEY is not set.")
            sys.exit(1)
        client = genai.Client(api_key=api_key)
    elif backend == "lora":
        _load_lora_model()  # warm up before the loop
    else:
        logging.error(f"Unknown backend: {backend}")
        sys.exit(1)

    # 1. Load initial prefix
    traj_data = load_initial_trajectory(program_id, split_percent)
    program_source = traj_data["program_source"]
    partial_trace = traj_data["partial_trace"]

    if not partial_trace:
        raise ValueError("Partial trace is empty. Cannot run simulation.")

    # 2. Initialize FSM
    last_state = partial_trace[-1]
    fsm = SchedulerFSM(last_state.get("goroutines", {}))

    logging.info(f"Loaded prefix for {program_id} ({len(partial_trace)} events). Initial FSM status: {fsm.states}")

    steps = []
    survival_steps = 0
    failure_reason = None
    violation_occurred = False

    # 3. Rollout loop
    for step in range(1, max_steps + 1):
        prompt_str = build_prompt(program_source, partial_trace)

        try:
            if backend == "gemini":
                raw_resp = call_gemini(client, model_name, prompt_str, temp)
            else:
                # LoRA backend: wrap prompt into chat messages for smart truncation
                prompt_messages = [
                    {"role": "system",    "content": "You are a code execution simulator."},
                    {"role": "user",      "content": prompt_str},
                ]
                raw_resp = call_lora_model(prompt_messages, temp)
            event_type, gid, reasoning = parse_response(raw_resp)
        except Exception as e:
            logging.error(f"Backend call failed at step {step}: {e}")
            failure_reason = f"Backend error: {e}"
            break

        if event_type is None or gid is None:
            failure_reason = "Malformed response JSON structure"
            violation_occurred = True
            logging.warning(f"Step {step} - Malformed response: {raw_resp}")
            break

        # Check invariants
        valid, error = fsm.check_and_apply(event_type, gid)
        
        step_record = {
            "step": step,
            "predicted_event": event_type,
            "predicted_goroutine_id": gid,
            "reasoning": reasoning,
            "fsm_valid": valid,
            "error_reason": error
        }
        steps.append(step_record)

        if not valid:
            failure_reason = error
            violation_occurred = True
            logging.warning(f"Step {step} - Invariant Violation: {error}")
            break

        # Append new trace event
        last_snap = partial_trace[-1]
        new_snap = {
            "event_id": last_snap["event_id"] + 1,
            "timestamp_ns": last_snap["timestamp_ns"] + 1000,  # incremental mock timestamp
            "event_type": event_type,
            "goroutine_id": gid,
            "goroutines": fsm.get_snapshot(),
            "channels": {},
            "mutexes": {}
        }
        partial_trace.append(new_snap)
        survival_steps += 1
        logging.info(f"Step {step} - Success: {event_type} for G{gid}. FSM: {fsm.states}")

    rollout_outcome = {
        "program_id":       program_id,
        "split_percent":    split_percent,
        "backend":          backend,
        "model_name":       model_name if backend == "gemini" else _LORA_BASE,
        "temperature":      temp,
        "max_steps":        max_steps,
        "survival_steps":   survival_steps,
        "violation_occurred": violation_occurred,
        "failure_reason":   failure_reason,
        "rollout_steps":    steps,
    }
    return rollout_outcome


def main():
    parser = argparse.ArgumentParser(description="Weave Autoregressive Trajectory Simulator (Dreamer)")
    parser.add_argument("--program", type=str, default="01_simple_channel", help="Program ID to run simulation on")
    parser.add_argument("--split",   type=int, default=25, choices=[25, 50, 75], help="Trace prefix split percentage")
    parser.add_argument("--steps",   type=int, default=10, help="Maximum simulation steps")
    parser.add_argument("--temp",    type=float, default=0.7, help="LLM generation temperature")
    parser.add_argument("--backend", type=str, default="gemini", choices=["gemini", "lora"],
                        help="Backend model to use: 'gemini' (default) or 'lora' (fine-tuned local adapter)")
    args = parser.parse_args()

    model_name = os.getenv("MODEL", "gemini-3.5-flash")

    logging.info(
        f"Starting rollout on {args.program} at {args.split}% split "
        f"(backend={args.backend}, temp={args.temp})"
    )

    try:
        result = run_simulation(args.program, args.split, args.steps, args.temp, model_name, backend=args.backend)
    except Exception as e:
        logging.error(f"Simulation crashed: {e}")
        sys.exit(1)

    # Output results to disk — include backend in filename to avoid collisions
    os.makedirs(RESULTS_DIR, exist_ok=True)
    suffix = f"_split{args.split}_{args.backend}.json"
    out_path = os.path.join(RESULTS_DIR, f"simulation_{args.program}{suffix}")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print("\n" + "="*65)
    print("=== TRAJECTORY ROLLOUT SIMULATION RESULT ===")
    print("="*65)
    print(f"  Program ID       : {result['program_id']}")
    print(f"  Prefix Split     : {result['split_percent']}%")
    print(f"  Backend          : {result['backend']}")
    print(f"  Model            : {result['model_name']}")
    print(f"  Max Steps        : {result['max_steps']}")
    print(f"  Survival Steps   : {result['survival_steps']}")
    print(f"  Violation?       : {result['violation_occurred']}")
    if result["violation_occurred"]:
        print(f"  Failure Reason   : {result['failure_reason']}")
    print(f"  Results saved to : {out_path}")
    print("="*65 + "\n")


if __name__ == "__main__":
    main()
