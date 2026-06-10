#!/usr/bin/env python3
"""
eval/kaggle_eval.py

Full 363-sample evaluation of the fine-tuned LoRA adapter on the Weave-Bench
validation set. Designed to run on Kaggle GPU (T4) for a proper apples-to-apples
comparison against the Phase 4 zero-shot baseline (56% event_type accuracy).

On Kaggle, mount the adapter as a dataset at /kaggle/input/weave-lora-adapter/
and the val file at /kaggle/input/weave-sft-dataset/val_point_dups.jsonl.

Run from Kaggle notebook cell:
    !python /kaggle/working/kaggle_eval.py

Or from repo root (CPU, slow — use inference_check.py for local quick checks):
    .venv/bin/python3 eval/kaggle_eval.py
"""

import json
import os
import re
import sys
import time
import torch
from collections import defaultdict

os.environ["HF_HUB_DISABLE_XET"] = "1"
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

# ── Paths — auto-detect Kaggle vs local ───────────────────────────────────
if os.path.exists("/kaggle/input"):
    BASE_MODEL   = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
    ADAPTER_PATH = "/kaggle/input/weave-lora-adapter"
    VAL_FILE     = "/kaggle/input/weave-sft-dataset/val_point_dups.jsonl"
    RESULTS_PATH = "/kaggle/working/eval_results_lora.json"
    MAX_TOKENS   = 2048   # T4 GPU: 3GB model + 2048-token KV cache fits easily in 14.5GB
    DEVICE_STR   = "cuda"
else:
    BASE_MODEL   = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
    ADAPTER_PATH = "dataset/output/lora_adapter"
    VAL_FILE     = "dataset/output/val_point_dups.jsonl"
    RESULTS_PATH = "eval/results/eval_results_lora.json"
    MAX_TOKENS   = 1024   # CPU fallback — still uses slim trace to stay under 1024
    DEVICE_STR   = "cpu"

MAX_NEW_TOKENS = 60
ALL_EVENT_TYPES = ["GoBlock", "GoCreate", "GoEnd", "GoSched", "GoStart", "GoUnblock"]


def smart_truncate_messages(messages, tokenizer, max_tokens):
    """
    Fit the prompt within max_tokens while preserving the critical tail.

    On Kaggle GPU (max_tokens=2048): uses the ORIGINAL full trace format — same as
    training distribution. Left-truncation cuts the program body if the prompt exceeds
    2048 tokens, but keeps full current_state + prediction request.

    On CPU fallback (max_tokens=1024): slims trace events to {event_id, event_type,
    goroutine_id} to stay within budget.
    """
    system_msg   = messages[0]
    user_content = messages[1]["content"]

    # For large budgets, use the original prompt directly (stays in training distribution)
    if max_tokens >= 2048:
        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        return tokenizer(
            prompt, return_tensors="pt",
            truncation=True, max_length=max_tokens,
            truncation_side="left",   # cut program body first, preserve tail
        )

    # CPU fallback: slim trace events to keep within 1024 tokens
    prog_match  = re.search(r"<program>(.*?)</program>",             user_content, re.DOTALL)
    trace_match = re.search(r"<trace>(.*?)</trace>",                 user_content, re.DOTALL)
    state_match = re.search(r"<current_state>(.*?)</current_state>", user_content, re.DOTALL)

    prog_head = "\n".join(prog_match.group(1).strip().split("\n")[:15]) if prog_match else ""

    if trace_match:
        try:
            events = json.loads(trace_match.group(1).strip())
            slim_events = [
                {"event_id": ev.get("event_id"), "event_type": ev.get("event_type"),
                 "goroutine_id": ev.get("goroutine_id")}
                for ev in events[-5:]
            ]
            trace_short = json.dumps(slim_events, indent=2)
        except (json.JSONDecodeError, TypeError):
            trace_short = ""
    else:
        trace_short = ""

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
        reconstructed, tokenize=False, add_generation_prompt=True,
    )
    return tokenizer(
        prompt, return_tensors="pt",
        truncation=True, max_length=max_tokens,
        truncation_side="left",
    )


