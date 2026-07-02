#!/usr/bin/env python3
"""
Least-squares cylinder-fit detector (method #3).

Geometric, no training data. Uses the shared proposer
(`find_barrel_clusters` from the 3dtk_hough `crop_barrel.py`) to answer
"a barrel is here", then fits each cluster with a nonlinear least-squares
cylinder fit (xingjiepan/cylinder_fitting, the Lukacs-style geometric-distance
fit) for the metric fit. Complements method #2 (ransac_cylinder): same proposer,
a different fit (LS vs RANSAC) — a clean fit-quality comparison.

Input / cluster / output handling mirror methods/ransac_cylinder/detect.py:
  scan000.pcd (m) or scan000.3d (cm->m); --crop runs the proposer, --no-crop
  treats the whole clean cloud as one barrel [default]; predictions.json in the
  project-standard schema (meters, camera_optical). See common/eval_schema.py.

Usage (from ~/masters):
  python3 methods/ls_cylinder/detect.py --scene data/synth/synth_half \
      --out methods/ls_cylinder/results/synth_half/predictions.json
"""
import argparse
import os
import sys
import time
import types

import numpy as np
import open3d as o3d

# cylinder_fitting's package __init__ pulls in a matplotlib visualizer that is
# broken against the installed matplotlib; stub it before importing.
_vis = types.ModuleType("cylinder_fitting.visualize")
for _fn in ("show_fit", "show_G_distribution"):
    setattr(_vis, _fn, lambda *a, **k: None)
sys.modules["cylinder_fitting.visualize"] = _vis
import cylinder_fitting as cf                       # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "common"))
sys.path.insert(0, os.path.join(_HERE, "..", "3dtk_hough"))
from eval_schema import Detection, save_pred         # noqa: E402
from crop_barrel import find_barrel_clusters          # noqa: E402


def load_cloud_m(scene_dir):
    """Return (xyz_m Nx3, o3d cloud, source label). Prefer scan000.pcd (m);
    fall back to the 3DTK scan000.3d (cm, first 3 cols)."""
    pcd_path = os.path.join(scene_dir, "scan000.pcd")
    if os.path.isfile(pcd_path):
        pcd = o3d.io.read_point_cloud(pcd_path)
        if len(pcd.points):
            return np.asarray(pcd.points), pcd, "scan000.pcd (m)"
    d3_path = os.path.join(scene_dir, "scan000.3d")
    if os.path.isfile(d3_path):
        xyz_m = np.loadtxt(d3_path)[:, :3] / 100.0
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(xyz_m)
        return xyz_m, pcd, "scan000.3d (cm->m, first 3 cols)"
    sys.exit(f"no scan000.pcd or scan000.3d in {scene_dir}")


def axis_extent(pts, center, axis):
    """Span of points projected onto the cylinder axis (meters)."""
    t = (pts - center) @ axis
    return float(t.max() - t.min())


def fit_ls(pts, fit_voxel):
    """LS cylinder fit on one cluster. Optionally voxel-downsample the fit
    input for speed (the nonlinear solve is the bottleneck). Returns
    (center_on_axis, axis_unit, radius, fit_err, n_fit_pts)."""
    fit_pts = pts
    if fit_voxel and fit_voxel > 0 and len(pts) > 2000:
        p = o3d.geometry.PointCloud()
        p.points = o3d.utility.Vector3dVector(pts)
        fit_pts = np.asarray(p.voxel_down_sample(fit_voxel).points)
    w, c, r, err = cf.fit(fit_pts)
    axis = np.asarray(w, float).ravel()
    n = np.linalg.norm(axis)
    if n > 1e-9:
        axis = axis / n
    return np.asarray(c, float).ravel(), axis, float(r), float(err), len(fit_pts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True, help="data scene dir (has scan000.*)")
    ap.add_argument("--out", required=True, help="predictions.json path")
    ap.add_argument("--method", default="ls_cylinder")
    ap.add_argument("--fit-voxel", type=float, default=0.004,
                    help="downsample per-cluster fit input to this voxel (m); 0=off")
    ap.add_argument("--r-min", type=float, default=0.02,
                    help="reject fits with radius below this (m)")
    ap.add_argument("--r-max", type=float, default=0.20,
                    help="reject fits with radius above this (m)")
    # proposer
    ap.add_argument("--crop", dest="crop", action="store_true",
                    help="run the find_barrel_clusters proposer (cluttered scans)")
    ap.add_argument("--no-crop", dest="crop", action="store_false",
                    help="treat the whole cloud as one barrel (clean synth) [default]")
    ap.set_defaults(crop=False)
    # proposer knobs (mirror crop_barrel.py defaults; used only with --crop)
    ap.add_argument("--voxel", type=float, default=0.005)
    ap.add_argument("--plane-thresh", type=float, default=0.01)
    ap.add_argument("--remove-planes", type=int, default=2)
    ap.add_argument("--eps", type=float, default=0.02)
    ap.add_argument("--min-pts", type=int, default=30)
    ap.add_argument("--target-width", type=float, default=0.085)
    ap.add_argument("--width-tol", type=float, default=0.03)
    ap.add_argument("--max-depth-ratio", type=float, default=0.7)
    ap.add_argument("--min-height", type=float, default=0.10)
    ap.add_argument("--cz-min", type=float, default=0.40)
    ap.add_argument("--cz-max", type=float, default=1.00)
    ap.add_argument("--label-crop-dist", type=float, default=None)
    args = ap.parse_args()

    scene = os.path.basename(os.path.normpath(args.scene))
    xyz_m, pcd, src = load_cloud_m(args.scene)
    print(f"loaded {len(xyz_m)} pts from {scene} [{src}]")

    if args.crop:
        clusters = [sub for _, sub in find_barrel_clusters(pcd, args)]
        if not clusters:
            print("proposer found no barrel cluster; falling back to whole cloud")
            clusters = [xyz_m]
    else:
        clusters = [xyz_m]
    print(f"{len(clusters)} candidate cluster(s)")

    t0 = time.time()
    dets = []
    for i, pts in enumerate(clusters):
        if len(pts) < 10:
            continue
        center, axis, radius, err, n_fit = fit_ls(pts, args.fit_voxel)
        ok = args.r_min <= radius <= args.r_max
        print(f"  cluster[{i}] n={len(pts):6d} fit_n={n_fit:6d}  "
              f"r={radius*100:6.2f}cm  axis=[{axis[0]:+.2f} {axis[1]:+.2f} "
              f"{axis[2]:+.2f}]  fit_err={err:.2e}  "
              f"{'KEEP' if ok else 'REJECT (radius out of band)'}")
        if not ok:
            continue
        dets.append(Detection(
            radius_m=radius,
            axis=axis.tolist(),
            center=center.tolist(),
            extent_m=axis_extent(pts, center, axis),
            score=float(1.0 / (1.0 + err)),   # higher = lower geometric residual
            lateral_pts=int(n_fit),
        ))
    runtime_s = time.time() - t0

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    save_pred(args.out, scene, args.method, dets, runtime_s=runtime_s)
    print(f"\nwrote {len(dets)} detection(s) -> {args.out}  ({runtime_s:.2f}s)")


if __name__ == "__main__":
    main()
