#!/usr/bin/env python3
"""Generate fig7: Phase 17 ablation analysis — format vs step-count vs volume."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path

OUT_DIR = Path("eval/figures")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Data ──────────────────────────────────────────────────────────────────────
models = [
    "Phase 13\n(CE, 3ep)",
    "Ablation B\n(point, 6ep)",
    "Ablation A\n(1-step traj, 3ep)",
    "Phase 16\n(traj 3–5, 3ep)",
]
accs = [36.2, 35.3, 40.1, 40.1]
colors = ["#5b8dd9", "#e07b54", "#6abf69", "#2e7d32"]

# Effect decomposition bar data
effects = {
    "Format effect\n(Abl A vs Ph 13)": 40.1 - 36.2,
    "Step-count effect\n(Ph 16 vs Abl A)": 40.1 - 40.1,
    "Volume effect\n(Abl B vs Ph 13)": 35.3 - 36.2,
    "Struct effect\n(Ph 16 vs Abl B)": 40.1 - 35.3,
}
effect_colors = ["#2e7d32" if v > 0 else "#c62828" for v in effects.values()]

fig, axes = plt.subplots(1, 2, figsize=(12, 5))
fig.suptitle("Phase 17 Ablation Analysis — Why Does Trajectory Training Work?",
             fontsize=13, fontweight="bold", y=1.01)

# ── Left: accuracy bar chart ──────────────────────────────────────────────────
ax = axes[0]
x = np.arange(len(models))
bars = ax.bar(x, accs, color=colors, width=0.55, edgecolor="white", linewidth=0.8)

for bar, val in zip(bars, accs):
    ax.text(bar.get_x() + bar.get_width() / 2, val + 0.3,
            f"{val:.1f}%", ha="center", va="bottom", fontsize=10, fontweight="bold")

# bracket: format effect
ax.annotate("", xy=(2, 41.5), xytext=(0, 41.5),
            arrowprops=dict(arrowstyle="<->", color="#2e7d32", lw=1.5))
ax.text(1, 42.0, "+3.9 pp\n(format)", ha="center", va="bottom",
        fontsize=8.5, color="#2e7d32", fontweight="bold")

# bracket: no step-count effect
ax.annotate("", xy=(3, 41.5), xytext=(2, 41.5),
            arrowprops=dict(arrowstyle="<->", color="#999999", lw=1.5))
ax.text(2.5, 42.0, "0 pp\n(steps)", ha="center", va="bottom",
        fontsize=8.5, color="#888888")

ax.set_xticks(x)
ax.set_xticklabels(models, fontsize=9)
ax.set_ylabel("Single-step accuracy (GoKer held-out)", fontsize=10)
ax.set_ylim(30, 44)
ax.set_title("Model Accuracy", fontsize=11)
ax.axhline(40.1, color="#2e7d32", linestyle="--", linewidth=0.8, alpha=0.5)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.grid(axis="y", alpha=0.3)

# ── Right: effect decomposition ───────────────────────────────────────────────
ax2 = axes[1]
labels = list(effects.keys())
vals = list(effects.values())
x2 = np.arange(len(labels))
bars2 = ax2.bar(x2, vals, color=effect_colors, width=0.5,
                edgecolor="white", linewidth=0.8)

for bar, val in zip(bars2, vals):
    ypos = val + 0.05 if val >= 0 else val - 0.25
    ax2.text(bar.get_x() + bar.get_width() / 2, ypos,
             f"{val:+.1f} pp", ha="center", va="bottom" if val >= 0 else "top",
             fontsize=10, fontweight="bold",
             color="#2e7d32" if val > 0 else "#c62828" if val < 0 else "#888888")

ax2.axhline(0, color="black", linewidth=0.8)
ax2.set_xticks(x2)
ax2.set_xticklabels(labels, fontsize=8.5)
ax2.set_ylabel("Accuracy delta (pp)", fontsize=10)
ax2.set_ylim(-2, 6.5)
ax2.set_title("Effect Decomposition", fontsize=11)
ax2.spines["top"].set_visible(False)
ax2.spines["right"].set_visible(False)
ax2.grid(axis="y", alpha=0.3)

pos_patch = mpatches.Patch(color="#2e7d32", label="Positive effect")
neg_patch = mpatches.Patch(color="#c62828", label="Negative / no effect")
ax2.legend(handles=[pos_patch, neg_patch], fontsize=8.5, loc="upper right")

plt.tight_layout()
for ext in ("png", "pdf"):
    path = OUT_DIR / f"fig7_ablation_analysis.{ext}"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"Saved {path}")

plt.close()
print("Done.")
