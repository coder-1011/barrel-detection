#!/usr/bin/env python3
"""
Render the figures the evaluation deck needs that don't exist elsewhere.

Reuses the project conventions (Agg backend, camera-optical projection,
viridis-by-depth scatter) from bilfinger_slides/make_figures.py.

Outputs -> researchwrite/presentation_assets/
  - binpicking_intro.png    (slide 1: general bin-picking schematic, open vs covered;
                             swapped out automatically if binpicking_ai_{1,2}.png exist)
  - fitting_explained.png   (slide 3: line-fit example -> cylinder parameters -> arc ambiguity)
  - pipeline_flow.png       (evaluation pipeline with the explanations INSIDE the graphic)
  - synth_data_example.png  (what the synthetic sweep clouds actually look like, 3 noise levels)
  - barrelnet_epochs.png    (BarrelNet real-drum score vs training epoch, laptop CPU vs A100)
  - station1_pile_raw.png   (the real partially-occluded 200 L drum pile, raw)

All figure text is sized to stay readable from the back row after the image is
scaled onto a 13.3" slide (>= ~13 pt at render size).

The synthetic noise-sweep chart (synth_noise_sweep.png) is produced separately
by eval/plot_noise_sweep.py, not here.
"""
import csv
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import (FancyBboxPatch, FancyArrowPatch, Circle,
                                Rectangle, Polygon)

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
    """Evaluation pipeline with the slide's explanations integrated into the
    graphic (supervisor feedback: bullets work better inside the diagram)."""
    boxes = [
        ("1. Data", "real scans +\nsynthetic clouds", ACCENT,
         "depth camera, survey\nLiDAR, generator"),
        ("2. Ground truth", "true barrel poses\n(gt.json)", DARK,
         "one shared format,\neverything in metres"),
        ("3. Detection", "each method runs\non the same scene", GREEN,
         "identical command:\nrun_detection.sh <scene>"),
        ("4. Predictions", "detected barrels\n(predictions.json)", DARK,
         "same format as the\nground truth"),
        ("5. Scoring", "match predictions\nto ground truth", ACCENT,
         "same matching rule\nfor every method"),
        ("6. Metrics", "precision / recall / F1\nradius & axis error", GREEN,
         "plus runtime\nper scene"),
    ]
    n = len(boxes)
    fig, ax = plt.subplots(figsize=(15.5, 4.4))
    ax.set_xlim(0, n)
    ax.set_ylim(0, 1)
    ax.axis("off")
    bw, bh = 0.88, 0.44
    cy = 0.62
    for i, (head, body, col, note) in enumerate(boxes):
        x = i + 0.5
        box = FancyBboxPatch((x - bw / 2, cy - bh / 2), bw, bh,
                             boxstyle="round,pad=0.02,rounding_size=0.06",
                             linewidth=2.0, edgecolor=col, facecolor=LIGHT)
        ax.add_patch(box)
        ax.text(x, cy + 0.115, head, ha="center", va="center",
                fontsize=16, fontweight="bold", color=col)
        ax.text(x, cy - 0.075, body, ha="center", va="center",
                fontsize=12.5, color=DARK)
        ax.text(x, cy - bh / 2 - 0.15, note, ha="center", va="center",
                fontsize=11.5, color="#666666", style="italic")
        if i < n - 1:
            ax.add_patch(FancyArrowPatch((x + bw / 2, cy),
                                         (x + 1 - bw / 2, cy),
                                         arrowstyle="-|>", mutation_scale=20,
                                         linewidth=2.0, color="#777777"))
    ax.set_title("One evaluation pipeline for every method — "
                 "same data in, same score out",
                 fontsize=19, fontweight="bold", color=DARK, pad=14)
    fig.tight_layout()
    out = os.path.join(ASSETS, "pipeline_flow.png")
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


