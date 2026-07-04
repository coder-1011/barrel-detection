#!/usr/bin/env python3
"""BarrelNet full-scene drum detector (the method-contract entry point).

Pipeline:
  1. sliding-window fixed-radius RANSAC proposer over the cloud (generalized
     from data/real/station1_pit_barrels/candidates/tools/find_drums.py)
  2. per-proposal shell patch -> BarrelNet pose (TTA ensemble over random
     subsamples + z-rotations) -> radius-locked circle-fit center (hybrid;
     falls back to the net's point-on-axis on sparse patches)
  3. re-score the refined cylinder against the whole cloud (inliers with
     radial normals / angular coverage / axial extent), gate, NMS
  4. predictions.json in the project schema (meters)

The radius is a fixed prior (200 L drum, r = 0.286 m by default) — BarrelNet
regresses pose only.

  .venv/bin/python methods/barrelnet/detect.py \
      --scene data/real/station1_pit_barrels \
      --ckpt methods/barrelnet/runs/a100/best.pt \
      --out methods/barrelnet/results/station1_pit_barrels/predictions.json
"""
import argparse
import os
import sys
import time

import numpy as np
import open3d as o3d
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
MASTERS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(MASTERS, "common"))
sys.path.insert(0, HERE)
from eval_schema import Detection, save_pred  # noqa: E402
from fit_from_segments import plane_basis, angular_coverage  # noqa: E402
from infer import load_models, predict_patch, refine_center  # noqa: E402


def load_scene(scene_dir):
    pcd = os.path.join(scene_dir, "scan000.pcd")
    if os.path.exists(pcd):
        return np.asarray(o3d.io.read_point_cloud(pcd).points)
    p3d = os.path.join(scene_dir, "scan000.3d")
    if os.path.exists(p3d):
        return np.loadtxt(p3d)[:, :3] / 100.0      # 3DTK cm -> m
    sys.exit(f"no scan000.pcd / scan000.3d in {scene_dir}")


def cyl_stats(pts, N, center, axis, R, shell=0.025, ndot=0.75, max_len=1.4):
    """Inlier count / angular coverage / axial extent of a fixed-R cylinder."""
    d = pts - center
    t = d @ axis
    perp = d - np.outer(t, axis)
    rd = np.linalg.norm(perp, axis=1)
    m = (np.abs(rd - R) < shell) & (np.abs(t) < max_len / 2)
    if m.sum() < 10:
        return 0, 0.0, 0.0
    rdir = perp[m] / rd[m, None]
    ok = np.abs(np.einsum("ij,ij->i", rdir, N[m])) > ndot
    idx = np.where(m)[0][ok]
    if len(idx) < 10:
        return 0, 0.0, 0.0
    u, v = plane_basis(axis)
    q = pts[idx] - center
    P2 = np.column_stack([q @ u, q @ v])
    cov = float(angular_coverage(P2, np.zeros(2)))
    ti = t[idx]
    return int(len(idx)), cov, float(ti.max() - ti.min())


