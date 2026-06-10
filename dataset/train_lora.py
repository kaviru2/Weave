#!/usr/bin/env python3
"""
dataset/train_lora.py

LoRA Fine-Tuning Setup for training a Stochastic Code World Model.
Fine-tunes an 8B instruction/coder model (Llama-3-8B or DeepSeek-Coder)
on the empirical frequency-duplicated datasets using 4-bit QLoRA.

Optimized to run on free-tier GPU services like Kaggle (T4 or 2x T4) or Google Colab.
Supports:
  1. Local sanity checks via --dry-run (no GPU or full package installation required).
  2. Training with gradient checkpointing, bitsandbytes 4-bit quantization, and paged optimizers.
  3. Post-training adapter merging via --merge.
"""

import os
import sys
import json
import argparse
import logging
from typing import Dict, Any, List, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Check imports and handle missing libraries gracefully
MISSING_DEPS = []
for dep in ["torch", "transformers", "datasets", "peft", "trl", "bitsandbytes", "accelerate"]:
    try:
        __import__(dep)
    except ImportError:
        MISSING_DEPS.append(dep)


def print_kaggle_instructions():
    """Prints useful instructions for setting up the environment on Kaggle."""
    print("""
================================================================================
KAGGLE SET UP & EXECUTION INSTRUCTIONS:
================================================================================
1. Create a new Kaggle Notebook.
2. Set the Accelerator to 'GPU T4 x2' (or 'GPU T4 x1') in the notebook settings.
3. Upload your dataset files:
   - dataset/output/train_point_dups.jsonl
   - dataset/output/val_point_dups.jsonl
4. Install required libraries inside your Kaggle Notebook cell:
   !pip install -q -U transformers peft trl bitsandbytes accelerate datasets
5. If using Llama-3-8B (gated), retrieve your HuggingFace Token:
   - Go to your Kaggle 'Add-ons' -> 'Secrets' menu.
   - Add a secret named 'HF_TOKEN' containing your HuggingFace Read token.
   - In your code, authenticate via:
     from kaggle_secrets import UserSecretsClient
     import os
     os.environ["HF_TOKEN"] = UserSecretsClient().get_secret("HF_TOKEN")
6. Run the training command:
   !python train_lora.py --model_id deepseek-ai/deepseek-coder-6.7b-instruct \\
                         --train_file /path/to/train_point_dups.jsonl \\
                         --val_file /path/to/val_point_dups.jsonl \\
                         --output_dir ./lora_adapter \\
                         --epochs 3 \\
                         --batch_size 4
================================================================================
""")


def run_dry_run(args: argparse.Namespace):
    """Runs a local dry run to verify datasets, formats, and training parameters."""
    logging.info("=== STARTING DRY-RUN VERIFICATION ===")
    
    if MISSING_DEPS:
        logging.warning(f"Optional deep learning dependencies are missing: {', '.join(MISSING_DEPS)}")
        logging.warning("Continuing dry-run to verify local dataset formatting and file structure...")

    # 1. Verify files exist
    if not os.path.exists(args.train_file):
        logging.error(f"Training dataset not found: {args.train_file}")
        sys.exit(1)
    if not os.path.exists(args.val_file):
        logging.error(f"Validation dataset not found: {args.val_file}")
        sys.exit(1)

    logging.info("Training and validation data files located successfully.")

    # 2. Inspect datasets
    try:
        with open(args.train_file, "r") as f:
            train_examples = [json.loads(line) for line in f.readlines()]
        with open(args.val_file, "r") as f:
            val_examples = [json.loads(line) for line in f.readlines()]
    except Exception as e:
        logging.error(f"Failed to read/parse JSONL datasets: {e}")
        sys.exit(1)

    logging.info(f"Loaded {len(train_examples)} training examples from {args.train_file}")
    logging.info(f"Loaded {len(val_examples)} validation examples from {args.val_file}")

    # Inspect a sample
    if train_examples:
        sample = train_examples[0]
        logging.info("Inspecting sample SFT message structure:")
        messages = sample.get("messages", [])
        for m in messages:
            role = m.get("role", "unknown")
            content = m.get("content", "")
            logging.info(f"  Role [{role}]: {content[:200]}...")

    # 3. Test Tokenizer Fallbacks
    if "transformers" not in MISSING_DEPS:
        from transformers import AutoTokenizer
        try:
            logging.info(f"Attempting to load tokenizer for model: {args.model_id} ...")
            tokenizer = AutoTokenizer.from_pretrained(args.model_id, trust_remote_code=True)
            logging.info("Tokenizer loaded successfully.")
        except Exception as e:
            logging.warning(f"Could not load tokenizer for '{args.model_id}' (auth gated or no network): {e}")
            logging.info("Falling back to public 'gpt2' tokenizer for dry-run format checking.")
            tokenizer = AutoTokenizer.from_pretrained("gpt2")
        
        # Test applying a chat template
        if train_examples and hasattr(tokenizer, "apply_chat_template"):
            try:
                # Add default template if missing
                if tokenizer.chat_template is None:
                    tokenizer.chat_template = (
                        "{% for message in messages %}"
                        "{{ '<|im_start|>' + message['role'] + '\\n' + message['content'] + '<|im_end|>\\n' }}"
                        "{% endfor %}"
                        "{% if add_generation_prompt %}"
                        "{{ '<|im_start|>assistant\\n' }}"
                        "{% endif %}"
                    )
                sample_msgs = train_examples[0]["messages"]
                formatted_prompt = tokenizer.apply_chat_template(sample_msgs, tokenize=False)
                logging.info("Successfully formatted chat sample using tokenizer template:")
                print("\n" + "-"*50)
                print(formatted_prompt[:600] + "\n... [TRUNCATED] ...")
                print("-"*50 + "\n")
            except Exception as cte:
                logging.error(f"Chat template application failed: {cte}")

    print_kaggle_instructions()
    logging.info("Dry run complete! Dataset and pipeline formats are valid.")