# ----------------------------------------------------------------- bin-picking intro
def _draw_bin(ax, cover=False):
    """Simple, back-row-readable side-view schematic of a bin with cylinders."""
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 8.6)
    ax.set_aspect("equal")
    ax.axis("off")
    # bin walls
    wall = dict(facecolor="#8a9aa8", edgecolor=DARK, linewidth=2)
    ax.add_patch(Rectangle((0.6, 0.6), 0.45, 4.6, **wall))
    ax.add_patch(Rectangle((8.95, 0.6), 0.45, 4.6, **wall))
    ax.add_patch(Rectangle((0.6, 0.2), 8.8, 0.5, **wall))
    # cylinders (side view = circles), tumbled pile
    drums = [(2.2, 1.5), (3.9, 1.4), (5.7, 1.5), (7.5, 1.4),
             (3.0, 3.0), (4.8, 2.9), (6.6, 3.0)]
    for i, (x, y) in enumerate(drums):
        ax.add_patch(Circle((x, y), 0.85, facecolor="#0B5C8A",
                            edgecolor="white", linewidth=2, alpha=0.9))
        ax.add_patch(Circle((x, y), 0.30, facecolor="none",
                            edgecolor="white", linewidth=1.5))
    if cover:
        # sand / debris layer burying most of the pile
        xs = np.linspace(0.6, 9.4, 100)
        ys = 3.3 + 0.5 * np.sin(xs * 1.7) + 0.25 * np.sin(xs * 4.1)
        verts = [(0.6, 0.7)] + list(zip(xs, ys)) + [(9.4, 0.7)]
        ax.add_patch(Polygon(verts, closed=True, facecolor="#C9A96A",
                             edgecolor="#8a6f3d", linewidth=2, alpha=0.92))
        ax.text(5.0, 2.0, "sand / debris", ha="center", fontsize=15,
                color="#5d4a26", fontweight="bold")
    # sensor looking down
    ax.add_patch(Polygon([(4.4, 8.3), (5.6, 8.3), (5.0, 7.6)], closed=True,
                         facecolor=DARK, edgecolor=DARK))
    ax.text(6.0, 8.0, "3D sensor", fontsize=14, color=DARK, va="center")
    for dx in (-1.6, 0.0, 1.6):
        ax.add_patch(FancyArrowPatch((5.0, 7.55), (5.0 + dx, 4.6 if not cover else 4.3),
                                     arrowstyle="-|>", mutation_scale=13,
                                     linewidth=1.3, color="#999999",
                                     linestyle=(0, (4, 3))))


def fig_binpicking_intro():
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.4))
    _draw_bin(axes[0], cover=False)
    axes[0].set_title("Bin picking: find each object and its pose,\nthen grasp it",
                      fontsize=17, fontweight="bold", color=DARK)
    _draw_bin(axes[1], cover=True)
    axes[1].set_title("Our case: the objects are also partially\nburied / covered",
                      fontsize=17, fontweight="bold", color=AMBER)
    fig.tight_layout()
    out = os.path.join(ASSETS, "binpicking_intro.png")
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


