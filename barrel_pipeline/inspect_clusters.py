#!/usr/bin/env python3
"""
Cluster the captured cloud and print/display per-cluster geometry,
so we can see where the barrel actually is and design a crop box.

Pipeline:
  1. voxel-downsample for speed
  2. RANSAC-remove the dominant plane (usually a wall or floor)
  3. DBSCAN cluster the remainder
  4. print bounding box, size, and centroid for each cluster
  5. visualize coloured clusters

Usage:
  python3 inspect_clusters.py --pcd data/scan000.pcd
"""
import argparse
import numpy as np
import open3d as o3d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pcd", required=True)
    ap.add_argument("--voxel", type=float, default=0.005, help="voxel size (m)")
    ap.add_argument("--plane-thresh", type=float, default=0.01,
                    help="RANSAC plane inlier distance (m)")
    ap.add_argument("--remove-planes", type=int, default=2,
                    help="how many dominant planes to remove before clustering")
    ap.add_argument("--eps", type=float, default=0.02,
                    help="DBSCAN neighborhood radius (m)")
    ap.add_argument("--min-pts", type=int, default=30,
                    help="DBSCAN min cluster points")
    args = ap.parse_args()

    pcd = o3d.io.read_point_cloud(args.pcd)
    print(f"loaded {len(pcd.points)} pts")

    pcd = pcd.voxel_down_sample(args.voxel)
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
    if pts.shape[0] < 30:
        print("nothing left to cluster")
        return

    labels = np.array(rest.cluster_dbscan(eps=args.eps, min_points=args.min_pts,
                                          print_progress=False))
    n_clusters = labels.max() + 1
    print(f"\n{n_clusters} cluster(s) (label -1 = noise: {(labels==-1).sum()} pts)\n")
    print(f"{'id':>3} {'n':>6}  {'cx':>7} {'cy':>7} {'cz':>7}  "
          f"{'dx':>5} {'dy':>5} {'dz':>5}  approx_diam")
    for k in range(n_clusters):
        m = labels == k
        sub = pts[m]
        c = sub.mean(0)
        mn = sub.min(0)
        mx = sub.max(0)
        d = mx - mn
        approx_diam = min(d[0], d[2]) * 100  # cm; smaller of horizontal extents
        print(f"{k:>3} {m.sum():>6}  "
              f"{c[0]*100:>6.1f}cm {c[1]*100:>6.1f}cm {c[2]*100:>6.1f}cm  "
              f"{d[0]*100:>4.1f} {d[1]*100:>4.1f} {d[2]*100:>4.1f}cm  ~{approx_diam:.1f}cm")

    # color by label and visualize
    colors = np.zeros((len(labels), 3))
    if n_clusters > 0:
        cmap = (np.random.RandomState(7).rand(n_clusters, 3) * 0.7 + 0.3)
        for k in range(n_clusters):
            colors[labels == k] = cmap[k]
    colors[labels == -1] = [0.4, 0.4, 0.4]
    rest.colors = o3d.utility.Vector3dVector(colors)
    o3d.visualization.draw_geometries(
        [rest, o3d.geometry.TriangleMesh.create_coordinate_frame(size=0.1)],
        window_name="clusters (after plane removal)",
        zoom=0.6, front=[0, 0, -1], lookat=[0, 0, 0.7], up=[0, -1, 0],
    )


if __name__ == "__main__":
    main()
