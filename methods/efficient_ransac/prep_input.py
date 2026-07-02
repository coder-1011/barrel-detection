#!/usr/bin/env python3
"""
Prepare the CGAL Efficient-RANSAC input: an ASCII "x y z nx ny nz" file in
METERS. CGAL needs oriented normals. We estimate them with Open3D (the same
hybrid radius+knn that works well on this small-radius barrel) and orient them
toward the sensor at the origin.

Loads scan000.pcd (m) or scan000.3d (cm->m, first 3 cols).

Usage:
  python3 prep_input.py --scene data/synth/synth_half --out /tmp/in.xyzn
"""
import argparse
import os
import sys

import numpy as np
import open3d as o3d


def load_cloud_m(scene_dir):
    pcd_path = os.path.join(scene_dir, "scan000.pcd")
    if os.path.isfile(pcd_path):
        pcd = o3d.io.read_point_cloud(pcd_path)
        if len(pcd.points):
            return pcd
    d3 = os.path.join(scene_dir, "scan000.3d")
    if os.path.isfile(d3):
        xyz = np.loadtxt(d3)[:, :3] / 100.0
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(xyz)
        return pcd
    sys.exit(f"no scan000.pcd or scan000.3d in {scene_dir}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--radius", type=float, default=0.02, help="normal search radius (m)")
    ap.add_argument("--max-nn", type=int, default=30)
    args = ap.parse_args()

    pcd = load_cloud_m(args.scene)
    pcd.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(
        radius=args.radius, max_nn=args.max_nn))
    pcd.orient_normals_towards_camera_location([0.0, 0.0, 0.0])
    xyz = np.asarray(pcd.points)
    nrm = np.asarray(pcd.normals)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    np.savetxt(args.out, np.hstack([xyz, nrm]), fmt="%.6f")
    print(f"wrote {len(xyz)} pts with normals -> {args.out}")


if __name__ == "__main__":
    main()
