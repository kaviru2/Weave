#!/usr/bin/env python3
"""
eval/inference_check.py

Quick inference check: loads the trained LoRA adapter on top of
Qwen/Qwen2.5-Coder-1.5B-Instruct and runs it on 10 validation examples.
Prints predicted vs ground-truth next scheduler event for each.

Run from repo root:
    .venv/bin/python3 eval/inference_check.py
"""

import json
import os
import random
import torch

# Use standard HTTP download — XET chunked system stalls on slow connections
os.environ["HF_HUB_DISABLE_XET"] = "1"
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_MODEL   = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
ADAPTER_PATH = "dataset/output/lora_adapter"  # final 3-epoch adapter
VAL_FILE     = "dataset/output/val_point_dups.jsonl"
N_SAMPLES    = 10
MAX_NEW_TOKENS = 60

# ── Device ─────────────────────────────────────────────────────────────────
# Use CPU — MPS OOMs when other apps are using memory on 18GB unified RAM
DEVICE = torch.device("cpu")
print("Using CPU")

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
    messages = ex["messages"]
    ground_truth = messages[-1]["content"]  # assistant response

    # Build prompt from system + user only (no assistant turn)
    prompt_messages = [m for m in messages if m["role"] != "assistant"]
    prompt = tokenizer.apply_chat_template(
        prompt_messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    # Truncate to 512 tokens — CPU attention is O(n²), long contexts are glacially slow
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512).to(DEVICE)
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,          # greedy — deterministic
            pad_token_id=tokenizer.eos_token_id,
        )

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
    print()

# ── Summary ────────────────────────────────────────────────────────────────
print("=" * 60)
print(f"event_type accuracy: {correct_type}/{N_SAMPLES} = {correct_type/N_SAMPLES:.0%}")
print("=" * 60)
