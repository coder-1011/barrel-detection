#!/usr/bin/env python3
"""
Visualize a PCD point cloud, optionally overlaying detected cylinders
from 3DTK detectCylinder's cylinder.2d output.

The cloud is in meters; cylinder.2d is in centimeters (3DTK uos convention),
so we scale cylinder coords by 0.01 by default.

Usage:
  python3 view_cloud.py --pcd data/scan000.pcd
  python3 view_cloud.py --pcd data/scan000.pcd \
                        --cylinders data/detectCylinder/cylinder.2d
"""
import argparse
import numpy as np
import open3d as o3d


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
    ap.add_argument("--pcd", required=True, help="PCD file in meters")
    ap.add_argument("--cylinders", help="cylinder.2d from detectCylinder")
    ap.add_argument("--scale-cyl", type=float, default=0.01,
                    help="multiply cylinder coords by this (cm->m: 0.01)")
    args = ap.parse_args()

    pcd = o3d.io.read_point_cloud(args.pcd)
    if len(pcd.points) == 0:
        raise SystemExit(f"empty cloud: {args.pcd}")
    print(f"loaded {len(pcd.points)} points from {args.pcd}")

    geoms = [pcd, o3d.geometry.TriangleMesh.create_coordinate_frame(size=0.1)]

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
        geoms, window_name="cloud + detected cylinders",
        zoom=0.7, front=[0, 0, -1], lookat=[0, 0, 0.5], up=[0, -1, 0],
    )


if __name__ == "__main__":
    main()
