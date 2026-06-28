#!/usr/bin/env python3
"""
scripts/eval_unsloth_traj.py — Unsloth-accelerated evaluation script.
Loads model + LoRA adapter via Unsloth for fast GPU inference.
Usage:
    python scripts/eval_unsloth_traj.py \
        --adapter  /root/lora_adapter_traj \
        --val_file /root/val_point_dups.jsonl \
        --out_file /root/eval_results_qwen25_wrapper_1287.json
"""
import argparse
import json
import time
import os
from collections import defaultdict
import torch

# Ensure HuggingFace environment variables are set
os.environ["HF_HUB_DISABLE_XET"] = "1"

MAX_NEW_TOKENS = 60

def evaluate(model, tokenizer, examples, device, args):
    """Run eval loop and return results dict."""
    correct = 0
    total   = 0
    per_pattern = defaultdict(lambda: {"correct": 0, "total": 0})
    per_nd      = defaultdict(lambda: {"correct": 0, "total": 0})
    confusion   = defaultdict(lambda: defaultdict(int))
    per_example = []
    t0 = time.time()

    print(f"\nEvaluating {len(examples)} examples using Unsloth...")
    for i, ex in enumerate(examples):
        messages     = ex["messages"]
        ground_truth = messages[-1]["content"]
        pattern      = ex.get("concurrency_pattern", "unknown")
        nd_level     = ex.get("nondeterminism", "unknown")

        prompt_msgs = [m for m in messages if m["role"] != "assistant"]
        prompt = tokenizer.apply_chat_template(
            prompt_msgs, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(
            prompt, return_tensors="pt",
            truncation=True, max_length=args.max_tokens,
        ).to(device)

        with torch.no_grad():
            out_ids = model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )

        new_tokens = out_ids[0][inputs["input_ids"].shape[1]:]
        prediction = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

        gt_type = pred_type = None
        match = False
        try: gt_type   = json.loads(ground_truth).get("event_type")
        except Exception: pass
        try: pred_type = json.loads(prediction).get("event_type")
        except Exception: pass

        if gt_type and pred_type and gt_type == pred_type:
            match = True
            correct += 1

        total += 1
        per_pattern[pattern]["total"] += 1
        per_nd[nd_level]["total"]     += 1
        confusion[gt_type or "parse_err"][pred_type or "parse_err"] += 1
        if match:
            per_pattern[pattern]["correct"] += 1
            per_nd[nd_level]["correct"]     += 1

        per_example.append({
            "index": i, "ground_truth": ground_truth,
            "prediction": prediction, "match": match,
            "pattern": pattern, "nondeterminism": nd_level,
        })

        if (i + 1) % 10 == 0 or (i + 1) == len(examples):
            elapsed = time.time() - t0
            avg_speed = elapsed / (i + 1)
            eta = avg_speed * (len(examples) - (i + 1))
            print(f"  [{i+1:4d}/{len(examples)}]  {correct}/{i+1} = {correct/(i+1):.1%}  (elapsed: {elapsed:.0f}s, speed: {avg_speed:.2f}s/ex, ETA: {eta:.0f}s)")

    elapsed = time.time() - t0
    sep = "=" * 65
    print(f"\n{sep}")
    print(f"  event_type accuracy : {correct}/{total} = {correct/total:.1%}")
    print(f"  Elapsed : {elapsed:.0f}s")
    print(sep)

    print("\n  By concurrency pattern:")
    for pat, c in sorted(per_pattern.items()):
        acc = c["correct"]/c["total"] if c["total"] else 0
        print(f"    {pat:<20}  {c['correct']:3d}/{c['total']:3d} = {acc:.1%}")

    print("\n  By nondeterminism level:")
    for nd, c in sorted(per_nd.items()):
        acc = c["correct"]/c["total"] if c["total"] else 0
        print(f"    {nd:<10}  {c['correct']:3d}/{c['total']:3d} = {acc:.1%}")

    # Print Confusion Matrix Table
    print("\n  Confusion Matrix:")
    events_list = sorted(list(set(list(confusion.keys()) + [p for r in confusion.values() for p in r.keys()])))
    header = f"    {'Ground Truth':<12} | " + " | ".join(f"{ev[:8]:<8}" for ev in events_list)
    print(header)
    print("    " + "-" * len(header))
    for gt in events_list:
        row = f"    {gt[:12]:<12} | " + " | ".join(f"{confusion[gt][pred]:<8}" for pred in events_list)
        print(row)

    return {
        "model": "Qwen2.5-Coder-7B-Instruct (Unsloth Inference)",
        "adapter": args.adapter,
        "total_examples": total, "correct": correct,
        "accuracy": correct/total,
        "elapsed_seconds": elapsed,
        "by_pattern":       {k: v for k, v in per_pattern.items()},
        "by_nondeterminism":{k: v for k, v in per_nd.items()},
        "confusion":        {gt: dict(row) for gt, row in confusion.items()},
        "per_example":      per_example,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter",    required=True)
    parser.add_argument("--val_file",   required=True)
    parser.add_argument("--out_file",   default="eval_results.json")
    parser.add_argument("--max_tokens", type=int, default=6144)
    args = parser.parse_args()

    # Enable Unsloth Model Loading
    try:
        from unsloth import FastLanguageModel
    except ImportError:
        print("Unsloth is not installed. Standalone inference mode requires Unsloth.")
        sys.exit(1)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}  |  Max Tokens: {args.max_tokens}")
    print(f"Loading Unsloth model with adapter: {args.adapter}")

    # Load FastLanguageModel directly with adapter path
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.adapter,
        max_seq_length=args.max_tokens,
        load_in_4bit=True,
    )
    FastLanguageModel.for_inference(model)
    print("Model loaded & optimized for fast inference.\n")

    with open(args.val_file) as f:
        examples = [json.loads(line) for line in f]

    results = evaluate(model, tokenizer, examples, device, args)
    with open(args.out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results successfully saved to: {args.out_file}")

if __name__ == "__main__":
    main()
