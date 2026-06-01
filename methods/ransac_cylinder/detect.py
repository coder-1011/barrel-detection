#!/usr/bin/env python3
"""
RANSAC cylinder-fit detector (method #2, after the 3DTK Hough baseline).

Reuses the shared proposer (`find_barrel_clusters` from the 3dtk_hough
`crop_barrel.py`) to answer "a barrel is here", then runs a pure-Python RANSAC
cylinder fit (pyRANSAC-3D) per cluster for the metric fit (radius / axis /
center). Honors the project's proposer-vs-fit split: swap only the fit, keep
the proposer.

Input handling (matches the project convention):
  scan000.pcd present -> read as meters
  else scan000.3d      -> read first 3 cols, divide by 100 (3DTK is cm)

Clusters:
  --crop     run the proposer (cluttered real scans: wall/floor + barrel)
  --no-crop  treat the whole cloud as one barrel (clean synth scans) [default]

Output: results/<scene>/predictions.json in the project-standard schema
(meters, camera_optical frame). See common/eval_schema.py.

Usage (from ~/masters):
  python3 methods/ransac_cylinder/detect.py --scene data/synth/data_synth_half \
      --out methods/ransac_cylinder/results/data_synth_half/predictions.json
"""
import argparse
import os
import sys
import time

import numpy as np
import open3d as o3d
import pyransac3d as pyrsc

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "common"))
sys.path.insert(0, os.path.join(_HERE, "..", "3dtk_hough"))
from eval_schema import Detection, save_pred       # noqa: E402
from crop_barrel import find_barrel_clusters        # noqa: E402


def load_cloud_m(scene_dir):
    """Return Nx3 xyz in meters. Prefer scan000.pcd (m); fall back to the
    3DTK scan000.3d (cm, first 3 cols)."""
    pcd_path = os.path.join(scene_dir, "scan000.pcd")
    if os.path.isfile(pcd_path):
        pcd = o3d.io.read_point_cloud(pcd_path)
        if len(pcd.points):
            return np.asarray(pcd.points), pcd, "scan000.pcd (m)"
    d3_path = os.path.join(scene_dir, "scan000.3d")
    if os.path.isfile(d3_path):
        arr = np.loadtxt(d3_path)
        xyz_m = arr[:, :3] / 100.0
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(xyz_m)
        return xyz_m, pcd, "scan000.3d (cm->m, first 3 cols)"
    sys.exit(f"no scan000.pcd or scan000.3d in {scene_dir}")


def _circle_algebraic(xy):
    """Kasa algebraic circle fit. xy is (N,2). Returns (cx, cy, r)."""
    x, y = xy[:, 0], xy[:, 1]
    A = np.column_stack([x, y, np.ones_like(x)])
    b = x * x + y * y
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy = sol[0] / 2.0, sol[1] / 2.0
    r = np.sqrt(max(0.0, sol[2] + cx * cx + cy * cy))
    return cx, cy, r


def _circle_ransac(xy, thresh, max_iter, rng):
    """2D circle RANSAC on a (partial) arc. Sample 3 pts -> circumcircle ->
    count inliers within thresh of the circle; refine algebraically on the
    best inlier set. Returns (cx, cy, r, inlier_mask)."""
    n = len(xy)
    best_mask, best_count = None, -1
    for _ in range(max_iter):
        i, j, k = rng.choice(n, 3, replace=False)
        (x1, y1), (x2, y2), (x3, y3) = xy[i], xy[j], xy[k]
        a = x1 - x2; b = y1 - y2; c = x1 - x3; d = y1 - y3
        e = ((x1 * x1 - x2 * x2) + (y1 * y1 - y2 * y2)) / 2.0
        f = ((x1 * x1 - x3 * x3) + (y1 * y1 - y3 * y3)) / 2.0
        det = a * d - b * c
        if abs(det) < 1e-12:
            continue
        cx = (d * e - b * f) / det
        cy = (a * f - c * e) / det
        r = np.hypot(x1 - cx, y1 - cy)
        resid = np.abs(np.hypot(xy[:, 0] - cx, xy[:, 1] - cy) - r)
        mask = resid < thresh
        cnt = int(mask.sum())
        if cnt > best_count:
            best_count, best_mask = cnt, mask
    if best_mask is None or best_mask.sum() < 3:
        cx, cy, r = _circle_algebraic(xy)
        return cx, cy, r, np.ones(n, dtype=bool)
    cx, cy, r = _circle_algebraic(xy[best_mask])
    resid = np.abs(np.hypot(xy[:, 0] - cx, xy[:, 1] - cy) - r)
    mask = resid < thresh
    if mask.sum() >= 3:
        cx, cy, r = _circle_algebraic(xy[mask])
    return cx, cy, r, mask


