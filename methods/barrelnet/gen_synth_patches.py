#!/usr/bin/env python3
"""Generate randomized synthetic single-drum patches for the BarrelNet-style
pose regressor. Pure numpy — runs fully offline.

Each patch: partial wall (+ optional cap / ground clutter) of a r=0.286 m drum at a
random orientation, seen as a scan-line grid (~survey-LiDAR spacing) with noise and
optional burial clipping. Labels: unit axis + the point on the axis nearest the
patch centroid (both in raw meters; the trainer normalizes).

Usage:
  .venv/bin/python methods/barrelnet/gen_synth_patches.py \
      --out data/synth_patches/train --n 8000 --seed 0
"""
import argparse, os
import numpy as np

R_DRUM = 0.286
H_DRUM = 0.85


def rand_unit(rng):
    v = rng.normal(size=3)
    return v / np.linalg.norm(v)


def make_patch(rng):
    axis = rand_unit(rng)
    # local frame
    tmp = np.array([0.0, 0.0, 1.0]) if abs(axis[2]) < 0.95 else np.array([1.0, 0.0, 0.0])
    u = np.cross(axis, tmp); u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    center = rng.uniform(-0.3, 0.3, 3)

    # visible arc: 60..300 deg around a random azimuth (single-viewpoint partial view)
    arc = np.radians(rng.uniform(60, 300))
    th0 = rng.uniform(0, 2 * np.pi)
    # scan grid spacing ~ survey lidar (8..25 mm), with jitter
    step = rng.uniform(0.008, 0.025)
    n_th = max(6, int(arc * R_DRUM / step))
    n_t = max(6, int(H_DRUM / step))
    th = th0 + (np.arange(n_th) + rng.uniform(0, 1, n_th)) / n_th * arc
    tt = (np.arange(n_t) + rng.uniform(0, 1, n_t)) / n_t * H_DRUM - H_DRUM / 2
    TH, TT = np.meshgrid(th, tt)
    TH, TT = TH.ravel(), TT.ravel()
    # random dropout (occlusion holes)
    keep = rng.uniform(size=len(TH)) > rng.uniform(0.0, 0.35)
    TH, TT = TH[keep], TT[keep]
    pts = (center + np.outer(TT, axis)
           + R_DRUM * (np.outer(np.cos(TH), u) + np.outer(np.sin(TH), v)))

    # optional cap disc (overhead views see caps)
    if rng.uniform() < 0.4:
        n_cap = int(len(pts) * rng.uniform(0.1, 0.4))
        rr = R_DRUM * np.sqrt(rng.uniform(0, 1, n_cap))
        aa = rng.uniform(0, 2 * np.pi, n_cap)
        s = 1 if rng.uniform() < 0.5 else -1
        cap = (center + s * (H_DRUM / 2) * axis
               + rr[:, None] * (np.cos(aa)[:, None] * u + np.sin(aa)[:, None] * v))
        pts = np.vstack([pts, cap])

    # burial: clip below a near-horizontal random plane through the drum
    if rng.uniform() < 0.6:
        gn = np.array([0, 0, 1.0]) + rng.normal(0, 0.15, 3)
        gn /= np.linalg.norm(gn)
        g0 = center + rng.uniform(-0.35, 0.1) * gn
        pts = pts[(pts - g0) @ gn > 0]

    # ground/sand clutter near the bottom of what's left
    if rng.uniform() < 0.7 and len(pts) > 50:
        n_cl = int(len(pts) * rng.uniform(0.05, 0.35))
        base = pts[rng.integers(0, len(pts), n_cl)]
        clutter = base + rng.normal(0, 0.12, (n_cl, 3)) * np.array([1, 1, 0.25])
        pts = np.vstack([pts, clutter])

    pts += rng.normal(0, rng.uniform(0.002, 0.015), pts.shape)   # sensor noise
    if len(pts) < 80:
        return None
    # label: axis + nearest point on axis to the centroid
    cen = pts.mean(0)
    p_on_axis = center + ((cen - center) @ axis) * axis
    return pts.astype(np.float32), axis.astype(np.float32), p_on_axis.astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=8000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--npoints", type=int, default=512, help="points stored per patch")
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    os.makedirs(args.out, exist_ok=True)

    P = np.zeros((args.n, args.npoints, 3), np.float32)
    A = np.zeros((args.n, 3), np.float32)
    C = np.zeros((args.n, 3), np.float32)
    made = 0
    while made < args.n:
        r = make_patch(rng)
        if r is None:
            continue
        pts, ax, ctr = r
        idx = rng.integers(0, len(pts), args.npoints) if len(pts) < args.npoints \
            else rng.choice(len(pts), args.npoints, replace=False)
        P[made], A[made], C[made] = pts[idx], ax, ctr
        made += 1
        if made % 1000 == 0:
            print(f"{made}/{args.n}", flush=True)
    out = os.path.join(args.out, f"patches_s{args.seed}.npz")
    np.savez_compressed(out, points=P, axis=A, point_on_axis=C)
    print("wrote", out, P.shape)


if __name__ == "__main__":
    main()
