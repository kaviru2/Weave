#!/bin/bash
# runpod_eval_phase23.sh — Eval Phase 23 adapter on 798 GoKer (apples-to-apples with P21).
# Run after training completes.
#
# Usage:
#   RUNPOD_IP=<ip> RUNPOD_PORT=<port> bash scripts/runpod_eval_phase23.sh

set -e

RUNPOD_IP="${RUNPOD_IP:?Set RUNPOD_IP}"
RUNPOD_PORT="${RUNPOD_PORT:?Set RUNPOD_PORT}"
RUNPOD_KEY="${RUNPOD_KEY:-$HOME/.ssh/id_runpod}"

SSH_OPTS="-p $RUNPOD_PORT -i $RUNPOD_KEY -o StrictHostKeyChecking=no"
SCP_OPTS="-P $RUNPOD_PORT -i $RUNPOD_KEY -o StrictHostKeyChecking=no"

echo "========================================"
echo " Weave — Phase 23 Eval"
echo " Phase 23 adapter x 798 GoKer (P21 val set)"
echo " Pod: root@$RUNPOD_IP:$RUNPOD_PORT"
echo "========================================"

# ── 1. Verify connection ───────────────────────────────────────────────────────
echo "[1/3] Testing SSH connection..."
ssh $SSH_OPTS root@$RUNPOD_IP "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader"

# ── 2. Upload 798-example val set for apples-to-apples comparison ─────────────
echo "[2/3] Uploading Phase 21 val set (798 GoKer, plain prompts)..."
scp $SCP_OPTS \
    eval/results/eval_results_phase21_798.json \
    root@$RUNPOD_IP:/root/eval_results_phase21_798_ref.json 2>/dev/null || true

# Upload the 798-example plain val set — rebuild from Phase 21 val_point_dups
# We use the current val_point_dups.jsonl (1287 ex) and filter to first 798 for comparison,
# OR simply eval on the full 1287-example set and compare with Phase 22 (25.3%).
# Decision: eval on full 1287 val set for maximum data, note Phase 21 used 798.

echo "[3/3] Launching eval..."
ssh $SSH_OPTS root@$RUNPOD_IP "
    export HF_HOME=/workspace/hf_cache
    nohup python -u /root/run_eval.py \
        --adapter  /root/lora_adapter_phase23 \
        --val_file /root/val_point_dups.jsonl \
        --load_in_4bit \
        --out_file /root/eval_results_phase23.json \
        > /root/eval_phase23.log 2>&1 &
    echo \"Eval PID: \$!\"
"

echo ""
echo "========================================"
echo " Eval running in background."
echo ""
echo " Monitor:"
echo "   ssh root@$RUNPOD_IP -p $RUNPOD_PORT -i $RUNPOD_KEY 'tail -f /root/eval_phase23.log'"
echo ""
echo " Download when done:"
echo "   scp $SCP_OPTS root@$RUNPOD_IP:/root/eval_results_phase23.json eval/results/eval_results_phase23.json"
echo "   scp $SCP_OPTS -r root@$RUNPOD_IP:/root/lora_adapter_phase23 lora_adapter_phase23/"
echo "========================================"
