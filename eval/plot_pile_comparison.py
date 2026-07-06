#!/usr/bin/env python3
"""
Top-down comparison figure: all 5 methods' detections on the station1_pit_barrels
drum pile vs the 21-drum (partial) ground truth.

One panel per method: cloud in gray (downsampled, cropped to the GT bbox + margin),
GT drums as green circles (r=0.286 m at each GT center), method detections as red
circles at their fitted radius. Panel title carries TP/recall from eval/<method>.csv.

  .venv/bin/python eval/plot_pile_comparison.py
  -> researchwrite/presentation_assets/station1_pile_methods.png
"""
import csv
import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import open3d as o3d

HERE = os.path.dirname(os.path.abspath(__file__))
MASTERS = os.path.abspath(os.path.join(HERE, ".."))
SCENE = "station1_pit_barrels"
OUTDIR = os.path.join(MASTERS, "researchwrite", "presentation_assets")

METHODS = [
    ("3dtk_hough",       "3DTK Hough (baseline)"),
    ("ransac_cylinder",  "RANSAC fit"),
    ("ls_cylinder",      "Least-squares fit"),
    ("efficient_ransac", "Efficient RANSAC"),
    ("barrelnet",        "BarrelNet (learned)"),
]


def csv_row(method):
    path = os.path.join(MASTERS, "eval", f"{method}.csv")
    with open(path) as f:
        for row in csv.DictReader(f):
            if row["scene"] == SCENE:
                return row
    return None


def main():
    gt = json.load(open(os.path.join(MASTERS, "data", "real", SCENE, "gt.json")))["barrels"]
    pts = np.asarray(o3d.io.read_point_cloud(
        os.path.join(MASTERS, "data", "real", SCENE, "scan000.pcd")).points)

    gtc = np.array([b["center"] for b in gt])
    lo, hi = gtc.min(0) - 1.0, gtc.max(0) + 1.0
    m = np.all((pts[:, :2] >= lo[:2]) & (pts[:, :2] <= hi[:2]), axis=1)
    crop = pts[m]
    rng = np.random.default_rng(0)
    crop = crop[rng.choice(len(crop), min(30000, len(crop)), replace=False)]

    plt.rcParams.update({"font.size": 13, "axes.titlesize": 15})
    fig, axes = plt.subplots(1, len(METHODS), figsize=(4.2 * len(METHODS), 5.2),
                             sharex=True, sharey=True)
    th = np.linspace(0, 2 * np.pi, 60)
    for ax, (method, label) in zip(axes, METHODS):
        ax.scatter(crop[:, 0], crop[:, 1], s=1, c=crop[:, 2], cmap="Greys", alpha=0.5)
        for b in gt:
            c, R = b["center"], b["radius_m"]
            ax.plot(c[0] + R * np.cos(th), c[1] + R * np.sin(th),
                    c="tab:green", lw=1.8)
        pf = os.path.join(MASTERS, "methods", method, "results", SCENE,
                          "predictions.json")
        dets = json.load(open(pf))["detections"] if os.path.isfile(pf) else []
        for d in dets:
            c, R = d["center"], d["radius_m"]
            ax.plot(c[0] + R * np.cos(th), c[1] + R * np.sin(th),
                    c="tab:red", lw=1.4, alpha=0.85)
        row = csv_row(method)
        sub = (f"TP {row['tp']}/21  recall {float(row['recall']):.2f}  "
               f"({len(dets)} dets)") if row else f"{len(dets)} dets"
        ax.set_title(f"{label}\n{sub}")
        ax.set_aspect("equal")
        ax.set_xlabel("X (m)")
    axes[0].set_ylabel("Y (m)")
    fig.suptitle("station1_pit_barrels drum pile, top-down: GT (green, 21 verified drums; "
                 "GT is ~30% of the pile) vs detections (red)",
                 fontsize=16, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    out = os.path.join(OUTDIR, "station1_pile_methods.png")
    fig.savefig(out, dpi=140)
    print("wrote", out)


if __name__ == "__main__":
    main()