def propose(pts, N, R, iters, min_win_inl, rng):
    """Sliding-window fixed-R RANSAC from point-pair normals -> raw proposals
    (center, axis, inlier index arrays). Window geometry scales with R."""
    win, step = 1.9 * R, 1.2 * R
    lo, hi = pts.min(0), pts.max(0)
    cands = []
    for cx in np.arange(lo[0], hi[0] + step, step):
        for cy in np.arange(lo[1], hi[1] + step, step):
            m = (np.abs(pts[:, 0] - cx) < win) & (np.abs(pts[:, 1] - cy) < win)
            if m.sum() < 250:
                continue
            W, WN, widx = pts[m], N[m], np.where(m)[0]
            n = len(W)
            best = (0, None)
            for _ in range(iters):
                i, j = rng.integers(0, n, 2)
                ax = np.cross(WN[i], WN[j])
                na = np.linalg.norm(ax)
                if na < 0.3:
                    continue
                ax /= na
                for s in (1, -1):
                    a0 = W[i] + s * R * WN[i]
                    d = W - a0
                    perp = d - np.outer(d @ ax, ax)
                    rd = np.linalg.norm(perp, axis=1)
                    rdir = perp / np.where(rd[:, None] < 1e-9, 1e-9, rd[:, None])
                    inl = (np.abs(rd - R) < 0.025) & \
                          (np.abs(np.einsum("ij,ij->i", rdir, WN)) > 0.75)
                    c = int(inl.sum())
                    if c > best[0]:
                        best = (c, (ax.copy(), a0.copy(), inl))
            if best[0] < min_win_inl:
                continue
            ax, a0, inl = best[1]
            P = W[inl]
            d = P - a0
            center = a0 + ax * float((d @ ax).mean())
            cands.append(dict(center=center, axis=ax, n_inl=best[0],
                              patch_idx=widx[inl]))
    # greedy merge of overlapping window hits
    cands.sort(key=lambda c: -c["n_inl"])
    kept = []
    for c in cands:
        if all(np.linalg.norm(c["center"] - k["center"]) > 1.2 * R for k in kept):
            kept.append(c)
    return kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ckpt", default=os.path.join(HERE, "runs/a100/best.pt"),
                    help="checkpoint path (comma-separated to ensemble)")
    ap.add_argument("--radius", type=float, default=0.286)
    ap.add_argument("--tta", type=int, default=32)
    ap.add_argument("--npoints", type=int, default=512)
    ap.add_argument("--iters", type=int, default=800, help="RANSAC iters/window")
    ap.add_argument("--min-win-inl", type=int, default=100,
                    help="min window RANSAC inliers to keep a proposal")
    ap.add_argument("--min-inl", type=int, default=120,
                    help="final gate: min cloud inliers of the refined cylinder")
    ap.add_argument("--min-cov", type=float, default=0.25,
                    help="final gate: min angular coverage")
    args = ap.parse_args()
    R = args.radius
    t0 = time.time()

    pts = load_scene(args.scene)
    pc = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(pts))
    pc.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=0.2 * R,
                                                             max_nn=30))
    N = np.asarray(pc.normals)
    print(f"{len(pts):,} pts, normals done", flush=True)

    rng = np.random.default_rng(0)
    props = propose(pts, N, R, args.iters, args.min_win_inl, rng)
    print(f"{len(props)} merged proposals", flush=True)

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    models = load_models(args.ckpt.split(","), dev)

    dets = []
    for p in props:
        # shell patch around the proposal (looser than the RANSAC inlier band)
        d = pts - p["center"]
        t = d @ p["axis"]
        perp = d - np.outer(t, p["axis"])
        rd = np.linalg.norm(perp, axis=1)
        m = (np.abs(rd - R) < 0.05) & (np.abs(t) < 0.75)
        patch = pts[m].astype(np.float32)
        if len(patch) < 60:
            continue
        ax, poa = predict_patch(models, patch, args.npoints, dev, tta=args.tta)
        center, _ = refine_center(patch, ax, R, poa)
        n_inl, cov, ext = cyl_stats(pts, N, center, ax, R)
        if n_inl < args.min_inl or cov < args.min_cov or not 0.15 < ext < 1.4:
            continue
        dets.append(dict(center=center, axis=ax, n_inl=n_inl, cov=cov, ext=ext))

    # NMS on the refined poses (two proposals can converge onto one drum)
    dets.sort(key=lambda x: -x["n_inl"])
    kept = []
    for x in dets:
        if all(np.linalg.norm(x["center"] - k["center"]) > R for k in kept):
            kept.append(x)
    print(f"{len(kept)} detections after refine+gate+NMS", flush=True)

    detections = [Detection(radius_m=R,
                            axis=[float(a) for a in x["axis"]],
                            center=[float(c) for c in x["center"]],
                            extent_m=x["ext"], score=x["cov"],
                            lateral_pts=x["n_inl"]) for x in kept]
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    save_pred(args.out, os.path.basename(os.path.abspath(args.scene)),
              "barrelnet", detections, runtime_s=time.time() - t0)
    print(f"wrote {args.out}  ({len(detections)} detections, "
          f"{time.time() - t0:.1f} s)")


if __name__ == "__main__":
    main()
