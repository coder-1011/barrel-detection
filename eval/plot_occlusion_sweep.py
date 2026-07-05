#!/usr/bin/env python3
"""
Build the synthetic occlusion-sweep artifacts (the thesis's headline experiment).

Reads the per-method eval CSVs, filters to scenes named occl_a<arc>_s<seed>
(visible arc in degrees; occlusion = 1 - arc/360), aggregates across the seeds
per (method, arc) level, and writes:
  - researchwrite/presentation_assets/synth_occlusion_sweep.png   (3-panel line chart)
  - researchwrite/presentation_assets/synth_occlusion_sweep_table.csv (summary table)
and prints a markdown summary to stdout.

barrelnet is included deliberately even though it scores 0 across the sweep:
its checkpoint is trained for r=0.286 m drums and does not transfer to the
r=4.25 cm lab barrel — the domain-specificity finding is part of the story.
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
    ("barrelnet",       "BarrelNet (drum-trained)", "#8c564b"),
]

SCENE_RE = re.compile(r"^occl_a(\d+)_s(\d+)$")


def load_method(name):
    """returns dict[occlusion_pct] -> list of per-seed metric dicts"""
    path = os.path.join(MASTERS, "eval", f"{name}.csv")
    by_occ = defaultdict(list)
    if not os.path.isfile(path):
        return by_occ
    with open(path) as f:
        for row in csv.DictReader(f):
            m = SCENE_RE.match(row["scene"])
            if not m:
                continue
            occ = (1.0 - float(m.group(1)) / 360.0) * 100.0
            def fnum(k):
                v = row.get(k, "")
                return float(v) if v not in ("", None) else np.nan
            by_occ[occ].append(dict(
                f1=fnum("f1"), recall=fnum("recall"), precision=fnum("precision"),
                tp=fnum("tp"), fp=fnum("fp"), fn=fnum("fn"),
                rrmse_cm=fnum("radius_rmse_m") * 100.0,
                axis_deg=fnum("axis_angle_mean_deg"),
            ))
    return by_occ


def agg(by_occ):
    """occlusion-sorted arrays of means + std for each metric (NaN-aware)."""
    occs = sorted(by_occ)
    out = dict(occ=np.array(occs))
    for key in ("f1", "recall", "rrmse_cm", "axis_deg"):
        means, stds = [], []
        for n in occs:
            vals = np.array([r[key] for r in by_occ[n]], float)
            means.append(np.nanmean(vals) if np.any(~np.isnan(vals)) else np.nan)
            stds.append(np.nanstd(vals) if np.any(~np.isnan(vals)) else np.nan)
        out[key] = np.array(means)
        out[key + "_std"] = np.array(stds)
    det = []
    for n in occs:
        det.append(np.mean([r["tp"] for r in by_occ[n]]))
    out["detrate"] = np.array(det)
    return out


def main():
    data = {name: agg(load_method(name)) for name, _, _ in METHODS}
    have = [(n, l, c) for n, l, c in METHODS if len(data[n]["occ"])]

    plt.rcParams.update({"font.size": 15, "axes.titlesize": 18,
                         "axes.labelsize": 16, "legend.fontsize": 13,
                         "xtick.labelsize": 13, "ytick.labelsize": 13})
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.4))
    panels = [("rrmse_cm", "Radius error (cm)", "Radius RMSE vs occlusion"),
              ("axis_deg", "Axis error (deg)",  "Axis-angle error vs occlusion"),
              ("f1",       "F1 score",          "F1 vs occlusion")]
    for ax, (key, ylab, title) in zip(axes, panels):
        for name, label, color in have:
            d = data[name]
            ax.errorbar(d["occ"], d[key], yerr=d[key + "_std"],
                        label=label, color=color, marker="o", ms=6,
                        lw=2.6, capsize=3.0, elinewidth=1.2, alpha=0.9)
        ax.set_xlabel("Occlusion (% of circumference hidden)")
        ax.set_ylabel(ylab)
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
    axes[2].set_ylim(-0.05, 1.05)
    axes[2].legend(loc="lower left", framealpha=0.9)
    fig.suptitle("Synthetic single-barrel occlusion sweep  "
                 "(arc 360->60 deg, sigma=0.1 cm, r=4.25 cm; 3 seeds/level)",
                 fontsize=17, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    png = os.path.join(OUTDIR, "synth_occlusion_sweep.png")
    fig.savefig(png, dpi=150)
    plt.close(fig)
    print("wrote", png)

    table_csv = os.path.join(OUTDIR, "synth_occlusion_sweep_table.csv")
    fields = ["method", "occlusion_pct", "visible_arc_deg", "n_seeds", "detect_rate",
              "f1_mean", "recall_mean", "radius_rmse_cm_mean", "radius_rmse_cm_std",
              "axis_deg_mean", "axis_deg_std"]
    rows = []
    for name, label, _ in have:
        by = load_method(name)
        d = data[name]
        for i, n in enumerate(d["occ"]):
            rows.append(dict(
                method=name, occlusion_pct=f"{n:.1f}",
                visible_arc_deg=f"{360.0 * (1 - n / 100.0):.0f}",
                n_seeds=len(by[n]),
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

    reps = [0.0, 50.0, 75.0, 83.3]
    print("\n## Per-method metrics at representative occlusion levels\n")
    for key, lab in [("f1", "F1"), ("recall", "recall"),
                     ("rrmse_cm", "radius RMSE (cm)"), ("axis_deg", "axis err (deg)")]:
        print(f"\n### {lab}\n")
        hdr = "| method | " + " | ".join(f"occ={r:.0f}%" for r in reps) + " |"
        print(hdr)
        print("|" + "---|" * (len(reps) + 1))
        for name, label, _ in have:
            d = data[name]
            cells = []
            for r in reps:
                idx = np.where(np.isclose(d["occ"], r, atol=0.2))[0]
                cells.append(f"{d[key][idx[0]]:.3f}" if len(idx) else "-")
            print(f"| {label} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
