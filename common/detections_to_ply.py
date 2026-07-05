#!/usr/bin/env python3
"""
Export a method's predictions.json (+ optional gt.json) as a colored cylinder-mesh
PLY for CloudCompare — so detections can be inspected in 3D next to the scan cloud
(e.g. in the docker-3dtk-show CloudCompare/VNC stack, which reads PLY natively).

Colors: matched detections green, unmatched ("candidate") detections orange,
GT drums as thin axis rods — white if some detection matched them, crimson if missed.
Matching = the project-standard gate (common/eval_schema.match: axis<=30deg,
center-to-axis dist <=10 cm). Cylinder radii are shrunk slightly (--shrink, default
1 cm) so the real drum-wall points sit OUTSIDE the mesh and stay visible on top.

USAGE (host, .venv or system python — numpy only, no open3d):
  python3 common/detections_to_ply.py \
      --pred methods/barrelnet/results/station1_pit_barrels/predictions.json \
      --gt   data/real/station1_pit_barrels/gt.json
writes <pred-dir>/detections.ply by default; load it together with the scene's
scan000.ply in CloudCompare (both are in meters, same frame).
"""
import argparse
import json
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import eval_schema as es

GREEN = (63, 211, 127)      # detection matched to a verified GT drum
ORANGE = (224, 154, 63)     # candidate detection (no GT to check against)
WHITE = (223, 233, 241)     # GT drum that some detection matched
CRIMSON = (228, 88, 110)    # GT drum missed by every detection


def basis(a):
    a = np.asarray(a, float)
    a = a / np.linalg.norm(a)
    t = np.array([1.0, 0, 0]) if abs(a[0]) < 0.9 else np.array([0, 1.0, 0])
    u = np.cross(a, t); u /= np.linalg.norm(u)
    v = np.cross(a, u)
    return a, u, v


def cylinder(center, axis, r, length, color, seg=26, caps=True):
    """Closed cylinder mesh -> (verts Nx3, faces Mx3, colors Nx3 uint8)."""
    a, u, v = basis(axis)
    c = np.asarray(center, float)
    hh = length / 2.0
    ang = 2 * np.pi * np.arange(seg) / seg
    ring = np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v
    bot = c + r * ring - hh * a
    top = c + r * ring + hh * a
    verts = [bot, top]
    faces = []
    for s in range(seg):
        s1 = (s + 1) % seg
        faces += [(s, s1, seg + s), (s1, seg + s1, seg + s)]
    if caps:
        verts.append([c - hh * a, c + hh * a])
        cb, ct = 2 * seg, 2 * seg + 1
        for s in range(seg):
            s1 = (s + 1) % seg
            faces += [(cb, s1, s), (ct, seg + s, seg + s1)]
    V = np.vstack(verts)
    F = np.asarray(faces, np.int32)
    C = np.tile(np.asarray(color, np.uint8), (len(V), 1))
    return V, F, C


def write_ply(path, verts, faces, colors):
    with open(path, "wb") as f:
        f.write((
            "ply\nformat binary_little_endian 1.0\n"
            f"element vertex {len(verts)}\n"
            "property float x\nproperty float y\nproperty float z\n"
            "property uchar red\nproperty uchar green\nproperty uchar blue\n"
            f"element face {len(faces)}\n"
            "property list uchar int vertex_indices\nend_header\n").encode())
        for p, c in zip(verts.astype("<f4"), colors):
            f.write(p.tobytes() + c.tobytes())
        for tri in faces.astype("<i4"):
            f.write(struct.pack("<B", 3) + tri.tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True, help="method predictions.json")
    ap.add_argument("--gt", default=None, help="scene gt.json (for match coloring + GT rods)")
    ap.add_argument("--out", default=None, help="output PLY (default <pred-dir>/detections.ply)")
    ap.add_argument("--shrink", type=float, default=0.01,
                    help="shrink cylinder radius by this (m) so wall points stay visible")
    ap.add_argument("--max-len", type=float, default=1.2, help="cap drawn cylinder length (m)")
    ap.add_argument("--gt-rod-r", type=float, default=0.02, help="GT axis rod radius (m)")
    args = ap.parse_args()

    pred = es.load_pred(args.pred)["detections"]
    gt = es.load_gt(args.gt)["barrels"] if args.gt else []
    pairs, ugt, _ = es.match(gt, pred) if gt else ([], [], list(range(len(pred))))
    matched_det = {di for _, di in pairs}
    missed_gt = set(ugt)

    V, F, C = [], [], []
    nv = 0

    def add(v, f, c):
        nonlocal nv
        V.append(v); F.append(f + nv); C.append(c)
        nv += len(v)

    for di, d in enumerate(pred):
        length = min(d.extent_m or 0.9, args.max_len)
        col = GREEN if di in matched_det else ORANGE
        add(*cylinder(d.center, d.axis, max(d.radius_m - args.shrink, 0.02), length, col))
    for gi, g in enumerate(gt):
        col = CRIMSON if gi in missed_gt else WHITE
        rodlen = min((g.height_m or 0.9), args.max_len) + 0.24
        add(*cylinder(g.center, g.axis, args.gt_rod_r, rodlen, col, seg=10))

    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.pred)), "detections.ply")
    write_ply(out, np.vstack(V), np.vstack(F), np.vstack(C))
    n_match = len(matched_det)
    print(f"wrote {out}: {len(pred)} detections ({n_match} green/matched, "
          f"{len(pred) - n_match} orange/candidate) + {len(gt)} GT rods "
          f"({len(missed_gt)} crimson/missed), {nv} verts")


if __name__ == "__main__":
    main()
