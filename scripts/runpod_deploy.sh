#!/bin/bash
# runpod_deploy.sh — runs LOCALLY to deploy and start training on a RunPod pod.
#
# Usage:
#   chmod +x scripts/runpod_deploy.sh
#   RUNPOD_IP=69.30.85.12 RUNPOD_PORT=22013 bash scripts/runpod_deploy.sh
#
# Optional env vars:
#   RUNPOD_KEY   — SSH key path (default: ~/.ssh/id_runpod)
#   MODEL_ID     — HuggingFace model (default: Qwen/Qwen2.5-Coder-7B-Instruct)
#   EPOCHS       — training epochs (default: 3)
#   BATCH_SIZE   — per-device batch size (default: 1, tuned for 20GB VRAM)
#   GRAD_ACCUM   — gradient accumulation steps (default: 8)
#   MAX_SEQ_LEN  — max sequence length (default: 4096)
#   KL_WEIGHT    — KL loss weight for Phase 14 (default: 1.0; 0 = pure CE ablation)
#   USE_KL       — set to "1" to use train_lora_kl.py instead of train_lora_unsloth.py

set -e

RUNPOD_IP="${RUNPOD_IP:?Set RUNPOD_IP to your pod's IP}"
RUNPOD_PORT="${RUNPOD_PORT:?Set RUNPOD_PORT to your pod's SSH port}"
RUNPOD_KEY="${RUNPOD_KEY:-$HOME/.ssh/id_runpod}"
MODEL_ID="${MODEL_ID:-Qwen/Qwen2.5-Coder-7B-Instruct}"
EPOCHS="${EPOCHS:-3}"
BATCH_SIZE="${BATCH_SIZE:-1}"
GRAD_ACCUM="${GRAD_ACCUM:-8}"
MAX_SEQ_LEN="${MAX_SEQ_LEN:-4096}"
KL_WEIGHT="${KL_WEIGHT:-1.0}"
USE_KL="${USE_KL:-0}"

SSH_OPTS="-p $RUNPOD_PORT -i $RUNPOD_KEY -o StrictHostKeyChecking=no"
SCP_OPTS="-P $RUNPOD_PORT -i $RUNPOD_KEY -o StrictHostKeyChecking=no"

echo "========================================"
echo " Weave RunPod Deploy"
echo " Pod: root@$RUNPOD_IP:$RUNPOD_PORT"
echo " Key: $RUNPOD_KEY"
echo "========================================"

# ── 1. Verify connection ───────────────────────────────────────────────────────
echo ""
echo "[1/4] Testing SSH connection..."
ssh $SSH_OPTS root@$RUNPOD_IP "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader"

# ── 2. Upload files ────────────────────────────────────────────────────────────
echo ""
echo "[2/4] Uploading files..."
scp $SCP_OPTS \
    dataset/output/kaggle_upload/train_point_dups.jsonl \
    dataset/output/kaggle_upload/val_point_dups.jsonl \
    dataset/output/aggregated.json \
    dataset/train_lora_unsloth.py \
    dataset/train_lora_kl.py \
    eval/simulation_rollout.py \
    scripts/run_eval.py \
    scripts/runpod_pod.sh \
    root@$RUNPOD_IP:/root/

echo "Files uploaded."

# ── 3. Install tmux ───────────────────────────────────────────────────────────
echo ""
echo "[3/4] Installing tmux..."
ssh $SSH_OPTS root@$RUNPOD_IP "apt-get update -q && apt-get install -y tmux -q 2>/dev/null || true"

# ── 4. Launch training in tmux ────────────────────────────────────────────────
echo ""
echo "[4/4] Launching training in tmux session 'train'..."
ssh $SSH_OPTS root@$RUNPOD_IP "
    tmux kill-session -t train 2>/dev/null || true
    tmux new-session -d -s train
    tmux send-keys -t train 'MODEL_ID=$MODEL_ID EPOCHS=$EPOCHS BATCH_SIZE=$BATCH_SIZE GRAD_ACCUM=$GRAD_ACCUM MAX_SEQ_LEN=$MAX_SEQ_LEN KL_WEIGHT=$KL_WEIGHT USE_KL=$USE_KL bash /root/runpod_pod.sh 2>&1 | tee /root/train.log' Enter
    echo 'Training launched.'
"

echo ""
echo "========================================"
echo " Training running in tmux on the pod."
echo ""
echo " Monitor logs:"
echo "   ssh root@$RUNPOD_IP -p $RUNPOD_PORT -i $RUNPOD_KEY"
echo "   tmux attach -t train"
echo ""
echo " Check progress remotely:"
echo "   ssh root@$RUNPOD_IP -p $RUNPOD_PORT -i $RUNPOD_KEY 'tail -5 /root/train.log'"
echo ""
echo " Download results when done:"
echo "   scp $SCP_OPTS root@$RUNPOD_IP:/root/eval_results.json eval/results/eval_results_runpod.json"
echo "   scp $SCP_OPTS -r root@$RUNPOD_IP:/root/lora_adapter dataset/output/lora_adapter_v3"
echo "========================================"
