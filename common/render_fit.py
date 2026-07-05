#!/usr/bin/env python3
"""
Headless fit-inspection renderer (PNG) — the host can't open a GUI (Hyprland/Wayland),
so visualise barrel fits to images instead.

For each barrel in a scene's gt.json (matched to its segment file by order) it writes a
per-barrel diagnostic (cross-section vs the fitted circle + shell-residual-along-length +
3D wireframe), and one overview of all fitted cylinders on the full scan000 cloud.

USAGE (host, project .venv):
  .venv/bin/python common/render_fit.py --scene data/real/station1_pit_barrels
  # -> <scene>/renders/fit_<segmentstem>.png  and  <scene>/renders/fit_on_full_cloud.png
  # (renders/ keeps the scene dir itself raw-clouds-only, per the data/ contract)
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import open3d as o3d

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fit_from_segments import extract_cylinder_ransac, load_points, plane_basis  # noqa: E402


def cyl_mesh(c, axis, R, h, u, v, nth=40, ns=12):
    th = np.linspace(0, 2 * np.pi, nth)
    s = np.linspace(-h / 2, h / 2, ns)
    TH, S = np.meshgrid(th, s)
    return c[None, None, :] + R * (np.cos(TH)[..., None] * u + np.sin(TH)[..., None] * v) \
        + S[..., None] * axis


def render_barrel(seg_pts, b, png, ransac=True):
    R = b["radius_m"]; axis = np.array(b["axis"], float); axis /= np.linalg.norm(axis)
    c = np.array(b["center"], float); h = b["height_m"]
    inl = seg_pts[extract_cylinder_ransac(seg_pts, R)] if ransac else seg_pts
    u, v = plane_basis(axis)
    q = inl - c
    a, bb = q @ u, q @ v
    t = q @ axis
    resid_mm = (np.hypot(a, bb) - R) * 1000

    fig = plt.figure(figsize=(16, 5.2))
    ax1 = fig.add_subplot(1, 3, 1)
    sc = ax1.scatter(a, bb, c=t, cmap="viridis", s=10)
    ph = np.linspace(0, 2 * np.pi, 200)
    ax1.plot(R * np.cos(ph), R * np.sin(ph), "r-", lw=2, label=f"fit R={R}m")
    ax1.set_aspect("equal"); ax1.legend(loc="upper right")
    ax1.set_title("cross-section (down the axis)\npoints should sit on the red circle")
    ax1.set_xlabel("m"); ax1.set_ylabel("m"); plt.colorbar(sc, ax=ax1, label="along-axis (m)")

    ax2 = fig.add_subplot(1, 3, 2)
    ax2.scatter(t, resid_mm, s=8, c="tab:blue"); ax2.axhline(0, color="r", lw=1.5)
    for y in (35, -35):
        ax2.axhline(y, color="gray", ls="--", lw=.8)
    ax2.set_title(f"shell residual along length\nRMS={b.get('fit_rms_m', 0)*1000:.0f}mm  (dashed=±35mm)")
    ax2.set_xlabel("along-axis (m)"); ax2.set_ylabel("dist-from-axis − R (mm)")

    ax3 = fig.add_subplot(1, 3, 3, projection="3d")
    ax3.scatter(*inl.T, s=8, c=t, cmap="viridis")
    CY = cyl_mesh(c, axis, R, h, u, v)
    ax3.plot_wireframe(CY[..., 0], CY[..., 1], CY[..., 2], color="red", lw=.5, alpha=.4)
    L = np.array([c - axis * h / 2, c + axis * h / 2]); ax3.plot(*L.T, c="darkred", lw=2)
    m = inl.mean(0); r = np.ptp(inl, 0).max() / 2 * 1.1
    ax3.set_xlim(m[0]-r, m[0]+r); ax3.set_ylim(m[1]-r, m[1]+r); ax3.set_zlim(m[2]-r, m[2]+r)
    ax3.set_box_aspect((1, 1, 1)); ax3.view_init(elev=18, azim=35)
    ax3.set_title("3D: inliers + cylinder")
    plt.suptitle(f"{os.path.basename(png)}  R={R}m h={h:.2f}m axis={axis.round(2)} n={len(inl)}")
    plt.tight_layout(); plt.savefig(png, dpi=120); plt.close(fig)
    print("wrote", png)


def render_full(full, gt, segfiles, png):
    rng = np.random.default_rng(0)
    F = full[rng.choice(len(full), min(35000, len(full)), replace=False)]
    fig = plt.figure(figsize=(16, 7.5))
    ax1 = fig.add_subplot(1, 2, 1)
    ax1.scatter(F[:, 0], F[:, 1], s=1, c=F[:, 2], cmap="Greys", alpha=.5)
    ax2 = fig.add_subplot(1, 2, 2, projection="3d")
    ax2.scatter(F[:, 0], F[:, 1], F[:, 2], s=1, c="lightgray", alpha=.3)
    for i, b in enumerate(gt):
        R = b["radius_m"]; axis = np.array(b["axis"], float); axis /= np.linalg.norm(axis)
        c = np.array(b["center"], float); h = b["height_m"]; u, v = plane_basis(axis)
        if i < len(segfiles):
            inl = load_points(segfiles[i]); inl = inl[extract_cylinder_ransac(inl, R)]
            ax1.scatter(inl[:, 0], inl[:, 1], s=4, c="tab:blue")
            ax2.scatter(inl[:, 0], inl[:, 1], inl[:, 2], s=5, c="tab:blue")
        CY = cyl_mesh(c, axis, R, h, u, v)
        ax1.plot(CY[..., 0].ravel(), CY[..., 1].ravel(), ".", ms=.5, c="red", alpha=.3)
        ax2.plot_wireframe(CY[..., 0], CY[..., 1], CY[..., 2], color="red", lw=.6)
        L = np.array([c - axis*h/2, c + axis*h/2])
        ax1.plot(L[:, 0], L[:, 1], c="darkred", lw=2); ax2.plot(L[:, 0], L[:, 1], L[:, 2], c="darkred", lw=2)
    ax1.set_aspect("equal"); ax1.set_title("full cloud top-down (gray=all pts, blue=inliers, red=fit)")
    ax1.set_xlabel("X (m)"); ax1.set_ylabel("Y (m)")
    m = F.mean(0); r = np.ptp(F, 0).max() / 2
    ax2.set_xlim(m[0]-r, m[0]+r); ax2.set_ylim(m[1]-r, m[1]+r); ax2.set_zlim(m[2]-r, m[2]+r)
    ax2.set_box_aspect((1, 1, 1)); ax2.view_init(elev=35, azim=40); ax2.set_title("full cloud 3D + fits")
    plt.suptitle(f"{len(gt)} fitted barrel(s) on the full cloud")
    plt.tight_layout(); plt.savefig(png, dpi=120); plt.close(fig)
    print("wrote", png)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True, help="scene dir with scan000.pcd, gt.json, segments/")
    ap.add_argument("--no-ransac", action="store_true", help="treat each segment as clean (no inlier extraction)")
    args = ap.parse_args()

    gt = json.load(open(os.path.join(args.scene, "gt.json")))["barrels"]
    outdir = os.path.join(args.scene, "renders")
    os.makedirs(outdir, exist_ok=True)
    segfiles = sorted(f for f in glob.glob(os.path.join(args.scene, "segments", "*"))
                      if os.path.isfile(f) and not f.endswith(".json"))
    for i, b in enumerate(gt):
        if i < len(segfiles):
            stem = os.path.splitext(os.path.basename(segfiles[i]))[0]
            render_barrel(load_points(segfiles[i]), b,
                          os.path.join(outdir, f"fit_{stem}.png"), ransac=not args.no_ransac)
    pcd = os.path.join(args.scene, "scan000.pcd")
    if os.path.isfile(pcd):
        full = np.asarray(o3d.io.read_point_cloud(pcd).points)
        render_full(full, gt, segfiles, os.path.join(outdir, "fit_on_full_cloud.png"))


if __name__ == "__main__":
    main()
