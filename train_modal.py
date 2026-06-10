#!/usr/bin/env python3
"""
train_modal.py

Single-command Weave QLoRA fine-tune + eval on Modal A10G GPU (~40 min, ~$0.50).
Trains Qwen2.5-Coder-1.5B-Instruct on the pre-truncated Weave dataset, then
immediately evaluates the adapter on the full val set and prints accuracy vs
the 56% zero-shot baseline.

Setup (one-time):
    pip install modal
    modal setup          # browser auth

Run:
    modal run train_modal.py

Download adapter after run:
    modal volume get weave-output lora_adapter ./dataset/output/lora_adapter_v2
"""

import modal
import os
import json

# ── Image: all ML deps pre-installed ─────────────────────────────────────────
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch",
        "transformers>=4.40.0",
        "peft>=0.10.0",
        "trl>=0.9.0",
        "bitsandbytes>=0.43.0",
        "accelerate>=0.28.0",
        "datasets>=2.18.0",
    )
)

# ── Persistent volume for adapter + eval results ──────────────────────────────
output_vol = modal.Volume.from_name("weave-output", create_if_missing=True)

# ── Local files to mount into the container ───────────────────────────────────
mounts = [
    modal.Mount.from_local_file(
        "dataset/output/kaggle_upload/train_point_dups.jsonl",
        remote_path="/data/train.jsonl",
    ),
    modal.Mount.from_local_file(
        "dataset/output/kaggle_upload/val_point_dups.jsonl",
        remote_path="/data/val.jsonl",
    ),
    modal.Mount.from_local_file(
        "dataset/train_lora.py",
        remote_path="/scripts/train_lora.py",
    ),
]

app = modal.App("weave-ccwm")


@app.function(
    gpu="L4",
    image=image,
    mounts=mounts,
    volumes={"/output": output_vol},
    timeout=7200,
)
def train_and_eval():
    import subprocess
    import sys
    import json
    import time
    import os
    import torch
    from collections import defaultdict
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    os.environ["HF_HUB_DISABLE_XET"] = "1"

    # ── Phase 1: Train ────────────────────────────────────────────────────────
    print("=" * 65)
    print("PHASE 1: TRAINING")
    print("=" * 65)

    subprocess.run(
        [
            sys.executable, "/scripts/train_lora.py",
            "--model_id",       "Qwen/Qwen2.5-Coder-1.5B-Instruct",
            "--train_file",     "/data/train.jsonl",
            "--val_file",       "/data/val.jsonl",
            "--output_dir",     "/output/lora_adapter",
            "--epochs",         "3",
            "--batch_size",     "4",
            "--grad_accum",     "2",
            "--max_seq_length", "4096",
        ],
        check=True,
    )
    print("\nTraining complete. Adapter saved to /output/lora_adapter")

    # ── Phase 2: Eval ─────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("PHASE 2: EVALUATION")
    print("=" * 65)

    BASE_MODEL   = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
    ADAPTER_PATH = "/output/lora_adapter"
    VAL_FILE     = "/data/val.jsonl"
    MAX_NEW_TOKENS = 60

    print(f"Loading base model: {BASE_MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )
    print(f"Loading LoRA adapter: {ADAPTER_PATH}")
    model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
    model.eval()
    print("Model ready.\n")

    with open(VAL_FILE) as f:
        examples = [json.loads(line) for line in f]
    print(f"Evaluating {len(examples)} examples...")

    correct_type = 0
    total        = 0
    per_pattern  = defaultdict(lambda: {"correct": 0, "total": 0})
    per_nd       = defaultdict(lambda: {"correct": 0, "total": 0})
    confusion    = defaultdict(lambda: defaultdict(int))
    per_example  = []
    device       = torch.device("cuda")

    t_start = time.time()

    for i, ex in enumerate(examples):
        messages     = ex["messages"]
        ground_truth = messages[-1]["content"]
        pattern      = ex.get("concurrency_pattern", "unknown")
        nd_level     = ex.get("nondeterminism", "unknown")

        prompt_messages = [m for m in messages if m["role"] != "assistant"]

        prompt = tokenizer.apply_chat_template(
            prompt_messages, tokenize=False, add_generation_prompt=True,
        )
        inputs = tokenizer(
            prompt, return_tensors="pt",
            truncation=True, max_length=4096, truncation_side="left",
        ).to(device)

        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )

        new_tokens = output_ids[0][inputs["input_ids"].shape[1]:]
        prediction = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

        gt_type = pred_type = None
        match = False
        try:
            gt_type = json.loads(ground_truth).get("event_type")
        except Exception:
            pass
        try:
            pred_type = json.loads(prediction).get("event_type")
        except Exception:
            pass

        if gt_type and pred_type and gt_type == pred_type:
            match = True
            correct_type += 1

        # Print first 5 for a sanity check
        if i < 5:
            status = "✓" if match else "✗"
            print(f"  [{i+1}] {status}  GT={ground_truth}  PR={prediction}")

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
            elapsed = time.time() - t_start
            print(f"  [{i+1:3d}/{total}]  accuracy: {correct_type}/{i+1} = {correct_type/(i+1):.1%}  ({elapsed:.0f}s)")

    elapsed_total = time.time() - t_start

    print("\n" + "=" * 65)
    print(f"  event_type accuracy : {correct_type}/{total} = {correct_type/total:.1%}")
    print(f"  Zero-shot baseline  : 56.0%")
    print(f"  Elapsed             : {elapsed_total:.0f}s")
    print("=" * 65)

    print("\n  By concurrency pattern:")
    for pat, counts in sorted(per_pattern.items()):
        acc = counts["correct"] / counts["total"] if counts["total"] else 0
        print(f"    {pat:<20}  {counts['correct']:3d}/{counts['total']:3d} = {acc:.1%}")

    print("\n  By nondeterminism level:")
    for nd, counts in sorted(per_nd.items()):
        acc = counts["correct"] / counts["total"] if counts["total"] else 0
        print(f"    {nd:<10}  {counts['correct']:3d}/{counts['total']:3d} = {acc:.1%}")

    results = {
        "model":              BASE_MODEL,
        "total_examples":     total,
        "correct":            correct_type,
        "accuracy":           correct_type / total,
        "zero_shot_baseline": 0.56,
        "elapsed_seconds":    elapsed_total,
        "by_pattern":         {k: v for k, v in per_pattern.items()},
        "by_nondeterminism":  {k: v for k, v in per_nd.items()},
        "confusion":          {gt: dict(row) for gt, row in confusion.items()},
        "per_example":        per_example,
    }

    with open("/output/eval_results.json", "w") as f:
        json.dump(results, f, indent=2)
    output_vol.commit()
    print("\nResults + adapter saved to Modal volume 'weave-output'.")

    return results


@app.local_entrypoint()
def main():
    print("Launching Modal A10G job (train 3 epochs + full eval)...")
    print("Logs will stream here in real-time.\n")

    results = train_and_eval.remote()

    os.makedirs("eval/results", exist_ok=True)
    out_path = "eval/results/eval_results_modal.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*65}")
    print(f"  Final accuracy : {results['correct']}/{results['total_examples']} = {results['accuracy']:.1%}")
    print(f"  Zero-shot      : 56.0%")
    print(f"  Results saved  : {out_path}")
    print(f"{'='*65}")
    print(f"\nTo download the adapter locally:")
    print(f"  modal volume get weave-output lora_adapter ./dataset/output/lora_adapter_v2")
