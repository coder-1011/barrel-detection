#!/usr/bin/env python3
"""
Visualize a point cloud, optionally overlaying detected cylinders. Overlays
come from either source:
  --pred <predictions.json>  project-standard schema (METERS; any method)
  --cylinders <cylinder.2d>  raw 3DTK detectCylinder output (CENTIMETERS)
and you can add --gt <gt.json> to draw the ground-truth cylinder for comparison.

Colors: prediction = red, ground truth = green.
Cloud is meters; --pcd accepts a .pcd (m) or a .3d (cm, auto /100).

Usage:
  # any method's predictions vs ground truth (the common case now):
  python3 common/view_cloud.py \
      --pcd  data/synth/data_synth_half/scan000.pcd \
      --pred methods/ransac_cylinder/results/data_synth_half/predictions.json \
      --gt   data/synth/data_synth_half/gt.json

  # legacy 3DTK cylinder.2d overlay:
  python3 common/view_cloud.py --pcd data/scan000.pcd \
                               --cylinders .../detectCylinder/cylinder.2d
"""
import argparse
import json
import os
import numpy as np
import open3d as o3d


def load_cloud(path):
    """Load a cloud in meters from a .pcd (m) or .3d (cm, first 3 cols)."""
    if path.endswith(".3d"):
        xyz = np.loadtxt(path)[:, :3] / 100.0
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(xyz)
        return pcd
    return o3d.io.read_point_cloud(path)


def parse_predictions(path):
    """Read predictions.json (meters) -> list of dicts with start/end/radius (m)."""
    with open(path) as f:
        d = json.load(f)
    out = []
    for det in d.get("detections", []):
        c = np.asarray(det["center"], float)
        a = np.asarray(det["axis"], float)
        a = a / (np.linalg.norm(a) + 1e-12)
        ext = det.get("extent_m") or 0.4
        out.append(dict(radius=det["radius_m"],
                        start=c - a * ext / 2.0,
                        end=c + a * ext / 2.0))
    return out


def parse_gt(path):
    """Read gt.json (meters) -> list of dicts with start/end/radius (m)."""
    with open(path) as f:
        d = json.load(f)
    out = []
    for b in d.get("barrels", []):
        c = np.asarray(b["center"], float)
        a = np.asarray(b["axis"], float)
        a = a / (np.linalg.norm(a) + 1e-12)
        h = b.get("height_m") or 0.4
        out.append(dict(radius=b["radius_m"],
                        start=c - a * h / 2.0,
                        end=c + a * h / 2.0))
    return out


def parse_cylinder_2d(path):
    """Parse the cylinder.2d file written by detectCylinder.cc.
    Layout per non-comment line, ';'-separated:
      idx ; radius ; ax ay az ; sx sy sz ; ex ey ez ; px py pz
    """
    out = []
    with open(path) as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = [p.strip() for p in s.split(";")]
            if len(parts) < 5:
                continue
            radius = float(parts[1])
            axis  = np.array([float(x) for x in parts[2].split()])
            start = np.array([float(x) for x in parts[3].split()])
            end   = np.array([float(x) for x in parts[4].split()])
            out.append(dict(radius=radius, axis=axis, start=start, end=end))
    return out


def cylinder_mesh(start, end, radius, color=(1.0, 0.2, 0.2)):
    """Triangle mesh for an arbitrary-axis cylinder, colored."""
    v = end - start
    h = float(np.linalg.norm(v))
    if h < 1e-6:
        return None
    mesh = o3d.geometry.TriangleMesh.create_cylinder(radius=radius, height=h, resolution=40)
    mesh.compute_vertex_normals()
    mesh.paint_uniform_color(color)
    # default cylinder is centered at origin along +Z.
    direction = v / h
    z = np.array([0.0, 0.0, 1.0])
    cross = np.cross(z, direction)
    s = np.linalg.norm(cross)
    c = float(np.dot(z, direction))
    if s < 1e-9:
        R = np.eye(3) if c > 0 else -np.eye(3)
    else:
        K = np.array([[0, -cross[2], cross[1]],
                      [cross[2], 0, -cross[0]],
                      [-cross[1], cross[0], 0]])
        R = np.eye(3) + K + K @ K * ((1 - c) / (s * s))
    mesh.rotate(R, center=(0, 0, 0))
    mesh.translate(start + v / 2)  # center -> midpoint of axis segment
    # Render as wireframe-like by also returning a LineSet outline
    return mesh


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pcd", required=True, help="cloud file: .pcd (m) or .3d (cm)")
    ap.add_argument("--pred", help="predictions.json (meters, any method)")
    ap.add_argument("--gt", help="gt.json (meters) -> drawn green for comparison")
    ap.add_argument("--cylinders", help="legacy 3DTK cylinder.2d (cm)")
    ap.add_argument("--scale-cyl", type=float, default=0.01,
                    help="multiply cylinder.2d coords by this (cm->m: 0.01)")
    args = ap.parse_args()

    pcd = load_cloud(args.pcd)
    if len(pcd.points) == 0:
        raise SystemExit(f"empty cloud: {args.pcd}")
    print(f"loaded {len(pcd.points)} points from {args.pcd}")

    geoms = [pcd, o3d.geometry.TriangleMesh.create_coordinate_frame(size=0.1)]

    if args.gt:
        gts = parse_gt(args.gt)
        print(f"ground truth: {len(gts)} barrel(s) from {args.gt}")
        for i, c in enumerate(gts):
            print(f"  GT[{i}] r={c['radius']*100:.2f}cm")
            m = cylinder_mesh(c["start"], c["end"], c["radius"],
                              color=(0.2, 0.8, 0.2))
            if m is not None:
                geoms.append(m)

    if args.pred:
        preds = parse_predictions(args.pred)
        print(f"predictions: {len(preds)} cylinder(s) from {args.pred}")
        for i, c in enumerate(preds):
            print(f"  PRED[{i}] r={c['radius']*100:.2f}cm")
            m = cylinder_mesh(c["start"], c["end"], c["radius"],
                              color=(0.9, 0.2, 0.2))
            if m is not None:
                geoms.append(m)

    if args.cylinders:
        cyls = parse_cylinder_2d(args.cylinders)
        print(f"loaded {len(cyls)} cylinder(s) from {args.cylinders}")
        for i, c in enumerate(cyls):
            print(f"  [{i}] r={c['radius']:.2f}cm  start={c['start']}  end={c['end']}")
            m = cylinder_mesh(
                c["start"] * args.scale_cyl,
                c["end"]   * args.scale_cyl,
                c["radius"] * args.scale_cyl,
            )
            if m is not None:
                geoms.append(m)

    o3d.visualization.draw_geometries(
        geoms, window_name="cloud + cylinders (pred=red, gt=green)",
        zoom=0.7, front=[0, 0, -1], lookat=[0, 0, 0.5], up=[0, -1, 0],
    )


if __name__ == "__main__":
    main()
