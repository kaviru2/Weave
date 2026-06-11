#!/usr/bin/env python3
"""
dataset/train_lora_unsloth.py

Unsloth-accelerated QLoRA fine-tuning for Weave CCWM.
Targets Qwen2.5-Coder-7B-Instruct on a single RTX 4000 Ada (20GB VRAM).
Uses Unsloth's fused kernels and gradient checkpointing to fit 7B at seq_len=4096
with batch_size=1, grad_accum=8 without OOM.

Usage (RunPod):
    python train_lora_unsloth.py \
        --model_id Qwen/Qwen2.5-Coder-7B-Instruct \
        --train_file /root/train_point_dups.jsonl \
        --val_file   /root/val_point_dups.jsonl \
        --output_dir /root/lora_adapter \
        --epochs 3
"""

import os
import sys
import json
import argparse
import logging
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def train(args: argparse.Namespace):
    logging.info("=== WEAVE UNSLOTH 7B TRAINING ===")

    try:
        from unsloth import FastLanguageModel
    except ImportError:
        logging.error("Unsloth not installed. Run: pip install unsloth")
        sys.exit(1)

    import torch
    from datasets import load_dataset
    from trl import SFTTrainer, SFTConfig

    logging.info(f"Loading model: {args.model_id}  (4-bit, seq={args.max_seq_length})")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model_id,
        max_seq_length=args.max_seq_length,
        load_in_4bit=True,
        dtype=None,  # auto-detect bfloat16/float16
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    trainable, total = model.get_nb_trainable_parameters()
    logging.info(f"Trainable params: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

    logging.info("Loading datasets...")
    dataset = load_dataset(
        "json",
        data_files={"train": args.train_file, "validation": args.val_file},
    )
    logging.info(f"Train: {len(dataset['train'])}  |  Val: {len(dataset['validation'])}")

    # Pre-apply chat template so Unsloth sees a plain "text" column — avoids
    # batched vs unbatched formatting_func ambiguity in Unsloth's SFTTrainer.
    def apply_template(example):
        return {"text": tokenizer.apply_chat_template(example["messages"], tokenize=False)}

    dataset = dataset.map(apply_template, num_proc=2)

    training_args = SFTConfig(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        eval_strategy="epoch",
        save_strategy="epoch",
        learning_rate=args.lr,
        weight_decay=0.01,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        logging_steps=10,
        bf16=True,
        fp16=False,
        gradient_checkpointing=True,
        optim="adamw_8bit",
        report_to="none",
        load_best_model_at_end=False,
        max_seq_length=args.max_seq_length,
        dataset_text_field="text",
        dataset_num_proc=2,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        args=training_args,
    )

    logging.info("Starting training...")
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    trainer.train()

    logging.info(f"Saving adapter to {args.output_dir}")
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    logging.info("Training complete.")


def run_merge(args: argparse.Namespace):
    logging.info("=== MERGING ADAPTER ===")
    try:
        from unsloth import FastLanguageModel
    except ImportError:
        logging.error("Unsloth not installed.")
        sys.exit(1)

    if not args.merge_dir:
        logging.error("Specify --merge_dir")
        sys.exit(1)

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.output_dir,
        max_seq_length=args.max_seq_length,
        load_in_4bit=True,
    )
    os.makedirs(args.merge_dir, exist_ok=True)
    model.save_pretrained_merged(args.merge_dir, tokenizer, save_method="merged_16bit")
    logging.info(f"Merged model saved to {args.merge_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unsloth 7B QLoRA training for Weave CCWM")
    parser.add_argument("--model_id",      default="Qwen/Qwen2.5-Coder-7B-Instruct")
    parser.add_argument("--train_file",    default="dataset/output/train_point_dups.jsonl")
    parser.add_argument("--val_file",      default="dataset/output/val_point_dups.jsonl")
    parser.add_argument("--output_dir",    default="dataset/output/lora_adapter")
    parser.add_argument("--epochs",        type=int,   default=3)
    parser.add_argument("--batch_size",    type=int,   default=1)
    parser.add_argument("--grad_accum",    type=int,   default=8)
    parser.add_argument("--lr",            type=float, default=2e-4)
    parser.add_argument("--max_seq_length",type=int,   default=4096)
    parser.add_argument("--lora_r",        type=int,   default=16)
    parser.add_argument("--lora_alpha",    type=int,   default=32)
    parser.add_argument("--lora_dropout",  type=float, default=0.05)
    parser.add_argument("--merge",         action="store_true")
    parser.add_argument("--merge_dir",     default="dataset/output/merged_model")
    args = parser.parse_args()

    if args.merge:
        run_merge(args)
    else:
        train(args)
