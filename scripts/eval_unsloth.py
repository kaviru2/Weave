#!/usr/bin/env python3
"""Eval script using Unsloth-loaded adapter — avoids re-downloading base model."""
import json, time, torch
from collections import defaultdict
from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="/root/lora_adapter",
    max_seq_length=4096,
    load_in_4bit=True,
)
FastLanguageModel.for_inference(model)
print("Model ready.\n")

with open("/root/val_point_dups.jsonl") as f:
    examples = [json.loads(l) for l in f]

print(f"Evaluating {len(examples)} examples...")
correct, total = 0, 0
per_pattern = defaultdict(lambda: {"correct": 0, "total": 0})
per_nd      = defaultdict(lambda: {"correct": 0, "total": 0})
per_example = []
t0 = time.time()

for i, ex in enumerate(examples):
    messages    = ex["messages"]
    gt          = messages[-1]["content"]
    pattern     = ex.get("concurrency_pattern", "unknown")
    nd          = ex.get("nondeterminism", "unknown")
    prompt_msgs = [m for m in messages if m["role"] != "assistant"]
    prompt = tokenizer.apply_chat_template(prompt_msgs, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=4096).to("cuda")
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=60, do_sample=False,
                             pad_token_id=tokenizer.eos_token_id)
    pred = tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
    gt_t = pred_t = None
    try: gt_t   = json.loads(gt).get("event_type")
    except Exception: pass
    try: pred_t = json.loads(pred).get("event_type")
    except Exception: pass
    match = bool(gt_t and pred_t and gt_t == pred_t)
    if match: correct += 1
    total += 1
    per_pattern[pattern]["total"] += 1
    per_nd[nd]["total"] += 1
    if match:
        per_pattern[pattern]["correct"] += 1
        per_nd[nd]["correct"] += 1
    per_example.append({"index": i, "ground_truth": gt, "prediction": pred,
                        "match": match, "pattern": pattern, "nondeterminism": nd})
    if (i + 1) % 10 == 0:
        elapsed = time.time() - t0
        print(f"  [{i+1:3d}/{total}]  {correct}/{i+1} = {correct/(i+1):.1%}  ({elapsed:.0f}s)")

elapsed = time.time() - t0
sep = "=" * 60
print(f"\n{sep}")
print(f"  event_type accuracy : {correct}/{total} = {correct/total:.1%}")
print(f"  1.5B fine-tuned baseline: 40.2%")
print(f"  Elapsed: {elapsed:.0f}s")
print(sep)

print("\n  By concurrency pattern:")
for p, c in sorted(per_pattern.items()):
    acc = c["correct"] / c["total"] if c["total"] else 0
    print(f"    {p:<22} {c['correct']:3d}/{c['total']:3d} = {acc:.1%}")

print("\n  By nondeterminism level:")
for n, c in sorted(per_nd.items()):
    acc = c["correct"] / c["total"] if c["total"] else 0
    print(f"    {n:<10} {c['correct']:3d}/{c['total']:3d} = {acc:.1%}")

results = {
    "model": "Qwen2.5-Coder-7B-Instruct (QLoRA Unsloth)",
    "total": total, "correct": correct, "accuracy": correct / total,
    "baseline_1.5b_finetuned": 0.402, "baseline_zeroshot": 0.56,
    "elapsed_seconds": elapsed,
    "by_pattern":       {k: v for k, v in per_pattern.items()},
    "by_nondeterminism":{k: v for k, v in per_nd.items()},
    "per_example": per_example,
}
with open("/root/eval_results.json", "w") as f:
    json.dump(results, f, indent=2)
print("\nSaved to /root/eval_results.json")
