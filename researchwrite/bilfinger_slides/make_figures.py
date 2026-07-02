#!/usr/bin/env python3
"""
Render PNG figures for the Bilfinger progress slides.

Reads raw clouds from data/{real,synth}/<scene>/ and each method's
predictions.json (project schema, meters), draws an x-y side projection
(camera optical: x right, y down -> barrel axis is vertical) with the
detected cylinder overlaid (red) and, where available, ground truth (green).

Output PNGs -> researchwrite/bilfinger_slides/assets/
"""
import os
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
MASTERS = os.path.abspath(os.path.join(HERE, "..", ".."))
ASSETS = os.path.join(HERE, "assets")
os.makedirs(ASSETS, exist_ok=True)
MAX_PTS = 25000
np.random.seed(0)


# ----------------------------------------------------------------- IO
def load_pcd_ascii(path):
    pts = []
    with open(path) as f:
        in_data = False
        for line in f:
            if in_data:
                p = line.split()
                if len(p) >= 3:
                    pts.append([float(p[0]), float(p[1]), float(p[2])])
            elif line.startswith("DATA"):
                in_data = True
    return np.array(pts, float)


def load_cloud_m(scene_dir):
    pcd = os.path.join(scene_dir, "scan000.pcd")
    if os.path.isfile(pcd):
        return load_pcd_ascii(pcd)
    txt = os.path.join(scene_dir, "scan000.3d")
    if os.path.isfile(txt):
        return np.loadtxt(txt)[:, :3] / 100.0
    raise FileNotFoundError(scene_dir)


def load_cyls(path, key):
    with open(path) as f:
        d = json.load(f)
    return d.get(key, [])


# ----------------------------------------------------------------- draw
def draw_cloud(ax, pts):
    if pts.shape[0] > MAX_PTS:
        pts = pts[np.random.choice(pts.shape[0], MAX_PTS, replace=False)]
    ax.scatter(pts[:, 0], pts[:, 1], s=1.2, c=pts[:, 2],
               cmap="viridis", linewidths=0, alpha=0.75)


def draw_cyl(ax, c, color, radius_key="radius_m"):
    """x-y side projection: rectangle along (projected) axis + end circles."""
    ctr = np.asarray(c["center"], float)
    ax_v = np.asarray(c["axis"], float)
    r = float(c[radius_key])
    ext = c.get("extent_m") or c.get("height_m") or 0.40
    half = ext / 2.0
    s = ctr - ax_v * half
    e = ctr + ax_v * half
    s2, e2 = s[:2], e[:2]
    a = e2 - s2
    h = np.linalg.norm(a)
    ax.add_patch(plt.Circle(s2, r, fill=False, edgecolor=color, lw=1.6))
    ax.add_patch(plt.Circle(e2, r, fill=False, edgecolor=color, lw=1.6))
    if h > 1e-6:
        u = a / h
        n = np.array([-u[1], u[0]])
        corners = np.array([s2 + n * r, e2 + n * r, e2 - n * r, s2 - n * r])
        ax.add_patch(plt.Polygon(corners, closed=True, fill=True,
                                 facecolor=color, edgecolor=color,
                                 alpha=0.20, lw=1.2))


def style(ax, title):
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xlabel("x (m)", fontsize=9)
    ax.set_ylabel("y (m)", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.set_title(title, fontsize=11)
    ax.grid(True, alpha=0.25)
    ax.invert_yaxis()  # camera optical: +y down


# ----------------------------------------------------------------- figures
def fig_raw_vs_det(scene_group, scene, pred_path, out, banner, det_label):
    pts = load_cloud_m(os.path.join(MASTERS, "data", scene_group, scene))
    dets = load_cyls(pred_path, "detections")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 5.2))
    draw_cloud(a1, pts)
    style(a1, f"raw point cloud  ({pts.shape[0]:,} pts)")
    draw_cloud(a2, pts)
    for c in dets:
        draw_cyl(a2, c, "red")
    style(a2, det_label)
    fig.suptitle(banner, fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(out, dpi=160)
    plt.close(fig)
    print("wrote", out)


def fig_det_vs_gt(scene_group, scene, pred_path, gt_path, out, banner):
    pts = load_cloud_m(os.path.join(MASTERS, "data", scene_group, scene))
    dets = load_cyls(pred_path, "detections")
    gts = load_cyls(gt_path, "barrels")
    fig, ax = plt.subplots(figsize=(6.4, 5.8))
    draw_cloud(ax, pts)
    for g in gts:
        draw_cyl(ax, g, "limegreen")
    for c in dets:
        draw_cyl(ax, c, "red")
    style(ax, "detected (red) vs ground truth (green)")
    fig.suptitle(banner, fontsize=11, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(out, dpi=160)
    plt.close(fig)
    print("wrote", out)


def fig_methods_grid(scene_group, scene, methods, out, banner):
    pts = load_cloud_m(os.path.join(MASTERS, "data", scene_group, scene))
    fig, axes = plt.subplots(1, len(methods), figsize=(3.0 * len(methods), 3.6))
    for ax, (m, label) in zip(axes, methods):
        draw_cloud(ax, pts)
        p = os.path.join(MASTERS, "methods", m, "results", scene,
                         "predictions.json")
        for c in load_cyls(p, "detections"):
            draw_cyl(ax, c, "red")
        style(ax, label)
    fig.suptitle(banner, fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(out, dpi=160)
    plt.close(fig)
    print("wrote", out)


def P(*a):
    return os.path.join(MASTERS, *a)


if __name__ == "__main__":
    # 1. REAL capture: raw vs detection
    fig_raw_vs_det(
        "real", "xtion02_crop",
        P("methods", "ransac_cylinder", "results", "xtion02_crop", "predictions.json"),
        os.path.join(ASSETS, "real_raw_vs_det.png"),
        "REAL DATA — Asus Xtion Pro depth capture (single barrel, ~180° visible)",
        "detected cylinder (RANSAC fit)  r=4.6 cm")

    # 2. SYNTHETIC: detection vs ground truth
    fig_det_vs_gt(
        "synth", "synth_half",
        P("methods", "ransac_cylinder", "results", "synth_half", "predictions.json"),
        P("data", "synth", "synth_half", "gt.json"),
        os.path.join(ASSETS, "synth_det_vs_gt.png"),
        "SYNTHETIC DATA — generated cloud with exact ground truth")

    # 3. Four methods on the same REAL scene
    fig_methods_grid(
        "real", "xtion02_crop",
        [("3dtk_hough", "3DTK Hough"),
         ("ransac_cylinder", "RANSAC fit"),
         ("ls_cylinder", "Least-squares"),
         ("efficient_ransac", "Efficient RANSAC")],
        os.path.join(ASSETS, "methods_grid_real.png"),
        "FOUR DETECTION METHODS on the same REAL barrel capture")
