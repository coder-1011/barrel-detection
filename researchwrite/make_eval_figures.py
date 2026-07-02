#!/usr/bin/env python3
"""
Render the few NEW figures the evaluation deck needs that don't exist yet.

Reuses the project conventions (Agg backend, camera-optical projection,
viridis-by-depth scatter) from bilfinger_slides/make_figures.py.

Outputs -> researchwrite/presentation_assets/
  - pipeline_flow.png      (slide 4: capture/synth -> crop -> run_detection -> evaluate)
  - station1_pile_raw.png  (slide 1: the real partially-occluded 200 L drum pile, raw)

The synthetic noise-sweep chart (synth_noise_sweep.png) is produced separately
by the noise-sweep batch job, not here.
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

HERE = os.path.dirname(os.path.abspath(__file__))
MASTERS = os.path.abspath(os.path.join(HERE, ".."))
ASSETS = os.path.join(HERE, "presentation_assets")
os.makedirs(ASSETS, exist_ok=True)

DARK = "#1F2D3D"
ACCENT = "#0B5C8A"
GREEN = "#2E7D32"
AMBER = "#B76E00"
LIGHT = "#F2F5F8"


# ----------------------------------------------------------------- IO
def load_pcd(path):
    """Robust loader: Open3D handles both ascii and binary .pcd."""
    import open3d as o3d
    return np.asarray(o3d.io.read_point_cloud(path).points, float)


# ----------------------------------------------------------------- pipeline flow
def fig_pipeline_flow():
    boxes = [
        ("Data sources", "Asus Xtion depth\nSurvey LiDAR\nsynth_cylinder.py", ACCENT),
        ("Scene + GT", "scan000.pcd / .3d\ngt.json  (metres)", DARK),
        ("Proposer / crop", "find_barrel_clusters\n(geometric methods)", AMBER),
        ("Detection", "run_detection.sh\n4 methods", GREEN),
        ("Predictions", "predictions.json\n(shared schema, m)", DARK),
        ("Evaluation", "eval/evaluate.py\nmatch GT ↔ pred", ACCENT),
        ("Metrics", "P / R / F1\nradius RMSE\naxis-angle, runtime", GREEN),
    ]
    n = len(boxes)
    fig, ax = plt.subplots(figsize=(13.2, 3.2))
    ax.set_xlim(0, n)
    ax.set_ylim(0, 1)
    ax.axis("off")
    bw, bh = 0.86, 0.62
    for i, (head, body, col) in enumerate(boxes):
        x = i + 0.5
        box = FancyBboxPatch((x - bw / 2, 0.5 - bh / 2), bw, bh,
                             boxstyle="round,pad=0.02,rounding_size=0.06",
                             linewidth=1.6, edgecolor=col, facecolor=LIGHT)
        ax.add_patch(box)
        ax.text(x, 0.5 + 0.17, head, ha="center", va="center",
                fontsize=11.5, fontweight="bold", color=col)
        ax.text(x, 0.5 - 0.08, body, ha="center", va="center",
                fontsize=8.8, color=DARK)
        if i < n - 1:
            ax.add_patch(FancyArrowPatch((x + bw / 2, 0.5),
                                         (x + 1 - bw / 2, 0.5),
                                         arrowstyle="-|>", mutation_scale=14,
                                         linewidth=1.4, color="#777777"))
    ax.set_title("Method-agnostic evaluation pipeline — every method reads the "
                 "same data and emits the same schema",
                 fontsize=12.5, fontweight="bold", color=DARK, pad=10)
    fig.tight_layout()
    out = os.path.join(ASSETS, "pipeline_flow.png")
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


# ----------------------------------------------------------------- raw drum pile
def fig_station1_pile_raw():
    pcd = os.path.join(MASTERS, "data", "real", "station1_pit_barrels",
                       "scan000.pcd")
    pts = load_pcd(pcd)
    rng = np.random.default_rng(0)
    if pts.shape[0] > 60000:
        pts = pts[rng.choice(pts.shape[0], 60000, replace=False)]
    fig = plt.figure(figsize=(11.5, 4.8))
    # left: 3D perspective
    ax0 = fig.add_subplot(1, 2, 1, projection="3d")
    ax0.scatter(pts[:, 0], pts[:, 1], pts[:, 2], s=0.5, c=pts[:, 2],
                cmap="viridis", linewidths=0)
    ax0.set_title("3D view", fontsize=11, color=DARK)
    ax0.set_xlabel("x (m)", fontsize=8)
    ax0.set_ylabel("y (m)", fontsize=8)
    ax0.set_zlabel("z (m)", fontsize=8)
    ax0.tick_params(labelsize=7)
    ax0.view_init(elev=22, azim=-60)
    # right: top-down (x-y) to show the tumbled / mutually-occluding layout
    ax1 = fig.add_subplot(1, 2, 2)
    ax1.scatter(pts[:, 0], pts[:, 1], s=0.6, c=pts[:, 2], cmap="viridis",
                linewidths=0)
    ax1.set_aspect("equal", adjustable="datalim")
    ax1.set_title("top-down (x–y)", fontsize=11, color=DARK)
    ax1.set_xlabel("x (m)", fontsize=8)
    ax1.set_ylabel("y (m)", fontsize=8)
    ax1.tick_params(labelsize=7)
    ax1.grid(True, alpha=0.25)
    fig.suptitle("Real survey LiDAR — tumbled, partially-buried 200 L drum pile "
                 f"({pts.shape[0]:,} pts shown; single viewpoint)",
                 fontsize=13, fontweight="bold", color=DARK)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out = os.path.join(ASSETS, "station1_pile_raw.png")
    fig.savefig(out, dpi=160)
    plt.close(fig)
    print("wrote", out)


if __name__ == "__main__":
    fig_pipeline_flow()
    fig_station1_pile_raw()
