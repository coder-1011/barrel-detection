#!/usr/bin/env python3
"""
Convert cgal_ransac stdout ("CYL r cx cy cz dx dy dz extent ninliers", meters)
into the project-standard predictions.json (meters, camera_optical frame).
See common/eval_schema.py.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "common"))
from eval_schema import Detection, save_pred  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="cgal_ransac output (CYL lines)")
    ap.add_argument("--scene", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--method", default="efficient_ransac")
    ap.add_argument("--runtime-s", type=float, default=None)
    ap.add_argument("--r-min", type=float, default=0.02, help="reject radius < this (m)")
    ap.add_argument("--r-max", type=float, default=0.20, help="reject radius > this (m)")
    args = ap.parse_args()

    dets = []
    with open(args.inp) as f:
        for line in f:
            t = line.split()
            if len(t) < 10 or t[0] != "CYL":
                continue
            r = float(t[1])
            center = [float(t[2]), float(t[3]), float(t[4])]
            axis = [float(t[5]), float(t[6]), float(t[7])]
            extent = float(t[8])
            ninl = int(t[9])
            if not (args.r_min <= r <= args.r_max):
                continue
            dets.append(Detection(radius_m=r, axis=axis, center=center,
                                  extent_m=extent, lateral_pts=ninl))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    save_pred(args.out, args.scene, args.method, dets, runtime_s=args.runtime_s)
    print(f"wrote {len(dets)} detection(s) -> {args.out}")


if __name__ == "__main__":
    main()
