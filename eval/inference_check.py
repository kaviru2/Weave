#!/usr/bin/env python3
"""
eval/inference_check.py

Quick inference check: loads the trained LoRA adapter on top of
Qwen/Qwen2.5-Coder-1.5B-Instruct and runs it on 20 validation examples.
Prints predicted vs ground-truth next scheduler event for each.

Run from repo root:
    .venv/bin/python3 eval/inference_check.py
"""

import json
import os
import re
import random
import time
import torch

# Use standard HTTP download — XET chunked system stalls on slow connections
os.environ["HF_HUB_DISABLE_XET"] = "1"
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_MODEL   = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
ADAPTER_PATH = "dataset/output/lora_adapter"  # final 3-epoch adapter
VAL_FILE     = "dataset/output/val_point_dups.jsonl"
N_SAMPLES    = 20
MAX_NEW_TOKENS = 60
MAX_TOKENS   = 1024   # 775 tokens after smart restructure — CPU handles this in ~20s/example

# ── Device ─────────────────────────────────────────────────────────────────
# Use CPU — MPS OOMs when other apps are using memory on 18GB unified RAM
DEVICE = torch.device("cpu")
print("Using CPU")


def smart_truncate_messages(messages, tokenizer, max_tokens=MAX_TOKENS):
    """
    Restructure the prompt to fit within max_tokens while preserving the
    critical tail (current state + task instruction).

    User messages are ~9k chars (~2k tokens). Each trace event in the training
    data includes the full goroutine state snapshot (~200-400 tokens per event),
    making even 3 events exceed the 512-token budget.

    Strategy:
      - Program header: first 15 lines (WEAVE_META + function signatures)
      - Trace: slim events — only {event_id, event_type, goroutine_id}, no goroutine
        state per event (that state is already in <current_state>). Keep up to 20 events.
      - Current state: keep in full (the prediction context)
      - Prediction tail: keep in full (critical — this is the task instruction)
    Budget: ~15 (template) + ~10 (sys) + ~100 (prog) + ~150 (slim trace) + ~100 (state)
            + ~50 (tail) ≈ 425 tokens — fits within 512 with margin.
    """
    system_msg   = messages[0]
    user_content = messages[1]["content"]

    prog_match  = re.search(r"<program>(.*?)</program>",             user_content, re.DOTALL)
    trace_match = re.search(r"<trace>(.*?)</trace>",                 user_content, re.DOTALL)
    state_match = re.search(r"<current_state>(.*?)</current_state>", user_content, re.DOTALL)

    # Program: first 15 lines (WEAVE_META + func/type declarations)
    if prog_match:
        prog_lines = prog_match.group(1).strip().split("\n")
        prog_head  = "\n".join(prog_lines[:15])
    else:
        prog_head = ""

    # Trace: slim to {event_id, event_type, goroutine_id} — drop per-event goroutine state.
    # The current state is already captured in <current_state>; keeping it per-event doubles
    # the token count for no prediction benefit.
    if trace_match:
        try:
            events      = json.loads(trace_match.group(1).strip())
            slim_events = [
                {
                    "event_id":    ev.get("event_id"),
                    "event_type":  ev.get("event_type"),
                    "goroutine_id": ev.get("goroutine_id"),
                }
                for ev in events[-5:]  # last 5 slim events — keeps budget well under 1024
            ]
            trace_short = json.dumps(slim_events, indent=2)
        except (json.JSONDecodeError, TypeError):
            trace_short = ""
    else:
        trace_short = ""

    # Current state and prediction tail — keep in full
    state_text = state_match.group(1).strip() if state_match else ""
    tail = user_content[state_match.end():].strip() if state_match else (
        'Predict the next scheduler event. What happens next?\n'
        'Respond in JSON matching this schema:\n'
        '{"event_type": "GoStart | GoBlock | GoUnblock | GoCreate | GoEnd | GoSched",'
        ' "goroutine_id": <which goroutine>,'
        ' "reasoning": "<brief explanation>",'
        ' "confidence": "high | medium | low"}'
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
    prompt = tokenizer.apply_chat_template(
        reconstructed,
        tokenize=False,
        add_generation_prompt=True,
    )
    # Use left truncation so that if the prompt still exceeds max_tokens, the beginning
    # (program header) is cut rather than the critical tail (current state + task instruction).
    return tokenizer(
        prompt, return_tensors="pt",
        truncation=True, max_length=max_tokens,
        truncation_side="left",
    )


# ── Load model + adapter ───────────────────────────────────────────────────
print(f"\nLoading base model: {BASE_MODEL}")
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)

base_model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    dtype=torch.float16,
    trust_remote_code=True,
)
print(f"Loading LoRA adapter: {ADAPTER_PATH}")
model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
model = model.to(DEVICE)
model.eval()
print("Model ready.\n")

# ── Load validation examples ───────────────────────────────────────────────
with open(VAL_FILE) as f:
    examples = [json.loads(line) for line in f]

random.seed(42)
samples = random.sample(examples, min(N_SAMPLES, len(examples)))

# ── Inference loop ─────────────────────────────────────────────────────────
correct_type = 0
results = []

for i, ex in enumerate(samples):
    messages      = ex["messages"]
    ground_truth  = messages[-1]["content"]

    # Build prompt from system + user only (exclude assistant turn)
    prompt_messages = [m for m in messages if m["role"] != "assistant"]

    t0 = time.time()
    inputs = smart_truncate_messages(prompt_messages, tokenizer, MAX_TOKENS).to(DEVICE)
    n_input_tokens = inputs["input_ids"].shape[1]

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )

    elapsed = time.time() - t0

    # Decode only the newly generated tokens
    new_tokens = output_ids[0][inputs["input_ids"].shape[1]:]
    prediction = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

    # Compare event_type
    try:
        pred_json = json.loads(prediction)
        gt_json   = json.loads(ground_truth)
        match = pred_json.get("event_type") == gt_json.get("event_type")
        if match:
            correct_type += 1
    except json.JSONDecodeError:
        match = False

    results.append({
        "ground_truth": ground_truth,
        "prediction":   prediction,
        "match":        match,
    })

    status = "✓" if match else "✗"
    print(f"[{i+1:2d}] {status}  GT: {ground_truth}")
    print(f"       PR: {prediction}")
    print(f"       ({n_input_tokens} tokens in, {elapsed:.1f}s)")
    print()

# ── Summary ────────────────────────────────────────────────────────────────
print("=" * 60)
print(f"event_type accuracy: {correct_type}/{N_SAMPLES} = {correct_type/N_SAMPLES:.0%}")
print("=" * 60)
