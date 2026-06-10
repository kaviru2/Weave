#!/usr/bin/env python3
"""
scripts/run_eval.py — standalone eval script. Works on CUDA (RunPod), MPS (Mac
Apple Silicon), and CPU. No bitsandbytes required — loads in float16/bfloat16.

Usage:
    # Mac (M-series):
    uv run python scripts/run_eval.py \
        --adapter  dataset/output/lora_adapter_v2 \
        --val_file dataset/output/kaggle_upload/val_point_dups.jsonl

    # RunPod / CUDA:
    python run_eval.py \
        --adapter  /root/lora_adapter \
        --val_file /root/val_point_dups.jsonl \
        --out_file /root/eval_results.json
"""
import argparse, json, time, os
from collections import defaultdict
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

os.environ["HF_HUB_DISABLE_XET"] = "1"

MAX_NEW_TOKENS = 60


def get_device():
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter",  required=True)
    parser.add_argument("--val_file", required=True)
    parser.add_argument("--model_id", default="Qwen/Qwen2.5-Coder-1.5B-Instruct")
    parser.add_argument("--out_file", default="eval_results.json")
    parser.add_argument("--max_tokens", type=int, default=4096)
    args = parser.parse_args()

    device = get_device()
    # MPS works best with bfloat16; CUDA and CPU use float16
    dtype = torch.bfloat16 if device.type == "mps" else torch.float16
    print(f"Device: {device}  |  dtype: {dtype}")
    print(f"Loading base model: {args.model_id}")

    tokenizer = AutoTokenizer.from_pretrained(args.model_id, trust_remote_code=True)
    tokenizer.truncation_side = "left"
    base_model = AutoModelForCausalLM.from_pretrained(
        args.model_id,
        torch_dtype=dtype,
        # device_map="auto" only works on CUDA; for MPS/CPU load then move manually
        device_map="auto" if device.type == "cuda" else None,
        trust_remote_code=True,
    )
    if device.type != "cuda":
        base_model = base_model.to(device)

    print(f"Loading adapter: {args.adapter}")
    model = PeftModel.from_pretrained(base_model, args.adapter)
    model.eval()
    print("Model ready.\n")

    with open(args.val_file) as f:
        examples = [json.loads(line) for line in f]
    print(f"Evaluating {len(examples)} examples...")

    correct = 0
    total   = 0
    per_pattern = defaultdict(lambda: {"correct": 0, "total": 0})
    per_nd      = defaultdict(lambda: {"correct": 0, "total": 0})
    confusion   = defaultdict(lambda: defaultdict(int))
    per_example = []
    t0 = time.time()

    for i, ex in enumerate(examples):
        messages     = ex["messages"]
        ground_truth = messages[-1]["content"]
        pattern      = ex.get("concurrency_pattern", "unknown")
        nd_level     = ex.get("nondeterminism", "unknown")

        prompt_msgs = [m for m in messages if m["role"] != "assistant"]
        prompt = tokenizer.apply_chat_template(
            prompt_msgs, tokenize=False, add_generation_prompt=True,
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

        if (i + 1) % 10 == 0:
            elapsed = time.time() - t0
            print(f"  [{i+1:3d}/{total}]  {correct}/{i+1} = {correct/(i+1):.1%}  ({elapsed:.0f}s)")

    elapsed = time.time() - t0

    print("\n" + "=" * 65)
    print(f"  event_type accuracy : {correct}/{total} = {correct/total:.1%}")
    print(f"  Zero-shot baseline  : 56.0%")
    print(f"  Elapsed             : {elapsed:.0f}s")
    print("=" * 65)

    print("\n  By concurrency pattern:")
    for pat, c in sorted(per_pattern.items()):
        acc = c["correct"]/c["total"] if c["total"] else 0
        print(f"    {pat:<20}  {c['correct']:3d}/{c['total']:3d} = {acc:.1%}")

    print("\n  By nondeterminism level:")
    for nd, c in sorted(per_nd.items()):
        acc = c["correct"]/c["total"] if c["total"] else 0
        print(f"    {nd:<10}  {c['correct']:3d}/{c['total']:3d} = {acc:.1%}")

    results = {
        "model": args.model_id, "adapter": args.adapter,
        "total_examples": total, "correct": correct,
        "accuracy": correct/total, "zero_shot_baseline": 0.56,
        "elapsed_seconds": elapsed,
        "by_pattern":       {k: v for k, v in per_pattern.items()},
        "by_nondeterminism":{k: v for k, v in per_nd.items()},
        "confusion":        {gt: dict(row) for gt, row in confusion.items()},
        "per_example":      per_example,
    }
    with open(args.out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to: {args.out_file}")


if __name__ == "__main__":
    main()
