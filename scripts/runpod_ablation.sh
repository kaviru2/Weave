#!/bin/bash
# runpod_ablation.sh — runs LOCALLY to deploy Phase 17 ablations to RunPod.
#
# Usage:
#   RUNPOD_IP=<ip> RUNPOD_PORT=<port> bash scripts/runpod_ablation.sh
#
# Optional:
#   RUNPOD_KEY — SSH key (default: ~/.ssh/id_runpod)
set -e

RUNPOD_IP="${RUNPOD_IP:?Set RUNPOD_IP}"
RUNPOD_PORT="${RUNPOD_PORT:?Set RUNPOD_PORT}"
RUNPOD_KEY="${RUNPOD_KEY:-$HOME/.ssh/id_runpod}"

SSH="ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 -p $RUNPOD_PORT -i $RUNPOD_KEY root@$RUNPOD_IP"
SCP="scp -o StrictHostKeyChecking=no -P $RUNPOD_PORT -i $RUNPOD_KEY"

echo "========================================"
echo " Weave Phase 17 — Ablation Deploy"
echo " Pod: root@$RUNPOD_IP:$RUNPOD_PORT"
echo "========================================"

# ── 1. Verify connection ──────────────────────────────────────────────────────
echo ""
echo "[1/4] Testing SSH connection..."
$SSH "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader"

# ── 2. Upload files ───────────────────────────────────────────────────────────
echo ""
echo "[2/4] Uploading files..."
$SCP \
    dataset/output/train_traj_1step.jsonl \
    dataset/output/val_traj_1step.jsonl \
    dataset/output/train_point_dups.jsonl \
    dataset/output/val_point_dups.jsonl \
    dataset/train_lora_trajectory.py \
    dataset/train_lora_unsloth.py \
    scripts/run_eval.py \
    scripts/runpod_ablation_pod.sh \
    root@$RUNPOD_IP:/root/
echo "Files uploaded."

# ── 3. Install tmux ───────────────────────────────────────────────────────────
echo ""
echo "[3/4] Installing tmux..."
$SSH "apt-get install -y tmux -q 2>/dev/null || true"

# ── 4. Launch in tmux ─────────────────────────────────────────────────────────
echo ""
echo "[4/4] Launching ablations in tmux session 'ablation'..."
$SSH "
    mkdir -p /workspace
    tmux kill-session -t ablation 2>/dev/null || true
    tmux new-session -d -s ablation
    tmux send-keys -t ablation 'bash /root/runpod_ablation_pod.sh 2>&1 | tee /workspace/ablation_main.log' Enter
    echo 'Launched.'
"

echo ""
echo "========================================"
echo " Ablations running (~2h55m, ~\$0.75)"
echo ""
echo " Monitor:"
echo "   $SSH 'tmux attach -t ablation'"
echo ""
echo " Quick progress check:"
echo "   $SSH 'tail -3 /workspace/train_1step.log 2>/dev/null; tail -3 /workspace/train_point6ep.log 2>/dev/null'"
echo ""
echo " Check completion:"
echo "   $SSH 'ls /workspace/eval_ablation_1step.json /workspace/eval_ablation_point6ep.json 2>/dev/null'"
echo ""
echo " GPU status:"
echo "   $SSH 'nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader'"
echo ""
echo " Download results when done:"
echo "   $SCP root@$RUNPOD_IP:/workspace/eval_ablation_1step.json eval/results/"
echo "   $SCP root@$RUNPOD_IP:/workspace/eval_ablation_point6ep.json eval/results/"
echo "========================================"
