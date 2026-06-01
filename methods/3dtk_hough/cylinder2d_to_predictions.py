#!/usr/bin/env python3
"""
Convert a 3DTK detectCylinder `cylinder.2d` (cm) into the project-standard
predictions.json (meters, camera_optical frame). See common/eval_schema.py.

cylinder.2d line layout (';'-separated, cm):
  idx ; radius ; ax ay az ; sx sy sz ; ex ey ez ; px py pz

Usage (from ~/masters):
  python3 methods/3dtk_hough/cylinder2d_to_predictions.py \
      --in   methods/3dtk_hough/results/data2_crop/normals_o3d/detectCylinder/cylinder.2d \
      --scene data2_crop \
      --out  methods/3dtk_hough/results/data2_crop/predictions.json \
      --min-extent-cm 10        # phantom filter on axis extent
"""
import argparse
import os
import re
import sys

import numpy as np

# detectCylinder prints "idx(lateralPts, inlierPts);..." to stdout but writes a
# bare "idx;..." to cylinder.2d. We read geometry from the file (clean spacing)
# and recover the per-index lateral-point count from the run log when given.
_COUNTS_RE = re.compile(r"\((\d+)\s*,\s*(\d+)\)")
_LOG_LINE_RE = re.compile(r"^\s*(\d+)\((\d+)\s*,\s*(\d+)\)\s*;")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "common"))
from eval_schema import Detection, save_pred  # noqa: E402


def parse_cylinder_2d(path):
    out = []
    with open(path) as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = [p.strip() for p in s.split(";")]
            if len(parts) < 5:
                continue
            idx_m = re.match(r"\s*(\d+)", parts[0])
            idx = int(idx_m.group(1)) if idx_m else None
            m = _COUNTS_RE.search(parts[0])
            lateral = int(m.group(1)) if m else None
            radius = float(parts[1])
            axis = [float(x) for x in parts[2].split()]
            start = np.array([float(x) for x in parts[3].split()])
            end = np.array([float(x) for x in parts[4].split()])
            out.append((idx, radius, axis, start, end, lateral))
    return out


def parse_log_counts(path):
    """Map CylinderIndex -> lateralSurfacePoints from a detectCylinder run log."""
    counts = {}
    with open(path) as f:
        for line in f:
            m = _LOG_LINE_RE.match(line)
            if m:
                counts[int(m.group(1))] = int(m.group(2))
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="cylinder.2d path")
    ap.add_argument("--scene", required=True)
    ap.add_argument("--out", required=True, help="predictions.json path")
    ap.add_argument("--method", default="3dtk_hough")
    ap.add_argument("--runtime-s", type=float, default=None)
    ap.add_argument("--log", default=None,
                    help="run.log to recover per-index lateral-point counts")
    ap.add_argument("--min-extent-cm", type=float, default=0.0,
                    help="drop detections whose axis extent < this (phantom filter)")
    args = ap.parse_args()

    log_counts = (parse_log_counts(args.log)
                  if args.log and os.path.isfile(args.log) else {})

    dets = []
    for idx, radius, axis, start, end, lateral in parse_cylinder_2d(args.inp):
        extent_cm = float(np.linalg.norm(end - start))
        if extent_cm < args.min_extent_cm:
            continue
        center = (start + end) / 2.0
        dets.append(Detection(
            radius_m=radius / 100.0,
            axis=axis,
            center=(center / 100.0).tolist(),
            extent_m=extent_cm / 100.0,
            lateral_pts=(lateral if lateral is not None else log_counts.get(idx)),
        ))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    save_pred(args.out, args.scene, args.method, dets, runtime_s=args.runtime_s)
    print(f"wrote {len(dets)} detection(s) -> {args.out}")


if __name__ == "__main__":
    main()
