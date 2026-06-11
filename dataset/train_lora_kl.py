#!/usr/bin/env python3
"""
Phase 14 — Distribution-loss training (KL divergence against empirical distributions).

Trains Qwen2.5-Coder-7B-Instruct with a mixed loss:
  total_loss = CE_loss (all output tokens) + kl_weight * KL_loss (event_type position)

The KL loss compares the model's softmax distribution over the six event-type
vocabulary tokens at the discriminating token position against the empirical
distribution derived from multiple runs (aggregated.json).

Handles both single-token event types (e.g. "GoBlock" → [12345]) and multi-token
event types (e.g. "GoBlock" → ["Go", "Block"]) automatically. If all event types
share a common first token (e.g. "Go"), the KL is computed at the second token
position, where the model actually discriminates between event types.

Usage (on RunPod RTX 4000 Ada):
    TMPDIR=/workspace/tmp python /root/train_lora_kl.py
    TMPDIR=/workspace/tmp python /root/train_lora_kl.py --kl-weight 0.5
    TMPDIR=/workspace/tmp python /root/train_lora_kl.py --kl-weight 0.0  # CE ablation
"""

from __future__ import annotations

import argparse
import json
import os
from functools import partial
from typing import Any, Optional

import torch
import torch.nn.functional as F
from torch.utils.data import Dataset
from transformers import Trainer, TrainingArguments
from unsloth import FastLanguageModel

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


# ── tokenisation helpers ──────────────────────────────────────────────────────

def analyse_event_type_tokens(tokenizer) -> dict[str, Any]:
    """Work out which token position is the discriminating one for KL.

    If all six event types share the same first token (e.g. they all tokenise
    as ["Go", "X"]), the model cannot discriminate between them at the first
    position — the discrimination happens at the second token. We detect this
    and set kl_offset=1 so compute_loss looks at the right logit position.

    Returns a dict with:
      full_ids   — {et: [tok_id, ...]}  complete token sequences
      kl_ids     — [tok_id, ...]        one per event type, the discriminating token
      kl_offset  — 0 or 1              logit_pos = event_type_first_pos + kl_offset - 1
    """
    full_ids: dict[str, list[int]] = {}
    for et in ALL_EVENT_TYPES:
        full_ids[et] = tokenizer.encode(et, add_special_tokens=False)

    first_tokens = [full_ids[et][0] for et in ALL_EVENT_TYPES]
    all_same_first = len(set(first_tokens)) == 1
    min_len = min(len(full_ids[et]) for et in ALL_EVENT_TYPES)

    if all_same_first and min_len >= 2:
        # All start with the same token (e.g. "Go") — discriminate at second token
        kl_ids = [full_ids[et][1] for et in ALL_EVENT_TYPES]
        kl_offset = 1
    else:
        # Each event type has a unique first token (or mixed) — discriminate at first
        kl_ids = [full_ids[et][0] for et in ALL_EVENT_TYPES]
        kl_offset = 0

    print("\nEvent-type tokenisation:")
    for et in ALL_EVENT_TYPES:
        toks = [tokenizer.decode([t]) for t in full_ids[et]]
        print(f"  {et:<12}: {full_ids[et]}  ({toks})")
    print(f"\nKL discriminating tokens (offset={kl_offset}):")
    for et, kid in zip(ALL_EVENT_TYPES, kl_ids):
        print(f"  {et:<12}: token {kid}  ({repr(tokenizer.decode([kid]))})")

    return {"full_ids": full_ids, "kl_ids": kl_ids, "kl_offset": kl_offset}


def find_et_position(
    full_ids: list[int],
    response_start: int,
    event_type: str,
    et_full_ids: dict[str, list[int]],
) -> int:
    """Return index of the FIRST token of event_type in full_ids[response_start:].

    Searches up to 80 tokens into the assistant response. Returns -1 if not found.
    """
    tids = et_full_ids[event_type]
    end = min(response_start + 80, len(full_ids) - len(tids) + 1)
    for i in range(response_start, end):
        if full_ids[i : i + len(tids)] == tids:
            return i
    return -1


# ── dataset ───────────────────────────────────────────────────────────────────

