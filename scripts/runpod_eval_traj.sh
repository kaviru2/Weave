#!/bin/bash
# runpod_eval_traj.sh — eval-only deploy for the Phase 16 trajectory-trained adapter.
# Uploads adapter + val data + eval script, installs deps, runs eval in tmux.
#
# Usage:
#   RUNPOD_IP=<ip> RUNPOD_PORT=<port> bash scripts/runpod_eval_traj.sh
#
# Optional:
#   RUNPOD_KEY  — SSH key (default: ~/.ssh/id_runpod)

set -e

RUNPOD_IP="${RUNPOD_IP:?Set RUNPOD_IP}"
RUNPOD_PORT="${RUNPOD_PORT:?Set RUNPOD_PORT}"
RUNPOD_KEY="${RUNPOD_KEY:-$HOME/.ssh/id_runpod}"

SSH_OPTS="-p $RUNPOD_PORT -i $RUNPOD_KEY -o StrictHostKeyChecking=no"
SCP_OPTS="-P $RUNPOD_PORT -i $RUNPOD_KEY -o StrictHostKeyChecking=no"

echo "========================================"
echo " Weave — Phase 16 Traj Accuracy Eval"
echo " Pod: root@$RUNPOD_IP:$RUNPOD_PORT"
echo "========================================"

# ── 1. Verify connection ───────────────────────────────────────────────────────
echo ""
echo "[1/4] Testing SSH connection..."
ssh $SSH_OPTS root@$RUNPOD_IP "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader"

# ── 2. Upload files ────────────────────────────────────────────────────────────
echo ""
echo "[2/4] Uploading eval script + val data (this may take a moment)..."
scp $SCP_OPTS \
    scripts/run_eval.py \
    dataset/output/val_point_dups.jsonl \
    root@$RUNPOD_IP:/root/

echo "Uploading traj adapter (166MB)..."
ssh $SSH_OPTS root@$RUNPOD_IP "mkdir -p /root/lora_adapter_traj"
scp $SCP_OPTS -r \
    dataset/output/lora_adapter_traj/ \
    root@$RUNPOD_IP:/root/lora_adapter_traj/

echo "Files uploaded."

# ── 3. Install deps ────────────────────────────────────────────────────────────
echo ""
echo "[3/4] Installing deps..."
ssh $SSH_OPTS root@$RUNPOD_IP "
    export HF_HOME=/workspace/hf_cache
    mkdir -p /workspace/hf_cache
    pip install -q transformers peft accelerate bitsandbytes datasets
"
echo "Deps installed."

# ── 4. Launch eval in tmux ─────────────────────────────────────────────────────
echo ""
echo "[4/4] Launching eval in tmux session 'eval'..."
ssh $SSH_OPTS root@$RUNPOD_IP "
    export HF_HOME=/workspace/hf_cache
    tmux kill-session -t eval 2>/dev/null || true
    tmux new-session -d -s eval
    tmux send-keys -t eval '
        export HF_HOME=/workspace/hf_cache
        python -u /root/run_eval.py \
            --adapter  /root/lora_adapter_traj \
            --val_file /root/val_point_dups.jsonl \
            --model_id "${MODEL_ID:-Qwen/Qwen3-8B}" \
            --load_in_4bit \
            --out_file /root/eval_results_traj.json \
            2>&1 | tee /root/eval_traj.log
    ' Enter
    echo 'Eval launched.'
"

echo ""
echo "========================================"
echo " Eval running in tmux on the pod."
echo ""
echo " Monitor logs:"
echo "   ssh root@$RUNPOD_IP -p $RUNPOD_PORT -i $RUNPOD_KEY"
echo "   tmux attach -t eval"
echo ""
echo " Check progress remotely:"
echo "   ssh root@$RUNPOD_IP -p $RUNPOD_PORT -i $RUNPOD_KEY 'tail -5 /root/eval_traj.log'"
echo ""
echo " Download results when done:"
echo "   scp $SCP_OPTS root@$RUNPOD_IP:/root/eval_results_traj.json eval/results/eval_results_traj_accuracy.json"
echo "========================================"
