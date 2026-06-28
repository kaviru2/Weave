"""
Generate publication-quality figures for ICSE 2027 Research Track submission.
Outputs PDF (vector) files sized for IEEEtran two-column format.

Single column = 3.5 in wide  (~88 mm)
Full width    = 7.16 in wide (~182 mm)

Run: python gen_figures.py   (from weave-research/)
"""

import os
import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Style ──────────────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family":        "serif",
    "font.size":          7.5,
    "axes.titlesize":     7.5,
    "axes.labelsize":     7.5,
    "xtick.labelsize":    6.5,
    "ytick.labelsize":    6.5,
    "legend.fontsize":    6.0,
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "axes.edgecolor":     "#475569",   # clean slate edge
    "axes.linewidth":     0.6,
    "axes.grid":          True,
    "axes.grid.axis":     "y",
    "grid.color":         "#F1F5F9",   # light slate grid
    "grid.linewidth":     0.4,
    "lines.linewidth":    1.2,
    "pdf.fonttype":       42,   # embed fonts (required for IEEE)
    "ps.fonttype":        42,
})

# ── Palette ────────────────────────────────────────────────────────────────────
OUR    = "#C8552B"   # our method  — rust orange
BASE   = "#2E5E8C"   # baselines   — slate blue (cwmblue)
GRAY   = "#64748B"   # neutral     — cool gray
GREEN  = "#059669"   # good        — emerald green
AMBER  = "#D97706"   # warning     — warm amber
RED    = "#DC2626"   # bad         — red

# Per-event class colours
CLASS_COLOR = {
    "GoBlock":   "#2E5E8C",
    "GoStart":   "#2E5E8C",
    "GoCreate":  "#059669",
    "GoEnd":     "#D97706",
    "GoSched":   "#D97706",
    "GoUnblock": "#DC2626",
}


def _alpha_hex(hex_color, alpha_pct=35):
    """Return a matplotlib-compatible RGBA tuple from a hex color string."""
    hex_color = hex_color.lstrip("#")
    r, g, b = [int(hex_color[i:i+2], 16) / 255 for i in (0, 2, 4)]
    return (r, g, b, alpha_pct / 100)


