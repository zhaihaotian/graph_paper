#!/usr/bin/env python3
"""
plot_metrics.py — boxplots comparing AI vs human paper metrics.

Reads metrics.csv (output of compute_metrics.py), groups by `label` column,
and draws a grid of box+strip plots organized into thematic groups.

Usage:
    python3 plot_metrics.py metrics.csv [-o plots.png]
"""

import csv
import sys
import math
import argparse
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def mann_whitney_u(x, y):
    """Two-sided Mann-Whitney U with normal approximation. Returns p-value."""
    nx, ny = len(x), len(y)
    if nx == 0 or ny == 0: return 1.0
    combined = sorted([(v, 'x') for v in x] + [(v, 'y') for v in y])
    ranks = defaultdict(list); i = 0
    while i < len(combined):
        j = i
        while j < len(combined) and combined[j][0] == combined[i][0]: j += 1
        avg_rank = (i + j + 1) / 2
        for k in range(i, j): ranks[combined[k][1]].append(avg_rank)
        i = j
    Rx = sum(ranks['x']); U1 = Rx - nx*(nx+1)/2; U2 = nx*ny - U1
    U = min(U1, U2); mu = nx*ny/2
    sigma = math.sqrt(nx*ny*(nx+ny+1)/12)
    if sigma == 0: return 1.0
    z = (U - mu) / sigma
    return math.erfc(abs(z)/math.sqrt(2))


# Curated 6 core fingerprint metrics with presentation-friendly names.
GROUPS = [
    ("A. Argument Structure", [
        ("sum_node_degree",      "Total Argumentative Connectivity"),
        ("graph_longest_path",   "Argumentation Depth"),
    ]),
    ("B. Prior-Work Coverage", [
        ("pw_node_count",        "Prior-Work Claim Count"),
        ("pw_total_cites",       "Citation Count for Prior Work"),
    ]),
    ("C. Limitation & Method", [
        ("lim_scope_avg_cites",  "Limitation Grounding"),
        ("method_node_count",    "Method Node Count"),
    ]),
]


def load(csv_path):
    by_label = defaultdict(lambda: defaultdict(list))
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            label = row["label"]
            for col in row:
                v = row.get(col, "")
                try:
                    by_label[label][col].append(float(v))
                except (ValueError, TypeError):
                    pass
    return by_label


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("-o", "--out", default="metrics_plots.png")
    args = ap.parse_args()

    by_label = load(args.csv)
    labels = sorted(by_label.keys())

    n_groups = len(GROUPS)
    n_cols = max(len(metrics) for _, metrics in GROUPS)
    fig, axes = plt.subplots(n_groups, n_cols, figsize=(3.4 * n_cols, 2.8 * n_groups))

    palette = {"ai": "#c4502e", "human": "#3a8a7e"}
    rng = np.random.default_rng(7)

    for gi, (group_name, metrics) in enumerate(GROUPS):
        for mi, (col, title) in enumerate(metrics):
            ax = axes[gi, mi]
            data = [by_label[lbl].get(col, []) for lbl in labels]

            bp = ax.boxplot(data, positions=range(len(labels)),
                            widths=0.55, patch_artist=True, showfliers=False,
                            medianprops=dict(color="#222", linewidth=1.4),
                            boxprops=dict(linewidth=1, edgecolor="#222"))
            for patch, lbl in zip(bp["boxes"], labels):
                patch.set_facecolor(palette.get(lbl, "#888"))
                patch.set_alpha(0.45)

            for j, (lbl, vals) in enumerate(zip(labels, data)):
                xs = rng.normal(j, 0.07, size=len(vals))
                ax.scatter(xs, vals, color=palette.get(lbl, "#888"),
                           edgecolor="#222", linewidth=0.4, s=20, alpha=0.85, zorder=3)

            for j, (lbl, vals) in enumerate(zip(labels, data)):
                if vals:
                    m = np.mean(vals)
                    ax.text(j, ax.get_ylim()[1], f"μ={m:.2f}", ha="center", va="top",
                            fontsize=8, fontweight="bold", color=palette.get(lbl, "#888"))

            # p-value + ratio annotation in the upper-right corner
            if len(data) == 2 and data[0] and data[1]:
                a_vals, h_vals = data[0], data[1]
                p = mann_whitney_u(a_vals, h_vals)
                if p < 1e-12: p_str = "p<1e-12"
                elif p < 1e-3: p_str = f"p={p:.0e}"
                else: p_str = f"p={p:.3f}"
                sig = "***" if p<0.001 else ("**" if p<0.01 else ("*" if p<0.05 else "ns"))
                ratio = np.mean(h_vals) / np.mean(a_vals) if np.mean(a_vals) else 0
                annot = f"{ratio:.2f}×  {p_str} {sig}"
                ax.text(0.98, 0.02, annot, transform=ax.transAxes,
                        ha="right", va="bottom", fontsize=8.5,
                        fontweight="bold", color="#222",
                        bbox=dict(boxstyle="round,pad=0.25", facecolor="#fff5d8",
                                  edgecolor="#bba", linewidth=0.6, alpha=0.92))

            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, fontsize=9)
            ax.set_title(title, fontsize=9.5)
            ax.grid(True, axis="y", linestyle=":", alpha=0.4)

        # Hide unused cells in this row
        for k in range(len(metrics), n_cols):
            axes[gi, k].set_visible(False)

        # Group label on the leftmost cell as ylabel
        axes[gi, 0].set_ylabel(group_name, fontsize=11, fontweight="bold",
                                rotation=90, labelpad=12)

    n_each = max(len(by_label[lbl]["pw_node_count"]) for lbl in labels)
    fig.suptitle(f"Argument-graph fingerprint: {labels[0]} vs {labels[1]}  (n={n_each} each, "
                 f"Mann-Whitney U two-tailed)",
                 fontsize=14, fontweight="bold", y=0.998)
    plt.tight_layout(rect=[0, 0, 1, 0.985])
    plt.savefig(args.out, dpi=140, bbox_inches="tight")
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
