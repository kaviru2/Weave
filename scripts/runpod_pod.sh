#!/bin/bash
# runpod_pod.sh — runs INSIDE the RunPod pod
# Installs Unsloth + deps, trains 7B QLoRA, evals, prints results.
# Usage: bash /root/runpod_pod.sh
set -e

MODEL_ID="${MODEL_ID:-Qwen/Qwen2.5-Coder-7B-Instruct}"
TRAIN_FILE="${TRAIN_FILE:-/root/train_point_dups.jsonl}"
VAL_FILE="${VAL_FILE:-/root/val_point_dups.jsonl}"
OUTPUT_DIR="${OUTPUT_DIR:-/root/lora_adapter}"
EPOCHS="${EPOCHS:-3}"
BATCH_SIZE="${BATCH_SIZE:-1}"
GRAD_ACCUM="${GRAD_ACCUM:-8}"
MAX_SEQ_LEN="${MAX_SEQ_LEN:-4096}"

echo "========================================"
echo " Weave RunPod Training Script (Unsloth)"
echo " Model:      $MODEL_ID"
echo " Epochs:     $EPOCHS | Batch: $BATCH_SIZE | GradAccum: $GRAD_ACCUM | Seq: $MAX_SEQ_LEN"
echo " GPU:        $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo unknown)"
echo "========================================"

# ── Install Unsloth and compatible deps ───────────────────────────────────────
echo ""
echo "Installing Unsloth + deps..."
# Let pip resolve all versions — unsloth manages its own transformers/tokenizers constraints
pip install -q unsloth trl peft accelerate bitsandbytes datasets
echo "Deps installed."

# ── Train ─────────────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo " PHASE 1: TRAINING"
echo "========================================"

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

python /root/train_lora_unsloth.py \
    --model_id        "$MODEL_ID" \
    --train_file      "$TRAIN_FILE" \
    --val_file        "$VAL_FILE" \
    --output_dir      "$OUTPUT_DIR" \
    --epochs          "$EPOCHS" \
    --batch_size      "$BATCH_SIZE" \
    --grad_accum      "$GRAD_ACCUM" \
    --max_seq_length  "$MAX_SEQ_LEN"

echo ""
echo "Training complete. Adapter at: $OUTPUT_DIR"

# ── Eval ──────────────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo " PHASE 2: EVALUATION"
echo "========================================"

python /root/run_eval.py \
    --adapter  "$OUTPUT_DIR" \
    --val_file "$VAL_FILE" \
    --model_id "$MODEL_ID" \
    --out_file /root/eval_results.json

echo ""
echo "========================================"
echo " DONE. Results at /root/eval_results.json"
echo " Download with:"
echo "   scp -P <PORT> -i <KEY> root@<IP>:/root/eval_results.json ."
echo "   scp -P <PORT> -i <KEY> -r root@<IP>:/root/lora_adapter ."
echo "========================================"