# ----------------------------------------------------------------- fitting explained
def fig_fitting_explained():
    fig = plt.figure(figsize=(16, 5.4))

    # --- panel 1: fitting a line (the simplest model) -----------------------
    ax = fig.add_subplot(1, 3, 1)
    rng = np.random.default_rng(3)
    x = np.linspace(0.5, 9.5, 14)
    y = 0.55 * x + 1.3 + rng.normal(0, 0.55, x.size)
    m, b = np.polyfit(x, y, 1)
    for xi, yi in zip(x, y):
        ax.plot([xi, xi], [yi, m * xi + b], color="#bbbbbb", lw=1.6, zorder=1)
    ax.scatter(x, y, s=55, color=ACCENT, zorder=3, label="measured points")
    xs = np.array([0, 10])
    ax.plot(xs, m * xs + b, color="#B02A2A", lw=3, zorder=2,
            label="fitted line")
    ax.set_title("Fitting a line:\nfind slope + offset that\nbest match the points",
                 fontsize=16, fontweight="bold", color=DARK)
    ax.legend(fontsize=13, loc="upper left")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)

    # --- panel 2: the cylinder model + its parameters ------------------------
    ax = fig.add_subplot(1, 3, 2, projection="3d")
    theta = np.linspace(0, 2 * np.pi, 60)
    zz = np.linspace(-1.2, 1.2, 20)
    T, Z = np.meshgrid(theta, zz)
    R = 0.7
    # tilt the cylinder for a nicer view
    ca, sa = np.cos(0.5), np.sin(0.5)
    X0, Y0, Z0 = R * np.cos(T), R * np.sin(T), Z
    X = X0
    Y = ca * Y0 - sa * Z0
    Zc = sa * Y0 + ca * Z0
    ax.plot_surface(X, Y, Zc, color="#9FC5DD", alpha=0.55, linewidth=0)
    # axis arrow
    az = np.array([0, -sa, ca])
    ax.quiver(0, 0, 0, *(az * 1.9), color="#B02A2A", lw=3.5,
              arrow_length_ratio=0.12)
    ax.quiver(0, 0, 0, *(-az * 1.6), color="#B02A2A", lw=3.5,
              arrow_length_ratio=0.0)
    ax.scatter([0], [0], [0], s=90, color=DARK, zorder=5)
    # radius arrow (perpendicular to axis)
    ax.quiver(0, 0, 0, R, 0, 0, color=GREEN, lw=3.5, arrow_length_ratio=0.18)
    ax.text(0.10, 0.18, 0.12, "centre", fontsize=15, color=DARK,
            fontweight="bold")
    ax.text(*(az * 2.05), "axis\ndirection", fontsize=15, color="#B02A2A",
            fontweight="bold")
    ax.text(R * 0.55, -0.05, -0.42, "radius", fontsize=15, color=GREEN,
            fontweight="bold")
    ax.set_axis_off()
    ax.set_box_aspect((1, 1, 1.15))
    ax.set_title("A cylinder has 3 things to find:\ncentre, axis direction, radius",
                 fontsize=16, fontweight="bold", color=DARK, pad=0)

    # --- panel 3: why occlusion makes it hard --------------------------------
    ax = fig.add_subplot(1, 3, 3)
    rng = np.random.default_rng(7)
    r_true = 1.0
    ang = np.deg2rad(np.linspace(60, 120, 26))          # thin 60-degree arc
    px = r_true * np.cos(ang) + rng.normal(0, 0.012, ang.size)
    py = r_true * np.sin(ang) + rng.normal(0, 0.012, ang.size)
    ax.scatter(px, py, s=45, color=ACCENT, zorder=5, label="visible points")
    for r, cyc, col in [(1.0, 0.0, "#B02A2A"), (1.55, -0.55, "#B76E00"),
                        (0.72, 0.28, "#7b4fa6")]:
        th = np.linspace(0, 2 * np.pi, 200)
        ax.plot(r * np.cos(th), cyc + r * np.sin(th) * 1.0, color=col,
                lw=2.6, alpha=0.85)
    ax.set_aspect("equal")
    ax.set_xlim(-1.9, 1.9); ax.set_ylim(-2.35, 1.55)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.legend(fontsize=13, loc="lower center")
    ax.set_title("The problem: a thin visible arc\nfits many different cylinders",
                 fontsize=16, fontweight="bold", color=AMBER)

    fig.tight_layout()
    out = os.path.join(ASSETS, "fitting_explained.png")
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


# ----------------------------------------------------------------- synth data example
def fig_synth_data_example():
    """Show what the synthetic sweep clouds actually look like (3 noise levels)."""
    levels = [("0.00", "no noise"), ("0.30", "medium noise"),
              ("0.60", "high noise")]
    fig = plt.figure(figsize=(15, 5.2))
    for i, (sig, lab) in enumerate(levels):
        pcd = os.path.join(MASTERS, "data", "synth", f"sweep_n{sig}_s0",
                           "scan000.pcd")
        pts = load_pcd(pcd)
        ax = fig.add_subplot(1, 3, i + 1, projection="3d")
        ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2], s=2.2, c=pts[:, 2],
                   cmap="viridis", linewidths=0)
        ax.set_title(f"noise σ = {sig} cm  ({lab})", fontsize=17,
                     fontweight="bold", color=DARK)
        ax.set_axis_off()
        # equal-ish aspect
        c = pts.mean(axis=0)
        r = float(np.abs(pts - c).max()) * 1.02
        ax.set_xlim(c[0] - r, c[0] + r)
        ax.set_ylim(c[1] - r, c[1] + r)
        ax.set_zlim(c[2] - r, c[2] + r)
        ax.view_init(elev=18, azim=-55)
    fig.suptitle("The synthetic test clouds — one barrel, 120° visible arc, "
                 "only the noise changes", fontsize=19, fontweight="bold",
                 color=DARK)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    out = os.path.join(ASSETS, "synth_data_example.png")
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


# ----------------------------------------------------------------- barrelnet epochs
def _load_train_log(path):
    ep, hits, dist, axis = [], [], [], []
    with open(path) as f:
        for row in csv.DictReader(f):
            ep.append(int(row["epoch"]))
            hits.append(int(row["real_hits"].split("/")[0]))
            dist.append(float(row["real_dist_m_med"]) * 100.0)
            axis.append(float(row["real_axis_deg_med"]))
    return (np.array(ep), np.array(hits, float), np.array(dist), np.array(axis))


def _smooth(y, k=7):
    if len(y) < k:
        return y
    pad = k // 2
    yp = np.pad(y, (pad, pad), mode="edge")
    return np.convolve(yp, np.ones(k) / k, mode="valid")


