#!/usr/bin/env python3
"""
dataset/train_lora_trajectory.py — Phase 16

Unsloth-accelerated QLoRA fine-tuning on multi-turn trajectory examples.
Differs from train_lora_unsloth.py in two ways:
  1. Trains on train_trajectory.jsonl (3–5 step multi-turn conversations)
  2. Uses train_on_responses_only so loss is computed only on assistant turns,
     not on the growing trace context in user turns.

Usage (RunPod):
    python train_lora_trajectory.py \
        --train_file /root/train_trajectory.jsonl \
        --val_file   /root/val_trajectory.jsonl \
        --output_dir /root/lora_adapter_traj \
        --epochs 3
"""

import os
import sys
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def train(args: argparse.Namespace) -> None:
    logging.info("=== WEAVE TRAJECTORY TRAINING (Phase 16) ===")

    try:
        from unsloth import FastLanguageModel
    except ImportError:
        logging.error("Unsloth not installed. Run: pip install unsloth")
        sys.exit(1)

    from datasets import load_dataset
    from trl import SFTTrainer, SFTConfig

    logging.info(f"Loading model: {args.model_id}  (4-bit, seq={args.max_seq_length})")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model_id,
        max_seq_length=args.max_seq_length,
        load_in_4bit=True,
        dtype=None,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
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

    logging.info("Loading trajectory datasets...")
    dataset = load_dataset(
        "json",
        data_files={"train": args.train_file, "validation": args.val_file},
    )
    logging.info(f"Train: {len(dataset['train'])}  |  Val: {len(dataset['validation'])}")

    def apply_template(example):
        return {"text": tokenizer.apply_chat_template(
            example["messages"], tokenize=False, add_generation_prompt=False,
            enable_thinking=False,
        )}

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

    logging.info("Starting trajectory training...")
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    trainer.train()

    logging.info(f"Saving adapter → {args.output_dir}")
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    logging.info("Trajectory training complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 16: trajectory QLoRA training")
    parser.add_argument("--model_id",       default="Qwen/Qwen3-8B-Instruct")
    parser.add_argument("--train_file",     default="/root/train_trajectory.jsonl")
    parser.add_argument("--val_file",       default="/root/val_trajectory.jsonl")
    parser.add_argument("--output_dir",     default="/root/lora_adapter_traj")
    parser.add_argument("--epochs",         type=int,   default=3)
    # Trajectory seqs are ~3-5x longer than single-step; reduce batch or use larger seq
    parser.add_argument("--batch_size",     type=int,   default=1)
    parser.add_argument("--grad_accum",     type=int,   default=8)
    parser.add_argument("--lr",             type=float, default=2e-4)
    parser.add_argument("--max_seq_length", type=int,   default=6144)
    parser.add_argument("--lora_r",         type=int,   default=16)
    parser.add_argument("--lora_alpha",     type=int,   default=32)
    parser.add_argument("--lora_dropout",   type=float, default=0.05)
    args = parser.parse_args()
    train(args)
