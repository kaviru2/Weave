#!/bin/bash
# runpod_deploy_phase23.sh — Phase 23: Stratified CE training (balanced event types).
# Tests the Class 1 taxonomy claim: GoSched/GoEnd at 0% is a data imbalance problem.
#
# Usage:
#   RUNPOD_IP=<ip> RUNPOD_PORT=<port> bash scripts/runpod_deploy_phase23.sh
#
# Optional:
#   RUNPOD_KEY  — SSH key (default: ~/.ssh/id_runpod)
#   EPOCHS      — training epochs (default: 3)

set -e

RUNPOD_IP="${RUNPOD_IP:?Set RUNPOD_IP}"
RUNPOD_PORT="${RUNPOD_PORT:?Set RUNPOD_PORT}"
RUNPOD_KEY="${RUNPOD_KEY:-$HOME/.ssh/id_runpod}"
EPOCHS="${EPOCHS:-3}"

SSH_OPTS="-p $RUNPOD_PORT -i $RUNPOD_KEY -o StrictHostKeyChecking=no"
SCP_OPTS="-P $RUNPOD_PORT -i $RUNPOD_KEY -o StrictHostKeyChecking=no"

echo "========================================"
echo " Weave — Phase 23: Stratified CE Train"
echo " Balanced: 200 examples/event type"
echo " Train: 2004 ex | Val: 1287 ex (103 GoKer)"
echo " Pod: root@$RUNPOD_IP:$RUNPOD_PORT"
echo "========================================"

# ── 1. Verify connection ───────────────────────────────────────────────────────
echo ""
echo "[1/5] Testing SSH connection..."
ssh $SSH_OPTS root@$RUNPOD_IP "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader"

# ── 2. Upload files ────────────────────────────────────────────────────────────
echo ""
echo "[2/5] Uploading training data + scripts..."
scp $SCP_OPTS \
    dataset/output/train_point_dups_balanced.jsonl \
    dataset/output/val_point_dups.jsonl \
    dataset/train_lora_unsloth.py \
    scripts/run_eval.py \
    root@$RUNPOD_IP:/root/

echo "Files uploaded."

# ── 3. Install deps ────────────────────────────────────────────────────────────
echo ""
echo "[3/5] Installing deps (unsloth handles everything)..."
ssh $SSH_OPTS root@$RUNPOD_IP "
    export HF_HOME=/workspace/hf_cache
    mkdir -p /workspace/hf_cache
    pip install -q unsloth
    pip install -q -U transformers peft bitsandbytes accelerate
"
echo "Deps installed."

# ── 4. Launch training ────────────────────────────────────────────────────────
echo ""
echo "[4/5] Launching Phase 23 CE training (balanced)..."
ssh $SSH_OPTS root@$RUNPOD_IP "
    export HF_HOME=/workspace/hf_cache
    HF_HOME=/workspace/hf_cache nohup python -u /root/train_lora_unsloth.py \
        --model_id   Qwen/Qwen3-8B \
        --train_file /root/train_point_dups_balanced.jsonl \
        --val_file   /root/val_point_dups.jsonl \
        --output_dir /root/lora_adapter_phase23 \
        --epochs     $EPOCHS \
        --batch_size 1 \
        --grad_accum 8 \
        --max_seq_length 4096 \
        > /root/train_phase23.log 2>&1 &
    echo \"Training PID: \$!\"
"

echo ""
echo "========================================"
echo " Training launched."
echo ""
echo " Monitor:"
echo "   ssh root@\$RUNPOD_IP -p \$RUNPOD_PORT -i \$RUNPOD_KEY 'tail -f /root/train_phase23.log'"
echo ""
echo " When training done, run eval:"
echo "   RUNPOD_IP=$RUNPOD_IP RUNPOD_PORT=$RUNPOD_PORT bash scripts/runpod_eval_phase23.sh"
echo "========================================"