class KLDataset(Dataset):
    def __init__(
        self,
        examples: list[dict[str, Any]],
        tokenizer,
        aggregated_lookup: dict[tuple[str, int], list[float]],
        et_info: dict[str, Any],
        max_seq_len: int = 4096,
    ) -> None:
        self.items: list[dict[str, Any]] = []
        n_with_kl = 0

        for ex in examples:
            messages: list[dict] = ex["messages"]
            program_id: str = ex.get("program_id", "")
            split_pct: int = ex.get("split_percent", -1)

            kl_target_list: list[float] = aggregated_lookup.get(
                (program_id, split_pct), []
            )

            # Tokenise full sequence
            full_text: str = tokenizer.apply_chat_template(
                messages, tokenize=False, add_special_tokens=False
            )
            full_enc = tokenizer(
                full_text, truncation=True, max_length=max_seq_len, return_tensors="pt"
            )
            full_ids: list[int] = full_enc["input_ids"][0].tolist()

            # Find response start (prompt-only tokenisation)
            prompt_msgs = [m for m in messages if m["role"] != "assistant"]
            prompt_text: str = tokenizer.apply_chat_template(
                prompt_msgs, tokenize=False,
                add_generation_prompt=True, add_special_tokens=False,
            )
            prompt_ids: list[int] = tokenizer(
                prompt_text, truncation=True, max_length=max_seq_len, return_tensors="pt"
            )["input_ids"][0].tolist()
            response_start = min(len(prompt_ids), len(full_ids) - 1)

            # Find event_type token position in response
            kl_position = -1
            if kl_target_list:
                gt_raw: str = next(
                    (m["content"] for m in messages if m["role"] == "assistant"), ""
                )
                gt_et: Optional[str] = None
                try:
                    gt_et = json.loads(gt_raw).get("event_type")
                except Exception:
                    pass
                if gt_et in et_info["full_ids"]:
                    kl_position = find_et_position(
                        full_ids, response_start, gt_et, et_info["full_ids"]
                    )
                    if kl_position >= 0:
                        n_with_kl += 1

            # Labels: mask prompt, keep response
            input_ids_t = torch.tensor(full_ids, dtype=torch.long)
            labels_t = input_ids_t.clone()
            labels_t[:response_start] = -100

            kl_target_t = torch.tensor(
                kl_target_list if kl_target_list else [1.0 / 6] * 6, dtype=torch.float
            )

            self.items.append({
                "input_ids": input_ids_t,
                "attention_mask": torch.ones_like(input_ids_t),
                "labels": labels_t,
                "kl_position": kl_position,
                "kl_target": kl_target_t,
            })

        print(f"  {len(self.items)} examples, {n_with_kl} with KL targets")

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, idx: int) -> dict:
        return self.items[idx]


def kl_collate(batch: list[dict], pad_id: int) -> dict[str, torch.Tensor]:
    max_len = max(b["input_ids"].shape[0] for b in batch)
    bs = len(batch)
    input_ids     = torch.full((bs, max_len), pad_id, dtype=torch.long)
    attention_mask = torch.zeros(bs, max_len, dtype=torch.long)
    labels        = torch.full((bs, max_len), -100, dtype=torch.long)
    kl_positions  = torch.full((bs,), -1, dtype=torch.long)
    kl_targets    = torch.full((bs, 6), 1.0 / 6, dtype=torch.float)

    for i, b in enumerate(batch):
        n = b["input_ids"].shape[0]
        input_ids[i, :n]      = b["input_ids"]
        attention_mask[i, :n] = 1
        labels[i, :n]         = b["labels"]
        kl_positions[i]       = b["kl_position"]
        kl_targets[i]         = b["kl_target"]

    return {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "labels": labels,
        "kl_position": kl_positions,
        "kl_target": kl_targets,
    }


# ── custom trainer ────────────────────────────────────────────────────────────

