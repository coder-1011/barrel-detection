#!/usr/bin/env python3
"""
Drop-in replacement for `calc_normals` for our pipeline.

Reads a 3DTK uos scan (cm), estimates normals with Open3D using a hybrid
radius+knn search, orients them all toward the sensor at the origin, and
writes a uos_normal scan in `<in>/normals_o3d/scan000.3d`.

Why: 3DTK's calc_normals on a small-radius (8.5 cm) curved surface produces
- ~12 deg mean error vs analytical truth
- ~39% of normals flipped antipodally (no consistent orientation)
- significant chord bias toward the axis
which together kill detectCylinder. Sensor-orientation alone fixes the flip;
hybrid radius+knn keeps neighborhoods compact to limit chord bias.

Usage:
  python3 compute_normals_o3d.py --in data_synth_half_n0.2_estnorm --radius-cm 0.6 --max-nn 30
  cd ~/masters/3DTK
  bin/detectCylinder -s 0 -e 0 -f uos_normal \
      ~/masters/barrel_pipeline/data_synth_half_n0.2_estnorm/normals_o3d/
"""
import argparse, os
import numpy as np
import open3d as o3d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="indir", required=True,
                    help="dir with scan000.3d (cm, xyz only)")
    ap.add_argument("--radius-cm", type=float, default=0.6,
                    help="hybrid neighborhood radius, cm")
    ap.add_argument("--max-nn", type=int, default=30,
                    help="cap on neighbors inside the radius")
    args = ap.parse_args()

    in_path = os.path.join(args.indir, "scan000.3d")
    arr = np.loadtxt(in_path)
    xyz_cm = arr[:, :3]

    # Open3D works in whatever units you give it; keep cm throughout.
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(xyz_cm)
    pcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(
            radius=args.radius_cm, max_nn=args.max_nn))
    # Sensor sits at origin in the optical frame.
    pcd.orient_normals_towards_camera_location(np.array([0.0, 0.0, 0.0]))

    n = np.asarray(pcd.normals)
    out_dir = os.path.join(args.indir, "normals_o3d")
    os.makedirs(out_dir, exist_ok=True)
    np.savetxt(os.path.join(out_dir, "scan000.3d"),
               np.hstack([xyz_cm, n]), fmt="%.4f")
    with open(os.path.join(out_dir, "scan000.pose"), "w") as f:
        f.write("0 0 0\n0 0 0\n")
    print(f"wrote {len(n)} pts with sensor-oriented normals to {out_dir}/")


if __name__ == "__main__":
    main()