def run_merge(args: argparse.Namespace):
    """Merges a trained LoRA adapter back into the base model weights."""
    logging.info("=== RUNNING WEIGHT MERGE ===")
    if MISSING_DEPS:
        logging.error(f"Missing libraries needed for merging: {', '.join(MISSING_DEPS)}")
        sys.exit(1)

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    if not args.merge_dir:
        logging.error("Please specify --merge_dir to output the final full merged model weights.")
        sys.exit(1)

    logging.info(f"Loading base model: {args.model_id}")
    device_map = "auto" if torch.cuda.is_available() else None
    
    # Load base model in half precision for merging
    base_model = AutoModelForCausalLM.from_pretrained(
        args.model_id,
        torch_dtype=torch.float16,
        device_map=device_map,
        trust_remote_code=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(args.model_id, trust_remote_code=True)

    logging.info(f"Loading PEFT/LoRA adapter from: {args.output_dir}")
    model = PeftModel.from_pretrained(base_model, args.output_dir)

    logging.info("Merging adapter weights with base model...")
    merged_model = model.merge_and_unload()

    logging.info(f"Saving fully merged model to: {args.merge_dir}")
    os.makedirs(args.merge_dir, exist_ok=True)
    merged_model.save_pretrained(args.merge_dir)
    tokenizer.save_pretrained(args.merge_dir)

    logging.info(f"Merge successfully completed! Model saved at {args.merge_dir}")


def train(args: argparse.Namespace):
    """Executes the standard PyTorch training loop on GPU."""
    logging.info("=== STARTING LORA FINE-TUNING ===")
    if MISSING_DEPS:
        logging.error(f"Missing libraries for training: {', '.join(MISSING_DEPS)}")
        sys.exit(1)

    import torch
    from datasets import load_dataset
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        TrainingArguments,
    )
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    try:
        from trl import SFTTrainer, SFTConfig
        HAS_SFT_CONFIG = True
    except ImportError:
        from trl import SFTTrainer
        HAS_SFT_CONFIG = False

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logging.info(f"Training device detected: {device.upper()}")

    # 1. Quantization Configuration
    logging.info("Configuring 4-bit double quantization parameters...")
    compute_dtype = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float16
    
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
    )

    # 2. Model Loading
    logging.info(f"Loading quantized model: {args.model_id}")
    if torch.cuda.is_available():
        model = AutoModelForCausalLM.from_pretrained(
            args.model_id,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
        )
        model = prepare_model_for_kbit_training(model)
    else:
        logging.warning("CUDA not available. Loading base model in 32-bit float on CPU.")
        model = AutoModelForCausalLM.from_pretrained(
            args.model_id,
            torch_dtype=torch.float32,
            device_map=None,
            trust_remote_code=True,
        )

    # 3. Tokenizer Loading
    tokenizer = AutoTokenizer.from_pretrained(args.model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Default fallback chat template
    if tokenizer.chat_template is None:
        tokenizer.chat_template = (
            "{% for message in messages %}"
            "{{ '<|im_start|>' + message['role'] + '\\n' + message['content'] + '<|im_end|>\\n' }}"
            "{% endfor %}"
            "{% if add_generation_prompt %}"
            "{{ '<|im_start|>assistant\\n' }}"
            "{% endif %}"
        )

    # 4. LoRA Target Adaption Setup
    logging.info("Initializing LoRA adapters configuration...")
    peft_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
    )

    # 5. Load SFT datasets
    logging.info("Loading train/val JSONL datasets...")
    dataset = load_dataset(
        "json",
        data_files={"train": args.train_file, "validation": args.val_file}
    )

    # Prompt formatting helper — new TRL calls this per-example (batched=False), expects a single string
    def formatting_prompts_func(example):
        return tokenizer.apply_chat_template(example['messages'], tokenize=False)

    # 6. Training Arguments Configuration
    logging.info("Configuring PyTorch Training Arguments...")
    
    # Handle evaluation_strategy vs eval_strategy deprecation dynamically
    import inspect
    import dataclasses
    eval_strategy_kwargs = {}
    
    if HAS_SFT_CONFIG:
        config_class = SFTConfig
    else:
        config_class = TrainingArguments

    sig = inspect.signature(config_class.__init__)
    if "eval_strategy" in sig.parameters:
        eval_strategy_kwargs["eval_strategy"] = "epoch"
    else:
        eval_strategy_kwargs["evaluation_strategy"] = "epoch"

    extra_kwargs = {}
    sft_config_has_max_seq = False
    sft_config_has_tok = False
    
    if HAS_SFT_CONFIG:
        sft_fields = {f.name for f in dataclasses.fields(SFTConfig)}
        if "max_seq_length" in sft_fields:
            extra_kwargs["max_seq_length"] = args.max_seq_length
            sft_config_has_max_seq = True
        elif "max_length" in sft_fields:
            extra_kwargs["max_length"] = args.max_seq_length
            sft_config_has_max_seq = True
        
        if "processing_class" in sft_fields:
            extra_kwargs["processing_class"] = tokenizer
            sft_config_has_tok = True
        elif "tokenizer" in sft_fields:
            extra_kwargs["tokenizer"] = tokenizer
            sft_config_has_tok = True

        # Fix TRL #3318: Qwen2.5 chat template ends with \n not eos_token, causing
        # TRL to double-append eos. Setting eos_token explicitly prevents this.
        if "eos_token" in sft_fields and tokenizer.eos_token is not None:
            extra_kwargs["eos_token"] = tokenizer.eos_token

    training_args = config_class(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        save_strategy="epoch",
        learning_rate=args.lr,
        weight_decay=0.01,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        logging_steps=10,
        fp16=not torch.cuda.is_bf16_supported() if torch.cuda.is_available() else False,
        bf16=torch.cuda.is_bf16_supported() if torch.cuda.is_available() else False,
        gradient_checkpointing=True,
        optim="paged_adamw_8bit" if torch.cuda.is_available() else "adamw_torch",
        report_to="none",
        load_best_model_at_end=False,
        **eval_strategy_kwargs,
        **extra_kwargs
    )

    # 7. Initialize Trainer
    logging.info("Initializing HuggingFace SFTTrainer...")
    
    trainer_kwargs = {}
    if not HAS_SFT_CONFIG or not sft_config_has_max_seq:
        trainer_kwargs["max_seq_length"] = args.max_seq_length

    if not sft_config_has_tok:
        trainer_sig = inspect.signature(SFTTrainer.__init__)
        if "tokenizer" in trainer_sig.parameters:
            trainer_kwargs["tokenizer"] = tokenizer
        elif "processing_class" in trainer_sig.parameters:
            trainer_kwargs["processing_class"] = tokenizer

    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        peft_config=peft_config,
        formatting_func=formatting_prompts_func,
        args=training_args,
        **trainer_kwargs
    )

    # 8. Start Fine-Tuning
    logging.info("Launching training process...")
    trainer.train()

    # 9. Save Fine-Tuned Adapter
    logging.info(f"Saving trained LoRA adapter weights to: {args.output_dir}")
    trainer.model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    logging.info("Training complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Weave LoRA Fine-Tuning Setup for Kaggle/Colab")
    parser.add_argument("--model_id", type=str, default="meta-llama/Meta-Llama-3-8B-Instruct",
                        help="Base model ID (e.g. meta-llama/Meta-Llama-3-8B-Instruct or deepseek-ai/deepseek-coder-6.7b-instruct)")
    parser.add_argument("--train_file", type=str, default="dataset/output/train_point_dups.jsonl",
                        help="Path to training jsonl dataset")
    parser.add_argument("--val_file", type=str, default="dataset/output/val_point_dups.jsonl",
                        help="Path to validation jsonl dataset")
    parser.add_argument("--output_dir", type=str, default="dataset/output/lora_adapter",
                        help="Path to save trained LoRA adapter weights")
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs")
    parser.add_argument("--batch_size", type=int, default=4, help="Batch size per device")
    parser.add_argument("--grad_accum", type=int, default=2, help="Gradient accumulation steps")
    parser.add_argument("--lr", type=float, default=2e-4, help="Learning rate")
    parser.add_argument("--max_seq_length", type=int, default=4096, help="Maximum sequence length")
    parser.add_argument("--lora_r", type=int, default=8, help="LoRA rank dimension")
    parser.add_argument("--lora_alpha", type=int, default=16, help="LoRA alpha scaling parameter")
    parser.add_argument("--lora_dropout", type=float, default=0.05, help="LoRA dropout rate")
    
    # Mode flags
    parser.add_argument("--dry-run", action="store_true", help="Perform local sanity validation without training")
    parser.add_argument("--merge", action="store_true", help="Merge LoRA adapter weights into base model weights")
    parser.add_argument("--merge_dir", type=str, default="dataset/output/merged_model",
                        help="Target path to write fully merged base+adapter weights")

    args_parsed = parser.parse_args()

    if args_parsed.dry_run:
        run_dry_run(args_parsed)
    elif args_parsed.merge:
        run_merge(args_parsed)
    else:
        train(args_parsed)
