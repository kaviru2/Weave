#!/bin/bash
# runpod_pod.sh — runs INSIDE the RunPod pod
# Installs deps, trains, evals, prints results.
# Usage: bash /root/runpod_pod.sh
set -e

MODEL_ID="${MODEL_ID:-Qwen/Qwen2.5-Coder-1.5B-Instruct}"
TRAIN_FILE="${TRAIN_FILE:-/root/train_point_dups.jsonl}"
VAL_FILE="${VAL_FILE:-/root/val_point_dups.jsonl}"
OUTPUT_DIR="${OUTPUT_DIR:-/root/lora_adapter}"
EPOCHS="${EPOCHS:-3}"
BATCH_SIZE="${BATCH_SIZE:-4}"
GRAD_ACCUM="${GRAD_ACCUM:-2}"
MAX_SEQ_LEN="${MAX_SEQ_LEN:-4096}"

echo "========================================"
echo " Weave RunPod Training Script"
echo " Model:      $MODEL_ID"
echo " Epochs:     $EPOCHS | Batch: $BATCH_SIZE | Seq: $MAX_SEQ_LEN"
echo " GPU:        $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo unknown)"
echo "========================================"

# ── Install deps pinned to torch 2.4.x (what RunPod PyTorch template ships) ──
TORCH_VER=$(python -c "import torch; print(torch.__version__.split('+')[0])" 2>/dev/null || echo "0.0.0")
TORCH_MAJOR=$(echo $TORCH_VER | cut -d. -f1)
TORCH_MINOR=$(echo $TORCH_VER | cut -d. -f2)

echo ""
echo "Detected PyTorch $TORCH_VER — installing compatible deps..."

if [ "$TORCH_MAJOR" -ge 2 ] && [ "$TORCH_MINOR" -ge 5 ]; then
    # torch 2.5+ — use latest
    pip install -q peft trl bitsandbytes accelerate datasets transformers
else
    # torch 2.4.x — pin to last known-good versions
    pip install -q \
        'transformers==4.46.3' \
        'peft==0.13.2' \
        'trl==0.11.4' \
        'bitsandbytes==0.44.1' \
        'accelerate==0.34.2' \
        'datasets==3.0.1'
fi

echo "Deps installed."

# ── Train ─────────────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo " PHASE 1: TRAINING"
echo "========================================"

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

python /root/train_lora.py \
    --model_id       "$MODEL_ID" \
    --train_file     "$TRAIN_FILE" \
    --val_file       "$VAL_FILE" \
    --output_dir     "$OUTPUT_DIR" \
    --epochs         "$EPOCHS" \
    --batch_size     "$BATCH_SIZE" \
    --grad_accum     "$GRAD_ACCUM" \
    --max_seq_length "$MAX_SEQ_LEN"

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
