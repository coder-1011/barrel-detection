#!/usr/bin/env python3
"""
Fit barrel ground truth from per-barrel point segments (radius-locked cylinder fit).

Pairs with the CloudCompare segmentation workflow: you carve each barrel out of the
pile (Segment tool) and export each one as its own cloud into a segments dir; this
reads them and fits a *known-radius* cylinder per segment, writing gt.json in the
project schema (common/eval_schema.Barrel). Self-contained — numpy + open3d only
(no cylinder_fitting dependency).

Per segment the unknowns are the axis direction and the center on the axis (radius and
height are priors for 200 L drums: r=0.286 m, h~0.85 m):
  - axis:   from --hints (2 points along the barrel) if given, else estimated as the
            direction most orthogonal to the segment's surface normals (the cylinder
            axis is perpendicular to every side-wall normal).
  - center: radius-locked circle fit in the plane perpendicular to the axis (robust to
            partial arcs — far better than eyeballing a center on an occluded barrel).
  - height / occlusion_frac: from the points' extent and angular coverage around the axis.

USAGE (host, with the project .venv):
  .venv/bin/python common/fit_from_segments.py \
      --segments-dir data/real/station1_pit_barrels/segments \
      --scene data/real/station1_pit_barrels [--hints hints.json] [--radius 0.286]

Segment files: barrel_*.{xyz,asc,txt,pcd} (any extension; ascii = first 3 cols x y z).
Optional --hints JSON: {"barrel_00": [[x1,y1,z1],[x2,y2,z2]], ...} axis end-points per
segment (keyed by filename stem). Use it for heavily-occluded drums where the auto axis
from a thin arc is unreliable.
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
import open3d as o3d


def load_points(path):
    """Load Nx3 meters from a segment file (.pcd via open3d, else ascii first 3 cols)."""
    if path.lower().endswith((".pcd", ".ply")):
        p = o3d.io.read_point_cloud(path)
        return np.asarray(p.points)
    for delim in (None, ",", ";"):
        try:
            a = np.loadtxt(path, usecols=(0, 1, 2), delimiter=delim, comments=("#", "/"))
            if a.ndim == 2 and len(a):
                return a
        except Exception:
            continue
    raise ValueError(f"could not parse points from {path}")


def estimate_axis_from_normals(pts):
    """Cylinder axis = direction most orthogonal to surface normals (min-eigvec of NtN)."""
    pc = o3d.geometry.PointCloud()
    pc.points = o3d.utility.Vector3dVector(pts)
    nn = pc.compute_nearest_neighbor_distance()
    r = max(3.0 * float(np.median(nn)), 0.05)
    pc.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=r, max_nn=30))
    N = np.asarray(pc.normals)
    if len(N) < 3:
        return pca_axis(pts), N
    w, V = np.linalg.eigh(N.T @ N)        # ascending eigenvalues
    return V[:, 0] / np.linalg.norm(V[:, 0]), N


def pca_axis(pts):
    """Fallback axis: largest-extent principal direction (drum is taller than wide)."""
    c = pts - pts.mean(0)
    _, V = np.linalg.eigh(c.T @ c)
    return V[:, -1] / np.linalg.norm(V[:, -1])


def plane_basis(axis):
    a = axis / np.linalg.norm(axis)
    t = np.array([1.0, 0, 0]) if abs(a[0]) < 0.9 else np.array([0, 1.0, 0])
    u = np.cross(a, t); u /= np.linalg.norm(u)
    v = np.cross(a, u)
    return u, v


def fixed_radius_circle(P2, R, c0, iters=50):
    """Gauss-Newton fit of a circle of FIXED radius R to 2D points P2; returns center."""
    c = c0.astype(float).copy()
    for _ in range(iters):
        d = P2 - c
        dist = np.linalg.norm(d, axis=1)
        dist = np.where(dist < 1e-9, 1e-9, dist)
        res = dist - R                       # residual per point
        J = -d / dist[:, None]               # d(res)/d(center)
        H = J.T @ J
        g = J.T @ res
        try:
            step = np.linalg.solve(H + 1e-9 * np.eye(2), g)
        except np.linalg.LinAlgError:
            break
        c -= step
        if np.linalg.norm(step) < 1e-6:
            break
    rms = float(np.sqrt(np.mean((np.linalg.norm(P2 - c, axis=1) - R) ** 2)))
    return c, rms


def angular_coverage(P2, center):
    """Fraction of the full circle the arc spans (1.0 = closed; small = thin sliver)."""
    ang = np.sort(np.arctan2(P2[:, 1] - center[1], P2[:, 0] - center[0]))
    if len(ang) < 2:
        return 0.0
    gaps = np.diff(np.concatenate([ang, [ang[0] + 2 * np.pi]]))
    return float((2 * np.pi - gaps.max()) / (2 * np.pi))


def extract_cylinder_ransac(pts, R, tol=0.035, iters=4000, seed=0):
    """Pull the dominant fixed-radius-R cylinder out of a coarse crop (for no-mouse
    box crops that catch clutter/neighbours). Axis = n_i x n_j of two points' normals;
    center seeded from p_i +/- R*n_i; inliers = points within tol of the R-shell whose
    normal is roughly radial. Returns the inlier mask."""
    pc = o3d.geometry.PointCloud()
    pc.points = o3d.utility.Vector3dVector(pts)
    nn = pc.compute_nearest_neighbor_distance()
    rr = max(3.0 * float(np.median(nn)), 0.05)
    pc.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=rr, max_nn=30))
    N = np.asarray(pc.normals)
    rng = np.random.default_rng(seed)
    n = len(pts)
    best = None
    for _ in range(iters):
        i, j = rng.integers(0, n, 2)
        ax = np.cross(N[i], N[j]); na = np.linalg.norm(ax)
        if na < 0.3:
            continue
        ax /= na
        for s in (1, -1):
            a0 = pts[i] + s * R * N[i]
            d = pts - a0
            perp = d - np.outer(d @ ax, ax)
            rad = np.linalg.norm(perp, axis=1)
            rdir = perp / np.where(rad[:, None] < 1e-9, 1e-9, rad[:, None])
            inl = (np.abs(rad - R) < tol) & (np.abs(np.einsum('ij,ij->i', rdir, N)) > 0.7)
            cnt = int(inl.sum())
            if best is None or cnt > best[0]:
                best = (cnt, inl)
    return best[1] if best else np.ones(n, bool)


def fit_segment(pts, R, hint=None):
    if hint is not None:
        axis = np.asarray(hint[1], float) - np.asarray(hint[0], float)
        axis = axis / np.linalg.norm(axis)
    else:
        axis, _ = estimate_axis_from_normals(pts)
    u, v = plane_basis(axis)
    o = pts.mean(0)
    q = pts - o
    P2 = np.column_stack([q @ u, q @ v])
    # init center: pull the arc centroid inward by R along the mean radial direction
    rad = P2 - P2.mean(0)
    rn = np.linalg.norm(rad, axis=1, keepdims=True)
    meandir = (rad / np.where(rn < 1e-9, 1e-9, rn)).mean(0)
    meandir = meandir / (np.linalg.norm(meandir) + 1e-9)
    c0 = P2.mean(0) - R * meandir
    c2, rms = fixed_radius_circle(P2, R, c0)
    center = o + c2[0] * u + c2[1] * v
    t = q @ axis
    height = float(t.max() - t.min())
    cov = angular_coverage(P2, c2)
    return dict(center=center, axis=axis, height=height, rms=rms, coverage=cov,
               n=len(pts))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments-dir", required=True, help="dir of per-barrel segment clouds")
    ap.add_argument("--scene", default=None, help="scene dir for gt.json (default: segments parent)")
    ap.add_argument("--radius", type=float, default=0.286, help="drum radius m (200L=0.286)")
    ap.add_argument("--height", type=float, default=0.85, help="prior drum height m (200L~0.85)")
    ap.add_argument("--hints", default=None, help="JSON {stem: [[p1],[p2]]} axis hints")
    ap.add_argument("--ransac", action="store_true",
                    help="first extract the dominant R-cylinder from each (coarse) crop, "
                         "then fit only its inliers — for boxes that caught clutter/neighbours")
    ap.add_argument("--ransac-tol", type=float, default=0.035, help="R-shell inlier tol (m)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--source", default="real_survey_lidar (CloudCompare segment + radius-locked fit)")
    args = ap.parse_args()

    scene_dir = args.scene or os.path.dirname(os.path.normpath(args.segments_dir))
    scene = os.path.basename(os.path.normpath(scene_dir))
    out = args.out or os.path.join(scene_dir, "gt.json")
    hints = json.load(open(args.hints)) if args.hints and os.path.isfile(args.hints) else {}

    files = sorted(f for f in glob.glob(os.path.join(args.segments_dir, "*"))
                   if os.path.isfile(f) and not f.endswith(".json"))
    if not files:
        sys.exit(f"no segment files in {args.segments_dir}")

    barrels = []
    for i, f in enumerate(files):
        stem = os.path.splitext(os.path.basename(f))[0]
        pts = load_points(f)
        if len(pts) < 20:
            print(f"  {stem}: only {len(pts)} pts — skipped")
            continue
        nfull = len(pts)
        if args.ransac and stem not in hints:
            mask = extract_cylinder_ransac(pts, args.radius, tol=args.ransac_tol)
            if mask.sum() >= 20:
                pts = pts[mask]
        fit = fit_segment(pts, args.radius, hints.get(stem))
        c = fit["center"]; a = fit["axis"]
        occ = round(1.0 - fit["coverage"], 2)
        src = "hint-axis" if stem in hints else ("ransac" if args.ransac else "auto-axis")
        print(f"  {stem}: n={fit['n']:5d}/{nfull} {src}  axis=[{a[0]:+.2f} {a[1]:+.2f} {a[2]:+.2f}]"
              f"  rms={fit['rms']*1000:5.1f}mm  cover={fit['coverage']:.2f} h={fit['height']:.2f}m")
        barrels.append(dict(
            id=i, radius_m=args.radius,
            axis=[round(float(x), 4) for x in a],
            center=[round(float(x), 4) for x in c],
            height_m=round(fit["height"], 3),
            occlusion_frac=occ,
            fit_rms_m=round(fit["rms"], 4),
        ))

    gt = dict(scene=scene, source=args.source, sensor="survey_lidar", units="m",
              frame="local_meters (de-offset site coords; z up)", barrels=barrels)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    json.dump(gt, open(out, "w"), indent=2)
    print(f"\nwrote {len(barrels)} barrel(s) -> {out}")


if __name__ == "__main__":
    main()
