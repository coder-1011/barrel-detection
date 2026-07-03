#!/usr/bin/env python3
"""
Build the synthetic noise-sweep slide artifacts.

Reads the 4 per-method eval CSVs, filters to scenes named sweep_n<noise>_s<seed>,
aggregates across the 3 seeds per (method, noise) level, and writes:
  - researchwrite/presentation_assets/synth_noise_sweep.png   (3-panel line chart)
  - researchwrite/presentation_assets/synth_noise_sweep_table.csv (summary table)
and prints a markdown summary to stdout.
"""
import os, re, csv
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
MASTERS = os.path.abspath(os.path.join(HERE, ".."))
OUTDIR = os.path.join(MASTERS, "researchwrite", "presentation_assets")
os.makedirs(OUTDIR, exist_ok=True)

METHODS = [
    ("3dtk_hough",      "3DTK Hough",       "#1f77b4"),
    ("ransac_cylinder", "RANSAC fit",       "#d62728"),
    ("ls_cylinder",     "Least-squares",    "#2ca02c"),
    ("efficient_ransac","Efficient RANSAC", "#9467bd"),
]

SCENE_RE = re.compile(r"^sweep_n(\d+\.\d+)_s(\d+)$")


def load_method(name):
    """returns dict[noise] -> list of per-seed metric dicts"""
    path = os.path.join(MASTERS, "eval", f"{name}.csv")
    by_noise = defaultdict(list)
    with open(path) as f:
        for row in csv.DictReader(f):
            m = SCENE_RE.match(row["scene"])
            if not m:
                continue
            noise = float(m.group(1))
            def fnum(k):
                v = row.get(k, "")
                return float(v) if v not in ("", None) else np.nan
            by_noise[noise].append(dict(
                f1=fnum("f1"), recall=fnum("recall"), precision=fnum("precision"),
                tp=fnum("tp"), fp=fnum("fp"), fn=fnum("fn"),
                rrmse_cm=fnum("radius_rmse_m") * 100.0,
                axis_deg=fnum("axis_angle_mean_deg"),
            ))
    return by_noise


def agg(by_noise):
    """noise-sorted arrays of means + std for each metric (NaN-aware)."""
    noises = sorted(by_noise)
    out = dict(noise=np.array(noises))
    for key in ("f1", "recall", "rrmse_cm", "axis_deg"):
        means, stds = [], []
        for n in noises:
            vals = np.array([r[key] for r in by_noise[n]], float)
            means.append(np.nanmean(vals) if np.any(~np.isnan(vals)) else np.nan)
            stds.append(np.nanstd(vals) if np.any(~np.isnan(vals)) else np.nan)
        out[key] = np.array(means)
        out[key + "_std"] = np.array(stds)
    # detection rate = mean tp (single-barrel scenes, tp in {0,1})
    det = []
    for n in noises:
        det.append(np.mean([r["tp"] for r in by_noise[n]]))
    out["detrate"] = np.array(det)
    return out


def main():
    data = {name: agg(load_method(name)) for name, _, _ in METHODS}

    # ---- figure: 3 panels ----
    # big fonts: the chart must stay readable from the back row of a talk
    plt.rcParams.update({"font.size": 15, "axes.titlesize": 18,
                         "axes.labelsize": 16, "legend.fontsize": 14,
                         "xtick.labelsize": 13, "ytick.labelsize": 13})
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.4))
    panels = [("rrmse_cm", "Radius error (cm)", "Radius RMSE vs noise"),
              ("axis_deg", "Axis error (deg)",  "Axis-angle error vs noise"),
              ("f1",       "F1 score",          "F1 vs noise")]
    for ax, (key, ylab, title) in zip(axes, panels):
        for name, label, color in METHODS:
            d = data[name]
            ax.errorbar(d["noise"], d[key], yerr=d[key + "_std"],
                        label=label, color=color, marker="o", ms=6,
                        lw=2.6, capsize=3.0, elinewidth=1.2, alpha=0.9)
        ax.set_xlabel("Gaussian noise sigma (cm)")
        ax.set_ylabel(ylab)
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
    axes[2].set_ylim(-0.05, 1.05)
    axes[0].legend(loc="upper left", framealpha=0.9)
    fig.suptitle("Synthetic single-barrel noise sweep  "
                 "(arc 120 deg, r=4.25 cm; 3 seeds/level, mean +/- std)",
                 fontsize=19, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    png = os.path.join(OUTDIR, "synth_noise_sweep.png")
    fig.savefig(png, dpi=150)
    plt.close(fig)
    print("wrote", png)

    # ---- summary table CSV ----
    table_csv = os.path.join(OUTDIR, "synth_noise_sweep_table.csv")
    fields = ["method", "noise_cm", "n_seeds", "detect_rate", "f1_mean",
              "recall_mean", "radius_rmse_cm_mean", "radius_rmse_cm_std",
              "axis_deg_mean", "axis_deg_std"]
    rows = []
    for name, label, _ in METHODS:
        by = load_method(name)
        d = data[name]
        for i, n in enumerate(d["noise"]):
            rows.append(dict(
                method=name, noise_cm=f"{n:.2f}", n_seeds=len(by[n]),
                detect_rate=f"{d['detrate'][i]:.3f}",
                f1_mean=f"{d['f1'][i]:.3f}",
                recall_mean=f"{d['recall'][i]:.3f}",
                radius_rmse_cm_mean=f"{d['rrmse_cm'][i]:.3f}",
                radius_rmse_cm_std=f"{d['rrmse_cm_std'][i]:.3f}",
                axis_deg_mean=f"{d['axis_deg'][i]:.3f}",
                axis_deg_std=f"{d['axis_deg_std'][i]:.3f}",
            ))
    with open(table_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print("wrote", table_csv)

    # ---- markdown summary at representative noise levels ----
    reps = [0.00, 0.20, 0.40, 0.60]
    print("\n## Per-method metrics at representative noise levels\n")
    for key, lab in [("f1", "F1"), ("recall", "recall"),
                     ("rrmse_cm", "radius RMSE (cm)"), ("axis_deg", "axis err (deg)")]:
        print(f"\n### {lab}\n")
        hdr = "| method | " + " | ".join(f"sigma={r:.2f}" for r in reps) + " |"
        print(hdr)
        print("|" + "---|" * (len(reps) + 1))
        for name, label, _ in METHODS:
            d = data[name]
            cells = []
            for r in reps:
                idx = np.where(np.isclose(d["noise"], r))[0]
                cells.append(f"{d[key][idx[0]]:.3f}" if len(idx) else "-")
            print(f"| {label} | " + " | ".join(cells) + " |")
    print("\n### detection rate (mean TP over 3 seeds, single barrel)\n")
    hdr = "| method | " + " | ".join(f"sigma={r:.2f}" for r in reps) + " |"
    print(hdr)
    print("|" + "---|" * (len(reps) + 1))
    for name, label, _ in METHODS:
        d = data[name]
        cells = []
        for r in reps:
            idx = np.where(np.isclose(d["noise"], r))[0]
            cells.append(f"{d['detrate'][idx[0]]:.2f}" if len(idx) else "-")
        print(f"| {label} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