def main():
    device = torch.device(DEVICE_STR)
    print(f"Device: {device}")
    print(f"Adapter: {ADAPTER_PATH}")
    print(f"Val file: {VAL_FILE}")

    # ── Load model ────────────────────────────────────────────────────────
    print(f"\nLoading base model: {BASE_MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)

    load_kwargs = {"trust_remote_code": True, "torch_dtype": torch.float16}
    if DEVICE_STR == "cuda":
        load_kwargs["device_map"] = "auto"

    base_model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, **load_kwargs)
    print(f"Loading LoRA adapter: {ADAPTER_PATH}")
    model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
    if DEVICE_STR != "cuda":
        model = model.to(device)
    model.eval()
    print("Model ready.\n")

    # ── Load val examples ─────────────────────────────────────────────────
    with open(VAL_FILE) as f:
        examples = [json.loads(line) for line in f]
    print(f"Evaluating {len(examples)} examples...\n")

    # ── Eval loop ─────────────────────────────────────────────────────────
    correct_type  = 0
    total         = 0
    per_pattern   = defaultdict(lambda: {"correct": 0, "total": 0})
    per_nd        = defaultdict(lambda: {"correct": 0, "total": 0})
    confusion     = defaultdict(lambda: defaultdict(int))  # confusion[gt][pred]
    per_example   = []

    t_start = time.time()

    for i, ex in enumerate(examples):
        messages     = ex["messages"]
        ground_truth = messages[-1]["content"]
        pattern      = ex.get("concurrency_pattern", "unknown")
        nd_level     = ex.get("nondeterminism", "unknown")

        prompt_messages = [m for m in messages if m["role"] != "assistant"]

        inputs = smart_truncate_messages(prompt_messages, tokenizer, MAX_TOKENS).to(device)

        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )

        new_tokens = output_ids[0][inputs["input_ids"].shape[1]:]
        prediction = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

        gt_type   = None
        pred_type = None
        match     = False
        try:
            gt_json   = json.loads(ground_truth)
            gt_type   = gt_json.get("event_type")
        except json.JSONDecodeError:
            pass
        try:
            pred_json = json.loads(prediction)
            pred_type = pred_json.get("event_type")
        except json.JSONDecodeError:
            pass

        if gt_type and pred_type and gt_type == pred_type:
            match = True
            correct_type += 1

        total += 1
        per_pattern[pattern]["total"]   += 1
        per_nd[nd_level]["total"]       += 1
        confusion[gt_type or "parse_err"][pred_type or "parse_err"] += 1
        if match:
            per_pattern[pattern]["correct"] += 1
            per_nd[nd_level]["correct"]     += 1

        per_example.append({
            "index":        i,
            "ground_truth": ground_truth,
            "prediction":   prediction,
            "match":        match,
            "pattern":      pattern,
            "nondeterminism": nd_level,
        })

        if (i + 1) % 20 == 0:
            elapsed = time.time() - t_start
            print(f"  [{i+1:3d}/{total}] running accuracy: {correct_type}/{i+1} = {correct_type/(i+1):.1%}  ({elapsed:.0f}s elapsed)")

    elapsed_total = time.time() - t_start

    # ── Print results ─────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print(f"  event_type accuracy: {correct_type}/{total} = {correct_type/total:.1%}")
    print(f"  Zero-shot baseline (Phase 4):  56.0%")
    print(f"  Elapsed: {elapsed_total:.0f}s")
    print("=" * 65)

    print("\n  By concurrency pattern:")
    for pat, counts in sorted(per_pattern.items()):
        acc = counts["correct"] / counts["total"] if counts["total"] else 0
        print(f"    {pat:<20}  {counts['correct']:3d}/{counts['total']:3d} = {acc:.1%}")

    print("\n  By nondeterminism level:")
    for nd, counts in sorted(per_nd.items()):
        acc = counts["correct"] / counts["total"] if counts["total"] else 0
        print(f"    {nd:<10}  {counts['correct']:3d}/{counts['total']:3d} = {acc:.1%}")

    print("\n  Confusion matrix (rows = ground truth, cols = predicted):")
    all_types_seen = sorted(set(list(confusion.keys()) + [t for row in confusion.values() for t in row]))
    header = "          " + "  ".join(f"{t[:8]:>8}" for t in all_types_seen)
    print("  " + header)
    for gt in all_types_seen:
        row_str = f"  {gt[:8]:>8}  " + "  ".join(
            f"{confusion[gt].get(pred, 0):>8d}" for pred in all_types_seen
        )
        print(row_str)

    # ── Save results ──────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    output = {
        "model":           BASE_MODEL,
        "adapter":         ADAPTER_PATH,
        "total_examples":  total,
        "correct":         correct_type,
        "accuracy":        correct_type / total,
        "zero_shot_baseline": 0.56,
        "elapsed_seconds": elapsed_total,
        "by_pattern":      {k: v for k, v in per_pattern.items()},
        "by_nondeterminism": {k: v for k, v in per_nd.items()},
        "confusion":       {gt: dict(row) for gt, row in confusion.items()},
        "per_example":     per_example,
    }
    with open(RESULTS_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Results saved to: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
