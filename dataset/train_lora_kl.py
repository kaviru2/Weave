#!/usr/bin/env python3
"""
Phase 14 — Distribution-loss training (KL divergence against empirical distributions).

Trains Qwen2.5-Coder-7B-Instruct with a mixed loss:
  total_loss = CE_loss (all output tokens) + kl_weight * KL_loss (event_type token only)

The KL loss compares the model's softmax distribution over the six event-type vocabulary
tokens at the event_type prediction position against the empirical distribution derived
from multiple runs of the same program at the same split depth (from aggregated.json).

This is the core CCWM research contribution: training with nondeterminism-derived
uncertainty targets rather than point predictions, enabling calibrated uncertainty
estimation over concurrent execution.

Usage (on RunPod RTX 4000 Ada):
    TMPDIR=/workspace/tmp python /root/train_lora_kl.py
    TMPDIR=/workspace/tmp python /root/train_lora_kl.py --kl-weight 0.5 --epochs 3
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from functools import partial
from typing import Any, Optional

import torch
import torch.nn.functional as F
from torch.utils.data import Dataset
from transformers import Trainer, TrainingArguments
from unsloth import FastLanguageModel

# ── constants ────────────────────────────────────────────────────────────────

ALL_EVENT_TYPES = ["GoBlock", "GoCreate", "GoEnd", "GoSched", "GoStart", "GoUnblock"]

DEFAULTS = dict(
    model_id="unsloth/qwen2.5-coder-7b-instruct-bnb-4bit",
    train_file="/root/train_point_dups.jsonl",
    val_file="/root/val_point_dups.jsonl",
    aggregated_file="/root/aggregated.json",
    output_dir="/root/lora_adapter_kl",
    epochs=3,
    batch_size=1,
    grad_accum=8,
    lr=2e-4,
    max_seq_len=4096,
    lora_r=16,
    lora_alpha=32,
    kl_weight=1.0,
)


# ── tokenization helpers ──────────────────────────────────────────────────────

def get_event_type_token_ids(tokenizer) -> dict[str, list[int]]:
    """Return the token ID(s) for each event type word."""
    ids: dict[str, list[int]] = {}
    for et in ALL_EVENT_TYPES:
        tids = tokenizer.encode(et, add_special_tokens=False)
        ids[et] = tids
    return ids


def find_event_type_position(
    full_ids: list[int],
    response_start: int,
    event_type: str,
    et_token_ids: dict[str, list[int]],
) -> int:
    """Return the index of the FIRST token of event_type in full_ids[response_start:].

    Searches up to 80 tokens into the assistant response. Returns -1 if not found.
    """
    tids = et_token_ids[event_type]
    search_end = min(response_start + 80, len(full_ids) - len(tids) + 1)
    for i in range(response_start, search_end):
        if full_ids[i : i + len(tids)] == tids:
            return i
    return -1


# ── dataset ───────────────────────────────────────────────────────────────────

class KLDataset(Dataset):
    """Pre-tokenised dataset for KL distribution-loss training.

    Each item includes:
      input_ids, attention_mask, labels  — standard causal LM fields
      kl_position                        — token index of event_type value (-1 if unknown)
      kl_target                          — 6-element empirical distribution tensor
    """

    def __init__(
        self,
        examples: list[dict[str, Any]],
        tokenizer,
        aggregated_lookup: dict[tuple[str, int], list[float]],
        et_token_ids: dict[str, list[int]],
        max_seq_len: int = 4096,
    ) -> None:
        self.items: list[dict[str, Any]] = []
        skipped = 0

        for ex in examples:
            messages = ex["messages"]
            program_id: str = ex.get("program_id", "")
            split_pct: int = ex.get("split_percent", -1)

            # Empirical target distribution
            kl_target_list: list[float] = aggregated_lookup.get(
                (program_id, split_pct), []
            )

            # Tokenise full sequence (prompt + response)
            full_text: str = tokenizer.apply_chat_template(
                messages, tokenize=False, add_special_tokens=False
            )
            full_enc = tokenizer(
                full_text,
                truncation=True,
                max_length=max_seq_len,
                return_tensors="pt",
            )
            full_ids: list[int] = full_enc["input_ids"][0].tolist()

            # Find where the assistant response starts
            prompt_msgs = [m for m in messages if m["role"] != "assistant"]
            prompt_text: str = tokenizer.apply_chat_template(
                prompt_msgs,
                tokenize=False,
                add_generation_prompt=True,
                add_special_tokens=False,
            )
            prompt_ids: list[int] = tokenizer(
                prompt_text,
                truncation=True,
                max_length=max_seq_len,
                return_tensors="pt",
            )["input_ids"][0].tolist()
            response_start = min(len(prompt_ids), len(full_ids) - 1)

            # Find the event_type value token position in the response
            kl_position = -1
            if kl_target_list:
                # The ground-truth event type is the assistant message content
                gt_raw: str = next(
                    (m["content"] for m in messages if m["role"] == "assistant"), ""
                )
                try:
                    gt_et: Optional[str] = json.loads(gt_raw).get("event_type")
                except Exception:
                    gt_et = None
                if gt_et in et_token_ids:
                    kl_position = find_event_type_position(
                        full_ids, response_start, gt_et, et_token_ids
                    )

            # Build labels: mask prompt tokens, keep response tokens
            input_ids_t = torch.tensor(full_ids, dtype=torch.long)
            labels_t = input_ids_t.clone()
            labels_t[:response_start] = -100

            # Uniform fallback distribution if no empirical data available
            kl_target_t = torch.tensor(
                kl_target_list if kl_target_list else [1.0 / 6] * 6,
                dtype=torch.float,
            )

            self.items.append(
                {
                    "input_ids": input_ids_t,
                    "attention_mask": torch.ones_like(input_ids_t),
                    "labels": labels_t,
                    "kl_position": kl_position,
                    "kl_target": kl_target_t,
                }
            )

        print(
            f"  Dataset: {len(self.items)} examples built"
            f" ({len(self.items) - skipped} with KL targets)"
        )

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        return self.items[idx]


def kl_collate_fn(batch: list[dict], pad_token_id: int) -> dict[str, torch.Tensor]:
    """Pad a batch of KLDataset items to the same length."""
    max_len = max(b["input_ids"].shape[0] for b in batch)
    bs = len(batch)

    input_ids = torch.full((bs, max_len), pad_token_id, dtype=torch.long)
    attention_mask = torch.zeros(bs, max_len, dtype=torch.long)
    labels = torch.full((bs, max_len), -100, dtype=torch.long)
    kl_positions = torch.full((bs,), -1, dtype=torch.long)
    kl_targets = torch.full((bs, 6), 1.0 / 6, dtype=torch.float)

    for i, b in enumerate(batch):
        n = b["input_ids"].shape[0]
        input_ids[i, :n] = b["input_ids"]
        attention_mask[i, :n] = 1
        labels[i, :n] = b["labels"]
        kl_positions[i] = b["kl_position"]
        kl_targets[i] = b["kl_target"]

    return {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "labels": labels,
        "kl_position": kl_positions,
        "kl_target": kl_targets,
    }


# ── custom trainer ────────────────────────────────────────────────────────────

class KLTrainer(Trainer):
    """Trainer that adds a KL divergence term at the event_type token position.

    Loss = CE(all response tokens) + kl_weight * KL(empirical || model_at_event_type_pos)

    The KL term is computed from the model's softmax over the six event-type vocabulary
    tokens at the position immediately before the ground-truth event_type token.
    """

    def __init__(
        self,
        et_token_ids: dict[str, list[int]],
        kl_weight: float = 1.0,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        # First token ID for each event type, used to index into logits
        self.et_first_token_ids = torch.tensor(
            [et_token_ids[et][0] for et in ALL_EVENT_TYPES], dtype=torch.long
        )
        self.kl_weight = kl_weight

    def compute_loss(
        self,
        model,
        inputs: dict[str, torch.Tensor],
        return_outputs: bool = False,
        **kwargs,
    ):
        kl_positions = inputs.pop("kl_position", None)
        kl_targets = inputs.pop("kl_target", None)

        outputs = model(**inputs)
        logits: torch.Tensor = outputs.logits  # (B, T, V)

        # ── standard causal LM cross-entropy ────────────────────────────────
        labels: torch.Tensor = inputs.get("labels")
        shift_logits = logits[..., :-1, :].contiguous()
        shift_labels = labels[..., 1:].contiguous()
        ce_loss = F.cross_entropy(
            shift_logits.view(-1, shift_logits.size(-1)),
            shift_labels.view(-1),
            ignore_index=-100,
        )

        if kl_positions is None or kl_targets is None or self.kl_weight == 0.0:
            return (ce_loss, outputs) if return_outputs else ce_loss

        # ── KL divergence at event_type token position ───────────────────────
        # logits[b, pos-1, :] is the distribution over next tokens at position pos
        et_ids = self.et_first_token_ids.to(logits.device)
        kl_total = torch.tensor(0.0, device=logits.device, requires_grad=False)
        n_valid = 0

        for b in range(logits.size(0)):
            pos = kl_positions[b].item()
            if pos <= 0 or pos >= logits.size(1):
                continue
            # Slice the 6 event-type logits at the prediction position
            et_logits = logits[b, pos - 1, et_ids]  # (6,)
            log_pred = F.log_softmax(et_logits, dim=-1)
            target = kl_targets[b].to(logits.device, dtype=torch.float)
            # KL(empirical || model): penalise model for disagreeing with empirical dist
            kl = F.kl_div(log_pred, target, reduction="sum")
            kl_total = kl_total + kl
            n_valid += 1

        if n_valid > 0:
            kl_loss = kl_total / n_valid
            total_loss = ce_loss + self.kl_weight * kl_loss
        else:
            total_loss = ce_loss

        return (total_loss, outputs) if return_outputs else total_loss


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 14 — KL distribution-loss training")
    parser.add_argument("--model-id",        default=DEFAULTS["model_id"])
    parser.add_argument("--train-file",      default=DEFAULTS["train_file"])
    parser.add_argument("--val-file",        default=DEFAULTS["val_file"])
    parser.add_argument("--aggregated-file", default=DEFAULTS["aggregated_file"])
    parser.add_argument("--output-dir",      default=DEFAULTS["output_dir"])
    parser.add_argument("--epochs",          type=int,   default=DEFAULTS["epochs"])
    parser.add_argument("--batch-size",      type=int,   default=DEFAULTS["batch_size"])
    parser.add_argument("--grad-accum",      type=int,   default=DEFAULTS["grad_accum"])
    parser.add_argument("--lr",              type=float, default=DEFAULTS["lr"])
    parser.add_argument("--max-seq-len",     type=int,   default=DEFAULTS["max_seq_len"])
    parser.add_argument("--lora-r",          type=int,   default=DEFAULTS["lora_r"])
    parser.add_argument("--lora-alpha",      type=int,   default=DEFAULTS["lora_alpha"])
    parser.add_argument("--kl-weight",       type=float, default=DEFAULTS["kl_weight"],
                        help="Weight for KL loss term. 0 = pure CE (ablation), 1 = equal weight.")
    args = parser.parse_args()

    print("=" * 65)
    print("Phase 14 — KL Distribution-Loss Training")
    print(f"  model       : {args.model_id}")
    print(f"  kl_weight   : {args.kl_weight}")
    print(f"  epochs      : {args.epochs}")
    print(f"  batch×accum : {args.batch_size}×{args.grad_accum} = {args.batch_size*args.grad_accum}")
    print("=" * 65)

    # ── load model ────────────────────────────────────────────────────────────
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model_id,
        max_seq_length=args.max_seq_len,
        load_in_4bit=True,
        dtype=None,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    # ── event type token IDs ─────────────────────────────────────────────────
    et_token_ids = get_event_type_token_ids(tokenizer)
    print(f"\nEvent type token IDs:")
    for et, tids in et_token_ids.items():
        print(f"  {et}: {tids}")

    # ── load aggregated distributions ────────────────────────────────────────
    with open(args.aggregated_file) as f:
        aggregated = json.load(f)

    # Build lookup: (program_id, split_percent) → [p_GoBlock, p_GoCreate, ...]
    aggregated_lookup: dict[tuple[str, int], list[float]] = {}
    for g in aggregated:
        dist = g["next_event_distribution"]
        dist_vec = [dist.get(et, 0.0) for et in ALL_EVENT_TYPES]
        aggregated_lookup[(g["program_id"], g["split_percent"])] = dist_vec

    print(f"\nLoaded {len(aggregated_lookup)} empirical distributions from {args.aggregated_file}")

    # ── load training examples ────────────────────────────────────────────────
    def load_jsonl(path: str) -> list[dict]:
        with open(path) as f:
            return [json.loads(line) for line in f]

    print(f"\nLoading training data from {args.train_file}...")
    train_examples = load_jsonl(args.train_file)
    print(f"Loading validation data from {args.val_file}...")
    val_examples = load_jsonl(args.val_file)

    # ── build datasets ────────────────────────────────────────────────────────
    print("\nBuilding training dataset...")
    train_dataset = KLDataset(
        train_examples, tokenizer, aggregated_lookup, et_token_ids, args.max_seq_len
    )
    print("Building validation dataset...")
    val_dataset = KLDataset(
        val_examples, tokenizer, aggregated_lookup, et_token_ids, args.max_seq_len
    )

    # ── training arguments ────────────────────────────────────────────────────
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        bf16=True,
        optim="adamw_8bit",
        gradient_checkpointing=True,
        eval_strategy="steps",
        eval_steps=100,
        save_strategy="steps",
        save_steps=100,
        save_total_limit=3,
        logging_steps=10,
        report_to="none",
        dataloader_num_workers=0,
        remove_unused_columns=False,  # critical: keep kl_position and kl_target
    )

    collate = partial(
        kl_collate_fn, pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id
    )

    trainer = KLTrainer(
        et_token_ids=et_token_ids,
        kl_weight=args.kl_weight,
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        data_collator=collate,
    )

    print("\nStarting KL distribution-loss training...")
    trainer.train()

    print(f"\nSaving adapter to {args.output_dir}...")
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print("Done.")


if __name__ == "__main__":
    main()
