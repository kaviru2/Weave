#!/bin/bash
# runpod_ablation_pod.sh — runs INSIDE the RunPod pod.
# Executes Phase 17 ablations sequentially:
#   A) 1-step trajectory training  (answers: does multi-turn format help?)
#   B) Point training × 6 epochs   (answers: does more training alone help?)
# All outputs saved to /workspace (persistent volume).
set -e

MODEL_ID="${MODEL_ID:-Qwen/Qwen3-8B-Instruct}"
BATCH_SIZE="${BATCH_SIZE:-1}"
GRAD_ACCUM="${GRAD_ACCUM:-8}"

# Persistent storage — survives pod restart
export HF_HOME=/workspace/hf_cache
mkdir -p /workspace/hf_cache
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True,max_split_size_mb:512
export HF_HUB_DISABLE_XET=1

echo "========================================"
echo " Weave Phase 17 — Ablation Experiments"
echo " Model: $MODEL_ID"
echo " GPU:   $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader)"
echo " HF cache: $HF_HOME"
echo "========================================"

# ── Install deps ─────────────────────────────────────────────────────────────
echo ""
echo "[SETUP] Installing dependencies..."
pip install -q unsloth trl peft accelerate bitsandbytes datasets
echo "[SETUP] Done."

# ─────────────────────────────────────────────────────────────────────────────
# ABLATION A — 1-step trajectory training
# Purpose: isolate whether multi-turn FORMAT helps vs step count
# Train: train_traj_1step.jsonl (630 examples, 1 assistant turn each)
# Eval:  val_point_dups.jsonl (798 examples, comparable to Phase 13/16)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo " ABLATION A: 1-step trajectory training"
echo "========================================"

python -u /root/train_lora_trajectory.py \
    --model_id       "$MODEL_ID" \
    --train_file     /root/train_traj_1step.jsonl \
    --val_file       /root/val_traj_1step.jsonl \
    --output_dir     /workspace/lora_ablation_1step \
    --epochs         3 \
    --batch_size     "$BATCH_SIZE" \
    --grad_accum     "$GRAD_ACCUM" \
    --max_seq_length 4096 \
    2>&1 | tee /workspace/train_1step.log

echo "[ABLATION A] Training complete."

echo ""
echo "[ABLATION A] Running accuracy eval on GoKer held-out..."
python -u /root/run_eval.py \
    --adapter  /workspace/lora_ablation_1step \
    --val_file /root/val_point_dups.jsonl \
    --model_id "$MODEL_ID" \
    --out_file /workspace/eval_ablation_1step.json \
    2>&1 | tee -a /workspace/train_1step.log

echo "[ABLATION A] DONE. Results at /workspace/eval_ablation_1step.json"

# Print quick result
python3 -c "
import json
r = json.load(open('/workspace/eval_ablation_1step.json'))
print(f'ABLATION A RESULT: {r[\"correct\"]}/{r[\"total_examples\"]} = {r[\"accuracy\"]:.1%}')
print(f'  (Phase 13 baseline: 36.2%, Phase 16 traj: 40.1%)')
"

# ─────────────────────────────────────────────────────────────────────────────
# ABLATION B — Extended point training (6 epochs)
# Purpose: control for training duration / total gradient signal
# Train: train_point_dups.jsonl (945 examples, same as Phase 13)
# Eval:  val_point_dups.jsonl (798 examples)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo " ABLATION B: Point training × 6 epochs"
echo "========================================"

python -u /root/train_lora_unsloth.py \
    --model_id       "$MODEL_ID" \
    --train_file     /root/train_point_dups.jsonl \
    --val_file       /root/val_point_dups.jsonl \
    --output_dir     /workspace/lora_ablation_point6ep \
    --epochs         6 \
    --batch_size     "$BATCH_SIZE" \
    --grad_accum     "$GRAD_ACCUM" \
    --max_seq_length 4096 \
    2>&1 | tee /workspace/train_point6ep.log

echo "[ABLATION B] Training complete."

echo ""
echo "[ABLATION B] Running accuracy eval on GoKer held-out..."
python -u /root/run_eval.py \
    --adapter  /workspace/lora_ablation_point6ep \
    --val_file /root/val_point_dups.jsonl \
    --model_id "$MODEL_ID" \
    --out_file /workspace/eval_ablation_point6ep.json \
    2>&1 | tee -a /workspace/train_point6ep.log

echo "[ABLATION B] DONE. Results at /workspace/eval_ablation_point6ep.json"

python3 -c "
import json
r = json.load(open('/workspace/eval_ablation_point6ep.json'))
print(f'ABLATION B RESULT: {r[\"correct\"]}/{r[\"total_examples\"]} = {r[\"accuracy\"]:.1%}')
print(f'  (Phase 13 baseline: 36.2%, Phase 16 traj: 40.1%)')
"

# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo " PHASE 17 COMPLETE"
python3 -c "
import json
a = json.load(open('/workspace/eval_ablation_1step.json'))
b = json.load(open('/workspace/eval_ablation_point6ep.json'))
print(f'  Phase 13 (CE 3ep):          36.2%')
print(f'  Ablation A (1-step traj):   {a[\"accuracy\"]:.1%}')
print(f'  Ablation B (point 6ep):     {b[\"accuracy\"]:.1%}')
print(f'  Phase 16 (traj 3-5 steps):  40.1%')
"
echo ""
echo " Download results:"
echo "   scp -P PORT -i KEY root@IP:/workspace/eval_ablation_1step.json eval/results/"
echo "   scp -P PORT -i KEY root@IP:/workspace/eval_ablation_point6ep.json eval/results/"
echo "========================================"