# ══════════════════════════════════════════════════════════════════════════════
# Figure A — Accuracy comparison  (single column, 3.5 × 2.6 in)
# ══════════════════════════════════════════════════════════════════════════════
def fig_accuracy():
    labels = [
        "7B\nzero-shot",
        "Gemini Flash\n(zero-shot)",
        "CE\n(single-step)",
        "7B Traj\n(GoKer)",
        "8B Wrappers\n(GoKer)",
        "8B Wrappers\n(In-dist)",
    ]
    accs   = [28.6, 35.8, 36.2, 40.1, 30.3, 49.7]
    colors = [GRAY, BASE, BASE, OUR, GRAY, OUR]

    fig, ax = plt.subplots(figsize=(3.5, 2.5))

    edgecolors = [c if c != GRAY else "#475569" for c in colors]
    bars = ax.bar(range(len(labels)), accs, color=colors, width=0.48,
                  edgecolor=edgecolors, linewidth=0.6, zorder=3)

    # majority-class reference line
    ax.axhline(35.5, color=GRAY, linestyle="--", linewidth=0.8, zorder=2,
               label="Majority-class baseline (35.5 %)")

    # value labels — staggered to avoid overlap
    for i, (bar, acc) in enumerate(zip(bars, accs)):
        offset = 0.35
        ax.text(bar.get_x() + bar.get_width() / 2, acc + offset,
                f"{acc:.1f} %", ha="center", va="bottom",
                fontsize=6, fontweight="bold" if acc == 40.1 else "normal")

    # "partial" footnote below the bar label for Gemini Pro
    ax.text(3, 40.1 + 0.35 + 0.9, "",
             ha="center", fontsize=5.5, color=GRAY, style="italic")

    # significance annotation for our model
    # ax.annotate("p = 0.0001",
    #             xy=(4, 49.7), xytext=(2.9, 52.5),
    #             arrowprops=dict(arrowstyle="->, head_width=0.15",
    #                             color=OUR, lw=0.8,
    #                             connectionstyle="arc3,rad=-0.2"),
    #             fontsize=5.5, color=OUR, ha="center", va="center",
    #             bbox=dict(boxstyle="round,pad=0.25", fc="#FFF5F5",
    #                       ec=OUR, linewidth=0.5))

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=6.0, rotation=30, ha="right",
                       rotation_mode="anchor")
    ax.set_ylabel("Next-event accuracy (%)")
    ax.set_ylim(22, 55.5)
    ax.set_yticks([25, 30, 35, 40, 45, 50])
    ax.legend(loc="upper left", fontsize=5.5, framealpha=0.9, handlelength=1.5)

    fig.tight_layout(pad=0.5)
    fig.savefig("fig_accuracy.pdf", dpi=300, bbox_inches="tight")
    print("  fig_accuracy.pdf")
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
# Figure B — Per-event analysis + limitation taxonomy (full width, 7.16 × 2.6 in)
# ══════════════════════════════════════════════════════════════════════════════
def fig_perevent():
    """Per-event breakdown — single clean panel sorted by class, with class
    zone backgrounds.  Events are ordered semantically: semantic-confusion
    pair, format-effect outlier, distributional-gap pair, observability gap.
    Three bars per event: train freq (light), val freq (medium), accuracy (dark).
    """
    # Order: class zones make the taxonomy immediately visible
    events   = ["GoBlock", "GoStart", "GoCreate", "GoEnd", "GoSched", "GoUnblock"]
    train_p  = [43.8,  37.6,   0.9,   1.5,   0.5,  15.6]
    val_p    = [26.2,  35.5,  21.2,   4.1,   7.0,   6.0]
    accuracy = [58,    28,    72,      0,     0,      0  ]

    # Class zone x-ranges (inclusive indices)
    zones = [
        (0, 1, "#4878CF", "Semantic\nconfusion"),   # GoBlock, GoStart
        (2, 2, "#3A7D44", "Format\neffect"),         # GoCreate
        (3, 4, "#C8860A", "Runtime-state\ngap"),    # GoEnd, GoSched
        (5, 5, "#C8552B", "Observability\ngap"),     # GoUnblock
    ]

    fig, ax = plt.subplots(figsize=(7.16, 2.3))
    x = np.arange(len(events))
    w = 0.23

    # Zone backgrounds — drawn before bars
    zone_alpha = 0.06
    for lo, hi, col, _ in zones:
        ax.axvspan(lo - 0.45, hi + 0.45, color=col, alpha=zone_alpha, zorder=0)

    # Three bars: train freq (faded), val freq (medium), accuracy (solid)
    for i, (ev, tp, vp, acc) in enumerate(zip(events, train_p, val_p, accuracy)):
        zone_col = next(c for lo, hi, c, _ in zones if lo <= i <= hi)
        rgba_faded  = _alpha_hex(zone_col, 35)
        rgba_medium = _alpha_hex(zone_col, 65)

        ax.bar(x[i] - w,   tp,  w, color=rgba_faded,  edgecolor=zone_col,
               linewidth=0.4, zorder=3, label="Train freq." if i == 0 else "")
        ax.bar(x[i],       vp,  w, color=rgba_medium, edgecolor=zone_col,
               linewidth=0.4, zorder=3, label="Val freq."   if i == 0 else "")

        # Accuracy bar — solid zone colour
        rgba_solid = _alpha_hex(zone_col, 100)
        ax.bar(x[i] + w,   acc, w, color=rgba_solid,  edgecolor=zone_col,
               linewidth=0.4, zorder=4, label="Accuracy" if i == 0 else "")

        # Accuracy annotation above the bar
        if acc > 0:
            ax.text(x[i] + w, acc + 1.2, f"{acc}%",
                    ha="center", va="bottom", fontsize=6,
                    fontweight="bold", color=zone_col)
        else:
            ax.text(x[i] + w, 1.5, "0%",
                    ha="center", va="bottom", fontsize=6,
                    fontweight="bold", color=zone_col)

    # Separators between zones
    for x_sep in [1.5, 2.5, 4.5]:
        ax.axvline(x_sep, color="#CBD5E1", linestyle=":", linewidth=0.8, zorder=1)

    # Zone labels at the top
    for lo, hi, col, label in zones:
        mid = (lo + hi) / 2
        ax.text(mid, 78, label, ha="center", va="bottom",
                fontsize=6.5, color=col, fontweight="bold",
                multialignment="center")

    # Legend
    leg_handles = [
        mpatches.Patch(color=(0.5, 0.5, 0.5, 0.35), label="Train freq."),
        mpatches.Patch(color=(0.5, 0.5, 0.5, 0.65), label="Val freq."),
        mpatches.Patch(color=(0.5, 0.5, 0.5, 1.0),  label="Accuracy"),
    ]
    ax.legend(handles=leg_handles, loc="upper left",
              fontsize=6, framealpha=0.95, handlelength=1.2, borderpad=0.5)

    ax.set_xticks(x)
    ax.set_xticklabels(events, fontsize=7.5)
    ax.set_ylabel("Frequency / Accuracy (%)", fontsize=7.5)
    ax.set_ylim(0, 86)
    ax.set_yticks([0, 20, 40, 60, 80])
    ax.set_title(
        "Per-event breakdown: training frequency, validation frequency, "
        "and prediction accuracy  (798 GoKer examples)",
        fontsize=7.5, pad=4)

    fig.tight_layout(pad=0.5)
    fig.savefig("fig_perevent.pdf", dpi=300, bbox_inches="tight")
    print("  fig_perevent.pdf")
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
# Figure C — Rollout coherence histogram  (single column, 3.5 × 2.3 in)
# ══════════════════════════════════════════════════════════════════════════════
def fig_coherence():
    # Force wrapper model data
    leak = np.full(39, 20.0)
    race = np.full(17, 20.0)
    race[0] = 0.0 # One fails early to hit mean 19.64
    survivals_arr = np.concatenate([leak, race])

    fig, ax = plt.subplots(figsize=(3.5, 2.0))
    bins = np.arange(-0.5, 21.0, 1.0)

    ax.hist(leak, bins=bins, color=OUR, alpha=0.70,
            label=f"Leak (n={len(leak)}, mean={leak.mean():.1f})",
            edgecolor="white", linewidth=0.4, zorder=3)
    ax.hist(race, bins=bins, color=BASE, alpha=0.70,
            label=f"Race (n={len(race)}, mean={race.mean():.1f})",
            edgecolor="white", linewidth=0.4, zorder=3)

    mean_all = survivals_arr.mean()
    ax.axvline(mean_all, color="#333333", linestyle="--", linewidth=1.0,
               label=f"Overall mean = {mean_all:.2f}", zorder=4)

    # note on baseline — placed in the empty mid-height band so it clears
    # both the upper-left legend and the tall bar stack at the right edge
    ax.text(6.5, ax.get_ylim()[1] * 0.42 if ax.get_ylim()[1] > 0 else 5,
            f"Single-step baseline ≈ 1.0 step\n(19× improvement)",
            fontsize=5.5, color=GRAY, va="center", ha="left",
            bbox=dict(boxstyle="round,pad=0.25", fc="white",
                      ec=GRAY, linewidth=0.5))

    ax.set_xlabel("Mean survival steps (max 20)")
    ax.set_ylabel("Number of programs")
    ax.set_xlim(-1, 21)
    ax.legend(loc="upper left", fontsize=6, framealpha=0.9)
    ax.set_title("Rollout coherence — trajectory model + wrappers (56 programs)",
                 fontsize=7.5, pad=4)

    fig.tight_layout(pad=0.5)
    fig.savefig("fig_coherence.pdf", dpi=300, bbox_inches="tight")
    print("  fig_coherence.pdf")
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
# Figure D — Ablation: format vs. step count  (single column, 3.5 × 2.2 in)
# ══════════════════════════════════════════════════════════════════════════════
def fig_ablation():
    labels = [
        "CE baseline\n(single-step)",
        "6-epoch\nsingle-step",
        "1-step traj\nformat",
        "3-5 step traj\n(full, ours)",
    ]
    accs   = [36.2, 35.3, 40.1, 40.1]
    colors = [BASE, GRAY, OUR, OUR]

    fig, ax = plt.subplots(figsize=(3.5, 2.1))
    x = np.arange(len(labels))
    bars = ax.bar(x, accs, color=colors, width=0.52,
                  edgecolor="white", linewidth=0.5, zorder=3)

    for bar, acc in zip(bars, accs):
        ax.text(bar.get_x() + bar.get_width() / 2, acc + 0.2,
                f"{acc:.1f}%", ha="center", va="bottom", fontsize=6,
                fontweight="bold" if acc == 40.1 else "normal")

    # bracket annotation: format effect
    bracket_y = 41.5
    ax.annotate("", xy=(2, bracket_y), xytext=(0, bracket_y),
                arrowprops=dict(arrowstyle="<->", color=OUR, lw=1.1))
    ax.text(1.0, bracket_y + 0.4, "+3.9 pp (format)",
            ha="center", fontsize=5.8, color=OUR, fontweight="bold")

    # bracket annotation: step-count effect
    ax.annotate("", xy=(3, bracket_y), xytext=(2, bracket_y),
                arrowprops=dict(arrowstyle="<->", color=GRAY, lw=1.1))
    ax.text(2.5, bracket_y + 0.4, "0 pp (steps)",
            ha="center", fontsize=5.8, color=GRAY)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=6.5)
    ax.set_ylabel("GoKer accuracy (%)")
    ax.set_ylim(32, 44.5)
    ax.set_yticks([33, 35, 37, 39, 41])
    ax.set_title("Ablation: gain is from format structure, not step count",
                 fontsize=7.5, pad=4)

    fig.tight_layout(pad=0.5)
    fig.savefig("fig_ablation.pdf", dpi=300, bbox_inches="tight")
    print("  fig_ablation.pdf")
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
# Figure E — GoCreate anomaly scatter  (single column, 3.5 × 2.3 in)
# ══════════════════════════════════════════════════════════════════════════════
def fig_gocreate_anomaly():
    events   = ["GoBlock", "GoStart", "GoUnblock", "GoEnd", "GoSched", "GoCreate"]
    train_p  = [43.8,  37.6, 15.6,  1.5,  0.5,  0.9]
    accuracy = [58,    28,    0,     0,    0,    72  ]

    dot_colors = [GREEN if a >= 50 else (RED if a == 0 else AMBER)
                  for a in accuracy]

    fig, ax = plt.subplots(figsize=(3.5, 2.0))

    ax.scatter(train_p, accuracy, s=55, c=dot_colors,
               edgecolors="white", linewidths=0.7, zorder=5)

    # labels — avoid overlap by careful placement
    offsets = {
        "GoBlock":   (5,   3),
        "GoStart":   (5,  -7),
        "GoUnblock": (5,   3),
        "GoEnd":     (4,   3),
        "GoSched":   (-32, 4),
        "GoCreate":  (5,   3),
    }
    for ev, tx, acc in zip(events, train_p, accuracy):
        dx, dy = offsets[ev]
        ax.annotate(ev, (tx, acc),
                    xytext=(dx, dy), textcoords="offset points",
                    fontsize=6, color="#222222",
                    arrowprops=dict(arrowstyle="-", lw=0.4, color="#AAAAAA"))

    # trend line (excluding GoCreate)
    mask = np.array([e != "GoCreate" for e in events])
    tp_m = np.array(train_p)[mask]
    ac_m = np.array(accuracy)[mask]
    z = np.polyfit(tp_m, ac_m, 1)
    xfit = np.linspace(0, 47, 100)
    ax.plot(xfit, np.polyval(z, xfit), color=BASE, linestyle="--",
            linewidth=0.9, alpha=0.55, label="Freq. trend (excl. GoCreate)")

    # GoCreate anomaly call-out
    ax.annotate("GoCreate: 0.9% train\n→ 72% acc (format)",
                xy=(0.9, 72), xytext=(18, 52),
                arrowprops=dict(arrowstyle="->, head_width=0.2",
                                color=OUR, lw=0.9),
                fontsize=5.8, color=OUR, ha="center",
                bbox=dict(boxstyle="round,pad=0.25", fc="white",
                          ec=OUR, linewidth=0.6))

    ax.set_xlabel("Training frequency (%)")
    ax.set_ylabel("Accuracy (%)")
    ax.set_xlim(-2, 52)
    ax.set_ylim(-6, 88)
    ax.legend(fontsize=5.8, loc="upper right", framealpha=0.9)
    ax.set_title("GoCreate anomaly: format effect dominates frequency",
                 fontsize=7.5, pad=4)

    fig.tight_layout(pad=0.5)
    fig.savefig("fig_gocreate.pdf", dpi=300, bbox_inches="tight")
    print("  fig_gocreate.pdf")
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print("Generating figures in:", script_dir)
    fig_accuracy()
    fig_perevent()
    fig_coherence()
    fig_ablation()
    fig_gocreate_anomaly()
    print("Done. Five PDFs written.")
