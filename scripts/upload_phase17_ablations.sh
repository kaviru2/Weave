#!/bin/bash
# Upload Phase 17 ablation adapters to HuggingFace

set -e

echo "=== Weave Phase 17 — Upload Ablations ==="
echo ""

# Ablation A (1-step trajectory)
echo "[1/3] Ablation A (1-step trajectory, 40.1% accuracy)"
echo "      Repo: kavirubc/weave-ccwm-qwen2.5-coder-7b-ablation-1step-traj"
uv run python scripts/upload_model_hf.py \
    --repo kavirubc/weave-ccwm-qwen2.5-coder-7b-ablation-1step-traj \
    --adapter dataset/output/lora_ablation_1step \
    --dry-run

echo ""
echo "To upload, remove --dry-run:"
echo "  uv run python scripts/upload_model_hf.py --repo kavirubc/weave-ccwm-qwen2.5-coder-7b-ablation-1step-traj --adapter dataset/output/lora_ablation_1step"

echo ""
echo "[2/3] Ablation B (point 6 epochs, pending results)"
echo "      Repo: kavirubc/weave-ccwm-qwen2.5-coder-7b-ablation-point-6ep"
echo "      Status: Waiting for training to complete on RunPod"
echo "      Command when ready:"
echo "        uv run python scripts/upload_model_hf.py --repo kavirubc/weave-ccwm-qwen2.5-coder-7b-ablation-point-6ep --adapter dataset/output/lora_ablation_point6ep"

echo ""
echo "[3/3] Phase 16 (trajectory training, 40.1% accuracy, 10.48 survival)"
echo "      Repo: kavirubc/weave-ccwm-qwen2.5-coder-7b-traj-lora"
echo "      Status: Verify if already uploaded, or use:"
echo "        uv run python scripts/upload_model_hf.py --repo kavirubc/weave-ccwm-qwen2.5-coder-7b-traj-lora --adapter dataset/output/lora_adapter_traj"

echo ""
echo "=== Summary ==="
echo "After all ablations complete and download, run uploads without --dry-run"
echo "Adapters required for paper reproduction:"
echo "  1. Phase 16 (trajectory) — best single-step + 10x coherence"
echo "  2. Ablation A (1-step traj) — proves format matters"
echo "  3. Ablation B (point 6ep) — proves volume alone insufficient"
