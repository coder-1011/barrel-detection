#!/usr/bin/env python3
"""
Isolate barrel cluster(s) from a captured PCD and emit a 3DTK uos scan
directory containing only those clusters' points (full resolution).

Pipeline:
  1. voxel-downsample for speed
  2. RANSAC-remove the dominant planes (wall, floor)
  3. DBSCAN cluster the remainder
  4. keep ALL clusters matching barrel priors (handles multi-barrel scenes)
  5. project each kept cluster back to full-res via KDTree -- a full-res
     point is kept iff it lies within --label-crop-dist of any downsampled
     cluster point. Replaces the previous AABB+margin crop, which leaked
     wall/floor points near the box corners.
  6. write data*_crop/scan000.{pcd,3d,pose} with all kept clusters merged

Usage:
  python3 crop_barrel.py --pcd data2/scan000.pcd --out data2_crop
"""
import argparse
import os
import sys
import numpy as np
import open3d as o3d


def write_pcd_ascii(path, xyz_m):
    n = xyz_m.shape[0]
    with open(path, "w") as f:
        f.write(
            "# .PCD v0.7 - Point Cloud Data\n"
            "VERSION 0.7\nFIELDS x y z\nSIZE 4 4 4\nTYPE F F F\nCOUNT 1 1 1\n"
            f"WIDTH {n}\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\n"
            f"POINTS {n}\nDATA ascii\n"
        )
        np.savetxt(f, xyz_m, fmt="%.6f")


def full_res_mask_from_cluster(cluster_xyz, full_tree, n_full, dist_thresh):
    """Mark every full-res point within dist_thresh of any cluster point.
    full_tree is an o3d.geometry.KDTreeFlann built on the full cloud."""
    mask = np.zeros(n_full, dtype=bool)
    for p in cluster_xyz:
        [k, idx, _] = full_tree.search_radius_vector_3d(p, dist_thresh)
        if k > 0:
            mask[np.asarray(idx, dtype=np.int64)] = True
    return mask


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pcd", required=True, help="input PCD (meters)")
    ap.add_argument("--out", required=True, help="output scan dir")
    ap.add_argument("--voxel", type=float, default=0.005, help="voxel size (m)")
    ap.add_argument("--plane-thresh", type=float, default=0.01,
                    help="RANSAC plane inlier distance (m)")
    ap.add_argument("--remove-planes", type=int, default=2,
                    help="dominant planes to remove before clustering")
    ap.add_argument("--eps", type=float, default=0.02, help="DBSCAN radius (m)")
    ap.add_argument("--min-pts", type=int, default=30, help="DBSCAN min cluster pts")
    ap.add_argument("--target-width", type=float, default=0.085,
                    help="expected barrel diameter, m (matched against max(dx,dz))")
    ap.add_argument("--width-tol", type=float, default=0.03,
                    help="tolerance around --target-width, m")
    ap.add_argument("--max-depth-ratio", type=float, default=0.7,
                    help="min(dx,dz)/max(dx,dz) upper bound -- "
                         "barrel viewed from one side has depth << diameter")
    ap.add_argument("--min-height", type=float, default=0.10,
                    help="cluster height lower bound, m (dy)")
    ap.add_argument("--cz-min", type=float, default=0.40,
                    help="cluster centroid z min, m")
    ap.add_argument("--cz-max", type=float, default=1.00,
                    help="cluster centroid z max, m")
    ap.add_argument("--label-crop-dist", type=float, default=None,
                    help="full-res point kept iff within this distance (m) "
                         "of any cluster point; defaults to 1.5 * voxel")
    args = ap.parse_args()

    if args.label_crop_dist is None:
        args.label_crop_dist = 1.5 * args.voxel

    pcd_full = o3d.io.read_point_cloud(args.pcd)
    print(f"loaded {len(pcd_full.points)} pts from {args.pcd}")

    pcd = pcd_full.voxel_down_sample(args.voxel)
    print(f"after voxel({args.voxel}m): {len(pcd.points)} pts")

    rest = pcd
    for i in range(args.remove_planes):
        if len(rest.points) < 100:
            break
        plane, inliers = rest.segment_plane(distance_threshold=args.plane_thresh,
                                            ransac_n=3, num_iterations=500)
        a, b, c, d = plane
        print(f"plane[{i}]: {a:+.2f}x {b:+.2f}y {c:+.2f}z {d:+.2f}=0  "
              f"({len(inliers)} inliers)")
        rest = rest.select_by_index(inliers, invert=True)

    pts = np.asarray(rest.points)
    print(f"after plane removal: {pts.shape[0]} pts")
    if pts.shape[0] < args.min_pts:
        sys.exit("not enough points left to cluster")

    labels = np.array(rest.cluster_dbscan(eps=args.eps, min_points=args.min_pts,
                                          print_progress=False))
    n_clusters = labels.max() + 1
    print(f"\n{n_clusters} cluster(s)\n")

    kept = []
    print(f"{'id':>3} {'n':>6}  {'cx':>7} {'cy':>7} {'cz':>7}  "
          f"{'dx':>5} {'dy':>5} {'dz':>5}  match")
    for k in range(n_clusters):
        m = labels == k
        sub = pts[m]
        c = sub.mean(0)
        d = sub.max(0) - sub.min(0)
        diameter = max(d[0], d[2])  # front-on view: max horizontal extent ~= diameter
        depth = min(d[0], d[2])     # the other extent ~= front-shell depth
        keep = (abs(diameter - args.target_width) <= args.width_tol
                and (depth / diameter if diameter > 0 else 1.0) <= args.max_depth_ratio
                and d[1] >= args.min_height
                and args.cz_min <= c[2] <= args.cz_max)
        marker = "  <-" if keep else ""
        print(f"{k:>3} {m.sum():>6}  "
              f"{c[0]*100:>6.1f}cm {c[1]*100:>6.1f}cm {c[2]*100:>6.1f}cm  "
              f"{d[0]*100:>4.1f} {d[1]*100:>4.1f} {d[2]*100:>4.1f}cm{marker}")
        if keep:
            kept.append((k, sub))

    if not kept:
        sys.exit("no cluster matched barrel priors; "
                 "relax --width-tol / --max-depth-ratio / --min-height / --cz-*")
    print(f"\nkept {len(kept)} cluster(s): {[cid for cid, _ in kept]}")

    # Project each kept downsampled cluster back to full-res by keeping every
    # full-res point within --label-crop-dist of any cluster point. Avoids the
    # AABB-corner contamination of the previous bounding-box crop.
    full_xyz = np.asarray(pcd_full.points)
    full_tree = o3d.geometry.KDTreeFlann(pcd_full)
    combined_mask = np.zeros(len(full_xyz), dtype=bool)
    for cid, sub in kept:
        m = full_res_mask_from_cluster(sub, full_tree, len(full_xyz),
                                       args.label_crop_dist)
        print(f"  cluster {cid}: {sub.shape[0]} downsampled -> "
              f"{m.sum()} full-res pts")
        combined_mask |= m

    xyz_m = full_xyz[combined_mask]
    print(f"\ntotal full-res points kept: {xyz_m.shape[0]}")

    os.makedirs(args.out, exist_ok=True)
    write_pcd_ascii(os.path.join(args.out, "scan000.pcd"), xyz_m)
    np.savetxt(os.path.join(args.out, "scan000.3d"), xyz_m * 100.0, fmt="%.4f")
    with open(os.path.join(args.out, "scan000.pose"), "w") as f:
        f.write("0 0 0\n0 0 0\n")
    print(f"\nwrote {args.out}/scan000.{{pcd,3d,pose}}")


if __name__ == "__main__":
    main()