def fit_normals2step(pts, thresh, max_iter, rng):
    """Robust 2-step cylinder fit for partial one-sided arcs:
      1. axis = the direction all surface normals are perpendicular to
         (smallest-eigenvector of sum n n^T over estimated normals).
      2. project points to the plane perpendicular to axis and RANSAC-fit a
         2D circle (radius + center).
    Returns (center_on_axis, axis_unit, radius, n_inliers, n_fit_pts)."""
    p = o3d.geometry.PointCloud()
    p.points = o3d.utility.Vector3dVector(pts)
    p.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=0.02, max_nn=30))
    nrm = np.asarray(p.normals)
    M = nrm.T @ nrm
    w, V = np.linalg.eigh(M)
    axis = V[:, 0]                      # smallest eigenvalue -> cylinder axis
    axis = axis / (np.linalg.norm(axis) + 1e-12)
    # orthonormal basis for the plane perpendicular to axis
    tmp = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(axis, tmp); u /= (np.linalg.norm(u) + 1e-12)
    v = np.cross(axis, u)
    xy = np.column_stack([pts @ u, pts @ v])
    cx, cy, r, mask = _circle_ransac(xy, thresh, max_iter, rng)
    t_mean = float((pts @ axis).mean())
    center = cx * u + cy * v + t_mean * axis
    return center, axis, float(r), int(mask.sum()), len(pts)


def fit_one(pts, thresh, max_iter, fit_voxel):
    """RANSAC cylinder fit on one cluster. Optionally voxel-downsample the fit
    input for speed (synth clouds are dense). Returns
    (center, axis_unit, radius, n_inliers, n_fit_pts)."""
    fit_pts = pts
    if fit_voxel and fit_voxel > 0 and len(pts) > 2000:
        p = o3d.geometry.PointCloud()
        p.points = o3d.utility.Vector3dVector(pts)
        fit_pts = np.asarray(p.voxel_down_sample(fit_voxel).points)
    center, axis, radius, inliers = pyrsc.Cylinder().fit(
        fit_pts, thresh=thresh, maxIteration=max_iter)
    axis = np.asarray(axis, float).ravel()
    n = np.linalg.norm(axis)
    if n > 1e-9:
        axis = axis / n
    return (np.asarray(center, float).ravel(), axis, float(radius),
            len(inliers), len(fit_pts))


def axis_extent(pts, center, axis):
    """Span of the points projected onto the cylinder axis (meters)."""
    t = (pts - center) @ axis
    return float(t.max() - t.min())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True, help="data scene dir (has scan000.*)")
    ap.add_argument("--out", required=True, help="predictions.json path")
    ap.add_argument("--method", default="ransac_cylinder")
    ap.add_argument("--fit", choices=["normals2step", "pyransac"],
                    default="normals2step",
                    help="normals2step (robust, axis from normals + 2D circle "
                         "RANSAC) [default]; pyransac (pyRANSAC-3D 3-pt cylinder)")
    # fit knobs
    ap.add_argument("--thresh", type=float, default=0.005,
                    help="RANSAC inlier distance from the cylinder hull (m)")
    ap.add_argument("--max-iter", type=int, default=2000,
                    help="RANSAC iterations")
    ap.add_argument("--fit-voxel", type=float, default=0.004,
                    help="downsample the per-cluster fit input to this voxel (m); 0=off")
    ap.add_argument("--r-min", type=float, default=0.02,
                    help="reject fits with radius below this (m)")
    ap.add_argument("--r-max", type=float, default=0.20,
                    help="reject fits with radius above this (m)")
    ap.add_argument("--seed", type=int, default=0, help="RNG seed (reproducible RANSAC)")
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

    import random
    random.seed(args.seed)
    np.random.seed(args.seed)

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

    rng = np.random.default_rng(args.seed)
    t0 = time.time()
    dets = []
    for i, pts in enumerate(clusters):
        if len(pts) < 10:
            continue
        if args.fit == "normals2step":
            center, axis, radius, n_in, n_fit = fit_normals2step(
                pts, args.thresh, args.max_iter, rng)
        else:
            center, axis, radius, n_in, n_fit = fit_one(
                pts, args.thresh, args.max_iter, args.fit_voxel)
        ok = args.r_min <= radius <= args.r_max
        print(f"  cluster[{i}] n={len(pts):6d} fit_n={n_fit:6d}  "
              f"r={radius*100:6.2f}cm  axis=[{axis[0]:+.2f} {axis[1]:+.2f} "
              f"{axis[2]:+.2f}]  inliers={n_in}  "
              f"{'KEEP' if ok else 'REJECT (radius out of band)'}")
        if not ok:
            continue
        dets.append(Detection(
            radius_m=radius,
            axis=axis.tolist(),
            center=center.tolist(),
            extent_m=axis_extent(pts, center, axis),
            score=(n_in / max(1, n_fit)),
            lateral_pts=int(n_in),
        ))
    runtime_s = time.time() - t0

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    save_pred(args.out, scene, args.method, dets, runtime_s=runtime_s)
    print(f"\nwrote {len(dets)} detection(s) -> {args.out}  ({runtime_s:.2f}s)")


if __name__ == "__main__":
    main()
