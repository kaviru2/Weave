#!/usr/bin/env python3
"""
Generate all figures and tables for the Weave ICSE paper.
Run: uv run --with matplotlib --with numpy --with seaborn python eval/generate_paper_figures.py

Outputs to eval/figures/
"""
import json, os, statistics
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns

OUT = "eval/figures"
os.makedirs(OUT, exist_ok=True)

TRAJ_ACC  = "eval/results/eval_results_traj_accuracy.json"
ROLLOUT   = "eval/results/rollout_results_traj.json"

r_acc     = json.load(open(TRAJ_ACC))
r_roll    = json.load(open(ROLLOUT))

# ── Colour palette ────────────────────────────────────────────────────────────
BLUE   = "#2563EB"
GREEN  = "#16A34A"
ORANGE = "#EA580C"
GRAY   = "#6B7280"
RED    = "#DC2626"
PURPLE = "#7C3AED"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.spines.top":   False,
    "axes.spines.right": False,
})

# ─────────────────────────────────────────────────────────────────────────────
# Fig 1 — Model accuracy comparison (all phases)
# ─────────────────────────────────────────────────────────────────────────────
models = [
    ("7B zero-shot",           0.286, GRAY,   "GoKer held-out"),
    ("Gemini Flash\nzero-shot",0.348, ORANGE, "GoKer held-out"),
    ("7B CE fine-tuned\n(Phase 13)",   0.362, BLUE,   "GoKer held-out"),
    ("7B KL fine-tuned\n(Phase 14)",   0.358, PURPLE, "GoKer held-out"),
    ("7B Traj fine-tuned\n(Phase 16)", 0.401, GREEN,  "GoKer held-out"),
]

fig, ax = plt.subplots(figsize=(8, 4.2))
xs = range(len(models))
bars = ax.bar(xs, [m[1] for m in models], color=[m[2] for m in models],
              width=0.55, zorder=3)
ax.axhline(0.401, color=GREEN, ls="--", lw=1, alpha=0.5)
ax.set_xticks(xs)
ax.set_xticklabels([m[0] for m in models], fontsize=9.5)
ax.set_ylabel("event_type accuracy")
ax.set_ylim(0, 0.52)
ax.set_title("Single-step next-event accuracy — GoKer held-out (798 examples)", fontsize=11)
ax.grid(axis="y", alpha=0.3, zorder=0)
for bar, (_, acc, _, _) in zip(bars, models):
    ax.text(bar.get_x() + bar.get_width()/2, acc + 0.007,
            f"{acc:.1%}", ha="center", va="bottom", fontsize=9, fontweight="bold")
plt.tight_layout()
plt.savefig(f"{OUT}/fig1_accuracy_comparison.pdf", bbox_inches="tight")
plt.savefig(f"{OUT}/fig1_accuracy_comparison.png", dpi=150, bbox_inches="tight")
print("Saved fig1_accuracy_comparison")

# ─────────────────────────────────────────────────────────────────────────────
# Fig 2 — Per-event-type accuracy breakdown (Phase 16 traj model)
# ─────────────────────────────────────────────────────────────────────────────
confusion = r_acc["confusion"]
event_order = ["GoBlock", "GoCreate", "GoStart", "GoUnblock", "GoSched", "GoEnd"]
gt_totals  = {et: sum(confusion.get(et, {}).values()) for et in event_order}
gt_correct = {et: confusion.get(et, {}).get(et, 0)    for et in event_order}
pct_acc    = [gt_correct[et]/gt_totals[et] if gt_totals[et] else 0 for et in event_order]
counts     = [gt_totals[et] for et in event_order]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

# Left: per-event accuracy
colors = [GREEN if p > 0 else RED for p in pct_acc]
bars = ax1.barh(event_order, pct_acc, color=colors, height=0.55, zorder=3)
ax1.set_xlim(0, 1)
ax1.set_xlabel("Accuracy")
ax1.set_title("Per-event-type accuracy\n(Phase 16 traj model, n=798)")
ax1.grid(axis="x", alpha=0.3, zorder=0)
for bar, p, c in zip(bars, pct_acc, counts):
    label = f"{p:.0%} (n={c})" if p > 0 else f"0% (n={c})"
    ax1.text(max(p + 0.02, 0.03), bar.get_y() + bar.get_height()/2,
             label, va="center", fontsize=9)

# Right: confusion matrix heatmap
et_all = sorted(confusion.keys())
matrix = np.zeros((len(et_all), len(et_all)))
for i, gt in enumerate(et_all):
    row = confusion.get(gt, {})
    total = sum(row.values()) or 1
    for j, pred in enumerate(et_all):
        matrix[i][j] = row.get(pred, 0) / total