class KLTrainer(Trainer):
    """Trainer that adds KL divergence at the discriminating event-type token.

    Loss = CE(all response tokens) + kl_weight * KL(empirical || model)

    kl_offset=0: model discriminates at the first token of the event type.
    kl_offset=1: all event types share a common first token (e.g. "Go"),
                 discrimination happens at the second token.
    """

    def __init__(
        self,
        kl_ids: list[int],
        kl_offset: int,
        kl_weight: float = 1.0,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.kl_ids_cpu = torch.tensor(kl_ids, dtype=torch.long)
        self.kl_offset = kl_offset
        self.kl_weight = kl_weight

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        kl_positions = inputs.pop("kl_position", None)
        kl_targets   = inputs.pop("kl_target", None)

        outputs = model(**inputs)
        logits: torch.Tensor = outputs.logits  # (B, T, V)
        labels: torch.Tensor = inputs["labels"]

        # Standard causal-LM cross-entropy on all response tokens
        shift_logits = logits[..., :-1, :].contiguous()
        shift_labels = labels[..., 1:].contiguous()
        ce_loss = F.cross_entropy(
            shift_logits.view(-1, shift_logits.size(-1)),
            shift_labels.view(-1),
            ignore_index=-100,
        )

        if kl_positions is None or kl_targets is None or self.kl_weight == 0.0:
            return (ce_loss, outputs) if return_outputs else ce_loss

        # KL divergence at the discriminating event-type token position
        #
        # kl_position stores the index of the FIRST token of the event type.
        # logit_pos = kl_position + kl_offset - 1 gives the logit position
        # that predicts the discriminating token:
        #   offset=0 → logit_pos = pos - 1   (predicts first token, single-token case)
        #   offset=1 → logit_pos = pos        (predicts second token, multi-token case)
        kl_ids = self.kl_ids_cpu.to(logits.device)
        kl_accum = torch.zeros((), device=logits.device)  # scalar shape [], not [1]
        n_valid = 0

        for b in range(logits.size(0)):
            pos = int(kl_positions[b].item())
            if pos < 0:
                continue
            logit_pos = pos + self.kl_offset - 1
            if logit_pos < 0 or logit_pos >= logits.size(1):
                continue

            et_logits   = logits[b, logit_pos, kl_ids]        # (6,)
            log_pred    = F.log_softmax(et_logits, dim=-1)
            target      = kl_targets[b].to(logits.device, dtype=torch.float)
            kl_accum    = kl_accum + F.kl_div(log_pred, target, reduction="sum")
            n_valid    += 1

        if n_valid > 0:
            kl_loss   = kl_accum / n_valid
            total_loss = ce_loss + self.kl_weight * kl_loss
        else:
            total_loss = ce_loss

        return (total_loss.squeeze(), outputs) if return_outputs else total_loss.squeeze()


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
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
                        help="KL loss weight. 0.0 = pure CE ablation.")
    args = parser.parse_args()

    print("=" * 65)
    print("Phase 14 — KL Distribution-Loss Training")
    print(f"  model      : {args.model_id}")
    print(f"  kl_weight  : {args.kl_weight}")
    print(f"  batch×accum: {args.batch_size}×{args.grad_accum}")
    print(f"  epochs     : {args.epochs}")
    print("=" * 65)

    # Load model
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

    # Analyse event-type tokenisation
    et_info = analyse_event_type_tokens(tokenizer)

    # Load aggregated distributions
    with open(args.aggregated_file) as f:
        aggregated = json.load(f)
    agg_lookup: dict[tuple[str, int], list[float]] = {
        (g["program_id"], g["split_percent"]): [
            g["next_event_distribution"].get(et, 0.0) for et in ALL_EVENT_TYPES
        ]
        for g in aggregated
    }
    print(f"\nLoaded {len(agg_lookup)} empirical distributions")

    # Load examples
    def load_jsonl(path: str) -> list[dict]:
        with open(path) as f:
            return [json.loads(l) for l in f]

    print("\nBuilding training dataset...")
    train_ds = KLDataset(load_jsonl(args.train_file), tokenizer, agg_lookup, et_info, args.max_seq_len)
    print("Building validation dataset...")
    val_ds   = KLDataset(load_jsonl(args.val_file),   tokenizer, agg_lookup, et_info, args.max_seq_len)

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
        remove_unused_columns=False,   # must keep kl_position and kl_target
    )

    trainer = KLTrainer(
        kl_ids=et_info["kl_ids"],
        kl_offset=et_info["kl_offset"],
        kl_weight=args.kl_weight,
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=partial(kl_collate, pad_id=tokenizer.pad_token_id or tokenizer.eos_token_id),
    )

    print("\nStarting training...")
    os.environ["UNSLOTH_RETURN_LOGITS"] = "1"
    trainer.train()

    print(f"\nSaving adapter to {args.output_dir}...")
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print("Done.")


if __name__ == "__main__":
    main()