def fig_barrelnet_epochs():
    runs = [("runs/run1/train_log.csv", "laptop CPU run (stopped at epoch 148)",
             "#888888"),
            ("runs/a100/train_log.csv", "A100 GPU run (full 200 epochs)",
             ACCENT)]
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.0))
    panels = [("hits", "drums found (of 21)", "Drums within the accuracy gate"),
              ("dist", "median centre error (cm)", "How far off the centre is"),
              ("axis", "median axis error (deg)", "How far off the direction is")]
    data = {}
    for rel, label, color in runs:
        path = os.path.join(MASTERS, "methods", "barrelnet", rel)
        data[label] = (_load_train_log(path), color)
    for ax, (key, ylab, title) in zip(axes, panels):
        idx = {"hits": 1, "dist": 2, "axis": 3}[key]
        for label, ((ep, hits, dist, axis_), color) in [
                (lbl, d) for lbl, d in data.items()]:
            y = (hits, dist, axis_)[idx - 1]
            ax.plot(ep, y, color=color, alpha=0.25, lw=1.2)
            ax.plot(ep, _smooth(y), color=color, lw=3.0, label=label)
        if key == "hits":
            ax.set_ylim(0, 21)
            ax.axhline(21, color="#bbbbbb", ls=":", lw=1.5)
        if key == "dist":
            ax.axhline(10, color="#B02A2A", ls="--", lw=2)
            ax.text(3, 10.6, "10 cm gate", color="#B02A2A", fontsize=13)
        if key == "axis":
            ax.axhline(30, color="#B02A2A", ls="--", lw=2)
            ax.text(3, 30.8, "30° gate", color="#B02A2A", fontsize=13)
        ax.set_xlabel("training epoch", fontsize=14)
        ax.set_ylabel(ylab, fontsize=14)
        ax.set_title(title, fontsize=16, fontweight="bold", color=DARK)
        ax.tick_params(labelsize=12)
        ax.grid(True, alpha=0.3)
    # annotate final scores on the hits panel
    for label, ((ep, hits, _, _), color) in data.items():
        axes[0].annotate(f"{int(hits[-1])}/21", (ep[-1], hits[-1]),
                         textcoords="offset points", xytext=(-6, 8),
                         fontsize=15, fontweight="bold", color=color)
    axes[0].legend(fontsize=12.5, loc="upper left")
    fig.suptitle("BarrelNet on the 21 held-out REAL drums (never trained on) "
                 "— score vs training epoch", fontsize=19,
                 fontweight="bold", color=DARK)
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    out = os.path.join(ASSETS, "barrelnet_epochs.png")
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
    fig = plt.figure(figsize=(13.5, 5.6))
    # left: 3D perspective
    ax0 = fig.add_subplot(1, 2, 1, projection="3d")
    ax0.scatter(pts[:, 0], pts[:, 1], pts[:, 2], s=0.5, c=pts[:, 2],
                cmap="viridis", linewidths=0)
    ax0.set_title("3D view", fontsize=16, fontweight="bold", color=DARK)
    ax0.set_xlabel("x (m)", fontsize=12)
    ax0.set_ylabel("y (m)", fontsize=12)
    ax0.set_zlabel("z (m)", fontsize=12)
    ax0.tick_params(labelsize=11)
    ax0.view_init(elev=22, azim=-60)
    # right: top-down (x-y) to show the tumbled / mutually-occluding layout
    ax1 = fig.add_subplot(1, 2, 2)
    ax1.scatter(pts[:, 0], pts[:, 1], s=0.6, c=pts[:, 2], cmap="viridis",
                linewidths=0)
    ax1.set_aspect("equal", adjustable="datalim")
    ax1.set_title("view from above", fontsize=16, fontweight="bold", color=DARK)
    ax1.set_xlabel("x (m)", fontsize=12)
    ax1.set_ylabel("y (m)", fontsize=12)
    ax1.tick_params(labelsize=11)
    ax1.grid(True, alpha=0.25)
    fig.suptitle("Real survey LiDAR — tumbled, partially-buried 200 L drum pile "
                 "(one viewpoint)",
                 fontsize=19, fontweight="bold", color=DARK)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out = os.path.join(ASSETS, "station1_pile_raw.png")
    fig.savefig(out, dpi=160)
    plt.close(fig)
    print("wrote", out)


if __name__ == "__main__":
    fig_binpicking_intro()
    fig_fitting_explained()
    fig_pipeline_flow()
    fig_synth_data_example()
    fig_barrelnet_epochs()
    fig_station1_pile_raw()