mask_label = [[f"{matrix[i][j]:.0%}" if matrix[i][j] > 0.01 else "" for j in range(len(et_all))] for i in range(len(et_all))]
sns.heatmap(matrix, ax=ax2, annot=mask_label, fmt="s",
            xticklabels=et_all, yticklabels=et_all,
            cmap="Blues", vmin=0, vmax=1,
            linewidths=0.5, linecolor="white")
ax2.set_xlabel("Predicted")
ax2.set_ylabel("Ground truth")
ax2.set_title("Confusion matrix (row-normalised)\nPhase 16 traj model")
ax2.tick_params(axis="x", rotation=30)
ax2.tick_params(axis="y", rotation=0)

plt.tight_layout()
plt.savefig(f"{OUT}/fig2_per_event_accuracy.pdf", bbox_inches="tight")
plt.savefig(f"{OUT}/fig2_per_event_accuracy.png", dpi=150, bbox_inches="tight")
print("Saved fig2_per_event_accuracy")

# ─────────────────────────────────────────────────────────────────────────────
# Fig 3 — Rollout survival steps distribution
# ─────────────────────────────────────────────────────────────────────────────
survival_leak = []
survival_race = []
for prog in r_roll["results"]:
    s = prog["mean_survival_steps"]
    if prog["outcome"] == "leak":
        survival_leak.append(s)
    else:
        survival_race.append(s)

fig, ax = plt.subplots(figsize=(7, 4))
bins = np.arange(0, 16.5, 1)
ax.hist(survival_leak, bins=bins, alpha=0.65, color=RED,   label=f"Leak programs (n={len(survival_leak)}, mean={statistics.mean(survival_leak):.1f})", density=False)
ax.hist(survival_race, bins=bins, alpha=0.65, color=BLUE,  label=f"Race programs (n={len(survival_race)}, mean={statistics.mean(survival_race):.1f})", density=False)
ax.axvline(statistics.mean(survival_leak + survival_race), color="black", ls="--", lw=1.5, label=f"Overall mean = {statistics.mean(survival_leak+survival_race):.2f}")
ax.set_xlabel("Mean survival steps (max=15)")
ax.set_ylabel("Number of programs")
ax.set_title("Rollout coherence — Phase 16 traj model\n(54 GoKer programs, 3 samples each)")
ax.legend(fontsize=9)
ax.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig(f"{OUT}/fig3_rollout_survival.pdf", bbox_inches="tight")
plt.savefig(f"{OUT}/fig3_rollout_survival.png", dpi=150, bbox_inches="tight")
print("Saved fig3_rollout_survival")

# ─────────────────────────────────────────────────────────────────────────────
# Fig 4 — ECE calibration comparison (Phases 4, 7, 14)
# ─────────────────────────────────────────────────────────────────────────────
ece_data = [
    ("Point-prediction\nbaseline\n(Phase 4)", 0.2050, GRAY),
    ("Distribution\nno thinking\n(Phase 7)", 0.1833, ORANGE),
    ("Distribution\nthinking=1024\n(Phase 7)", 0.1689, BLUE),
    ("KL-trained model\n(Phase 14)", 0.169, GREEN),
]

fig, ax = plt.subplots(figsize=(7, 4))
xs = range(len(ece_data))
bars = ax.bar(xs, [d[1] for d in ece_data], color=[d[2] for d in ece_data], width=0.5, zorder=3)
ax.set_xticks(xs)
ax.set_xticklabels([d[0] for d in ece_data], fontsize=9)
ax.set_ylabel("Expected Calibration Error (lower = better)")
ax.set_title("Calibration improvement — distribution learning vs point-prediction baseline")
ax.grid(axis="y", alpha=0.3, zorder=0)
ax.set_ylim(0, 0.26)
for bar, (_, ece, _) in zip(bars, ece_data):
    ax.text(bar.get_x() + bar.get_width()/2, ece + 0.004,
            f"{ece:.4f}", ha="center", va="bottom", fontsize=9, fontweight="bold")
plt.tight_layout()
plt.savefig(f"{OUT}/fig4_ece_calibration.pdf", bbox_inches="tight")
plt.savefig(f"{OUT}/fig4_ece_calibration.png", dpi=150, bbox_inches="tight")
print("Saved fig4_ece_calibration")

# ─────────────────────────────────────────────────────────────────────────────
# Fig 5 — Entropy vs nondeterminism (Phase 7/8)
# ─────────────────────────────────────────────────────────────────────────────
nd_levels  = ["none", "low", "medium", "high"]
model_h_nothink  = [0.000, 0.042, 0.686, 0.287]
model_h_thinking = [0.687, 0.399, 0.928, 1.029]
empirical_h      = [0.971, 0.903, 1.210, 1.396]

