#!/bin/bash
# runpod_pod.sh — runs INSIDE the RunPod pod
# Installs Unsloth + deps, trains 7B QLoRA, evals, prints results.
# Usage: bash /root/runpod_pod.sh
set -e

MODEL_ID="${MODEL_ID:-Qwen/Qwen2.5-Coder-7B-Instruct}"
TRAIN_FILE="${TRAIN_FILE:-/root/train_point_dups.jsonl}"
VAL_FILE="${VAL_FILE:-/root/val_point_dups.jsonl}"
AGGREGATED_FILE="${AGGREGATED_FILE:-/root/aggregated.json}"
EPOCHS="${EPOCHS:-3}"
BATCH_SIZE="${BATCH_SIZE:-1}"
GRAD_ACCUM="${GRAD_ACCUM:-8}"
MAX_SEQ_LEN="${MAX_SEQ_LEN:-4096}"
KL_WEIGHT="${KL_WEIGHT:-1.0}"
USE_KL="${USE_KL:-0}"     # set to "1" to run Phase 14 KL training
USE_TRAJ="${USE_TRAJ:-0}" # set to "1" to run Phase 16 trajectory training

# Output dir — each phase writes to its own dir to avoid clobbering
if [ "$USE_TRAJ" = "1" ]; then
    OUTPUT_DIR="${OUTPUT_DIR:-/root/lora_adapter_traj}"
    TRAIN_FILE="/root/train_trajectory.jsonl"
    VAL_FILE="/root/val_trajectory.jsonl"
    MAX_SEQ_LEN="${MAX_SEQ_LEN:-6144}"
elif [ "$USE_KL" = "1" ]; then
    OUTPUT_DIR="${OUTPUT_DIR:-/root/lora_adapter_kl}"
else
    OUTPUT_DIR="${OUTPUT_DIR:-/root/lora_adapter}"
fi

echo "========================================"
echo " Weave RunPod Training Script (Unsloth)"
echo " Model:      $MODEL_ID"
echo " Mode:       $([ "$USE_TRAJ" = "1" ] && echo "Phase 16 trajectory" || ([ "$USE_KL" = "1" ] && echo "Phase 14 KL loss (kl_weight=$KL_WEIGHT)" || echo "Phase 13 CE loss"))"
echo " Epochs:     $EPOCHS | Batch: $BATCH_SIZE | GradAccum: $GRAD_ACCUM | Seq: $MAX_SEQ_LEN"
echo " GPU:        $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo unknown)"
echo "========================================"

# ── Install Unsloth and compatible deps ───────────────────────────────────────
echo ""
# Redirect HF cache to volume so model weights don't fill the 20GB root disk
export HF_HOME=/workspace/hf_cache
mkdir -p /workspace/hf_cache
echo "HF_HOME set to /workspace/hf_cache"

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

if [ "$USE_TRAJ" = "1" ]; then
    echo "Running Phase 16 trajectory training..."
    python /root/train_lora_trajectory.py \
        --model_id        "$MODEL_ID" \
        --train_file      "$TRAIN_FILE" \
        --val_file        "$VAL_FILE" \
        --output_dir      "$OUTPUT_DIR" \
        --epochs          "$EPOCHS" \
        --batch_size      "$BATCH_SIZE" \
        --grad_accum      "$GRAD_ACCUM" \
        --max_seq_length  "$MAX_SEQ_LEN"
elif [ "$USE_KL" = "1" ]; then
    echo "Running Phase 14 KL distribution-loss training..."
    python /root/train_lora_kl.py \
        --model-id        "$MODEL_ID" \
        --train-file      "$TRAIN_FILE" \
        --val-file        "$VAL_FILE" \
        --aggregated-file "$AGGREGATED_FILE" \
        --output-dir      "$OUTPUT_DIR" \
        --epochs          "$EPOCHS" \
        --batch-size      "$BATCH_SIZE" \
        --grad-accum      "$GRAD_ACCUM" \
        --max-seq-len     "$MAX_SEQ_LEN" \
        --kl-weight       "$KL_WEIGHT"
else
    echo "Running Phase 13 CE training (Unsloth)..."
    python /root/train_lora_unsloth.py \
        --model_id        "$MODEL_ID" \
        --train_file      "$TRAIN_FILE" \
        --val_file        "$VAL_FILE" \
        --output_dir      "$OUTPUT_DIR" \
        --epochs          "$EPOCHS" \
        --batch_size      "$BATCH_SIZE" \
        --grad_accum      "$GRAD_ACCUM" \
        --max_seq_length  "$MAX_SEQ_LEN"
fi

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

# ── Phase 15/16 rollout — run after KL or trajectory training ────────────────
if [ "$USE_TRAJ" = "1" ] || [ "$USE_KL" = "1" ]; then
    echo ""
    echo "========================================"
    echo " PHASE 3: TRAJECTORY ROLLOUT (Phase 15)"
    echo "========================================"
    python /root/simulation_rollout.py \
        --backend  unsloth \
        --adapter  "$OUTPUT_DIR" \
        --val-file "$VAL_FILE" \
        --batch \
        --steps   15 \
        --samples  3 \
        --out-file /root/rollout_results.json
    echo "Rollout complete. Results at /root/rollout_results.json"
fi

echo ""
echo "========================================"
echo " DONE."
echo " Download with:"
echo "   scp -P <PORT> -i <KEY> root@<IP>:/root/eval_results.json ."
echo "   scp -P <PORT> -i <KEY> root@<IP>:/root/rollout_results.json ."
echo "   scp -P <PORT> -i <KEY> -r root@<IP>:$OUTPUT_DIR ."
echo "========================================"
