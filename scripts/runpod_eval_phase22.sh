#!/bin/bash
# runpod_eval_phase22.sh — Phase 22 eval: Phase 21 adapter on all 103 GoKer programs (1287 examples).
#
# Usage:
#   RUNPOD_IP=<ip> RUNPOD_PORT=<port> bash scripts/runpod_eval_phase22.sh
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
echo " Weave — Phase 22 Eval"
echo " Phase 21 adapter x 103 GoKer (1287 ex)"
echo " Pod: root@$RUNPOD_IP:$RUNPOD_PORT"
echo "========================================"

# ── 1. Verify connection ───────────────────────────────────────────────────────
echo ""
echo "[1/4] Testing SSH connection..."
ssh $SSH_OPTS root@$RUNPOD_IP "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader"

# ── 2. Upload files ────────────────────────────────────────────────────────────
echo ""
echo "[2/4] Uploading eval script + expanded val data (1287 examples)..."
scp $SCP_OPTS \
    scripts/run_eval.py \
    dataset/output/val_point_dups.jsonl \
    root@$RUNPOD_IP:/root/

echo "Uploading Phase 21 adapter (178MB)..."
ssh $SSH_OPTS root@$RUNPOD_IP "mkdir -p /root/lora_adapter_phase21"
scp $SCP_OPTS \
    lora_adapter_phase21/adapter_config.json \
    lora_adapter_phase21/adapter_model.safetensors \
    lora_adapter_phase21/tokenizer_config.json \
    lora_adapter_phase21/tokenizer.json \
    root@$RUNPOD_IP:/root/lora_adapter_phase21/

echo "Files uploaded."

# ── 3. Install deps ────────────────────────────────────────────────────────────
echo ""
echo "[3/4] Installing deps..."
ssh $SSH_OPTS root@$RUNPOD_IP "
    export HF_HOME=/workspace/hf_cache
    mkdir -p /workspace/hf_cache
    pip install -q transformers==4.51.0 peft accelerate bitsandbytes torchvision
    pip install -q -U bitsandbytes
"
echo "Deps installed."

# ── 4. Launch eval (nohup — no tmux needed) ───────────────────────────────────
echo ""
echo "[4/4] Launching eval..."
ssh $SSH_OPTS root@$RUNPOD_IP "
    export HF_HOME=/workspace/hf_cache
    nohup python -u /root/run_eval.py \
        --adapter  /root/lora_adapter_phase21 \
        --val_file /root/val_point_dups.jsonl \
        --load_in_4bit \
        --out_file /root/eval_results_phase22.json \
        > /root/eval_phase22.log 2>&1 &
    echo \"Eval PID: \$!\"
"

echo ""
echo "========================================"
echo " Eval running in background on the pod."
echo ""
echo " Monitor logs:"
echo "   ssh root@$RUNPOD_IP -p $RUNPOD_PORT -i $RUNPOD_KEY 'tail -20 /root/eval_phase22.log'"
echo ""
echo " Download results when done:"
echo "   scp $SCP_OPTS root@$RUNPOD_IP:/root/eval_results_phase22.json eval/results/eval_results_phase22.json"
echo "========================================"