x = np.arange(len(nd_levels))
width = 0.27
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.bar(x - width, model_h_nothink,  width, label="Model (no thinking)",   color=GRAY,   alpha=0.85)
ax.bar(x,          model_h_thinking, width, label="Model (thinking=1024)", color=BLUE,   alpha=0.85)
ax.bar(x + width,  empirical_h,      width, label="Empirical (ground truth)", color=GREEN, alpha=0.85)
ax.set_xticks(x)
ax.set_xticklabels(nd_levels)
ax.set_xlabel("Nondeterminism level")
ax.set_ylabel("Entropy (bits)")
ax.set_title("Model entropy vs empirical entropy by nondeterminism level\n(Spearman ρ=0.412, p=0.007 with thinking=1024)")
ax.legend(fontsize=9)
ax.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig(f"{OUT}/fig5_entropy_nondeterminism.pdf", bbox_inches="tight")
plt.savefig(f"{OUT}/fig5_entropy_nondeterminism.png", dpi=150, bbox_inches="tight")
print("Saved fig5_entropy_nondeterminism")

# ─────────────────────────────────────────────────────────────────────────────
# Fig 6 — Coherence baseline vs traj (summary bar)
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(6, 3.5))
labels  = ["Single-step training\n(Phase 15 baseline)", "Trajectory training\n(Phase 16)"]
vals    = [1.0, 10.48]
colors_ = [GRAY, GREEN]
bars = ax.bar(labels, vals, color=colors_, width=0.4, zorder=3)
ax.set_ylabel("Mean survival steps (max=15)")
ax.set_title("Multi-step rollout coherence\n(54 GoKer programs, 15-step rollout)")
ax.set_ylim(0, 13)
ax.grid(axis="y", alpha=0.3, zorder=0)
for bar, v in zip(bars, vals):
    ax.text(bar.get_x() + bar.get_width()/2, v + 0.2,
            f"{v:.2f}", ha="center", va="bottom", fontsize=11, fontweight="bold")
ax.annotate("10× improvement", xy=(1, 10.48), xytext=(0.55, 11.2),
            arrowprops=dict(arrowstyle="->", color=GREEN), color=GREEN, fontsize=10)
plt.tight_layout()
plt.savefig(f"{OUT}/fig6_coherence_comparison.pdf", bbox_inches="tight")
plt.savefig(f"{OUT}/fig6_coherence_comparison.png", dpi=150, bbox_inches="tight")
print("Saved fig6_coherence_comparison")

# ─────────────────────────────────────────────────────────────────────────────
# Print summary table for LaTeX
# ─────────────────────────────────────────────────────────────────────────────
print()
print("=== LaTeX table: per-event accuracy (Phase 16) ===")
print(r"\begin{tabular}{lrrr}")
print(r"\toprule")
print(r"Event type & Count & Correct & Accuracy \\")
print(r"\midrule")
for et in event_order:
    tot = gt_totals[et]
    cor = gt_correct[et]
    pct = cor/tot if tot else 0
    flag = r" \textbf{(never predicted)}" if pct == 0 else ""
    print(fr"{et} & {tot} & {cor} & {pct:.0%}{flag} \\")
print(r"\midrule")
print(fr"Total & {sum(gt_totals.values())} & {sum(gt_correct.values())} & {sum(gt_correct.values())/sum(gt_totals.values()):.1%} \\")
print(r"\bottomrule")
print(r"\end{tabular}")

print()
print("=== STRUCTURAL CEILING ANALYSIS ===")
learnable_types = ["GoBlock", "GoCreate", "GoStart"]
learnable_total   = sum(gt_totals[et] for et in learnable_types)
learnable_correct = sum(gt_correct[et] for et in learnable_types)
unpredictable = sum(gt_totals[et] for et in ["GoEnd","GoSched","GoUnblock"])
print(f"Learnable events (GoBlock, GoCreate, GoStart): {learnable_correct}/{learnable_total} = {learnable_correct/learnable_total:.1%}")
print(f"Never-predicted events (GoEnd, GoSched, GoUnblock): {unpredictable}/{sum(gt_totals.values())} = {unpredictable/sum(gt_totals.values()):.1%} of val set")
print(f"Theoretical ceiling if unpredictable events were learned: {(sum(gt_correct.values())+unpredictable)/sum(gt_totals.values()):.1%}")
print(f"Theoretical upper bound (perfect on learnable, 0 on others): {learnable_total/sum(gt_totals.values()):.1%}")

print()
print(f"All figures saved to {OUT}/")
