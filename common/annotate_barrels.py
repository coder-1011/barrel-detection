#!/usr/bin/env python3
"""
Annotate barrel ground truth by clicking cap centers in an Open3D window.

For vertical drums of known size, GT reduces to picking each barrel's center:
radius, axis (vertical) and height are constant priors. You Shift+click the top
of each drum once; on close this writes data/<scene>/gt.json in the project
schema (common/eval_schema.Barrel).

USAGE (run locally — needs a display; do NOT launch from Claude tools):
  .venv/bin/python common/annotate_barrels.py --scene data/real/station1_pit_barrels \
      --radius 0.286 --height 0.85 --axis 0 0 1

In the window:
  - drag to rotate, scroll to zoom (cloud is colored by height for cap visibility)
  - Shift + left-click the center-top of each drum   (Shift+right-click undoes)
  - press Q / close the window when done

Reference: if a candidates JSON exists (e.g. the cap-disc prototype output) pass
--candidates <file> to print its centers to the terminal as a guide before picking.
"""
import argparse
import json
import os
import sys

import numpy as np
import open3d as o3d


def load_cloud(scene_dir):
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


def color_by_height(pcd):
    z = np.asarray(pcd.points)[:, 2]
    t = (z - z.min()) / max(np.ptp(z), 1e-6)
    # simple turbo-ish ramp: blue(low) -> red(high)
    cols = np.stack([t, np.clip(1 - np.abs(2 * t - 1), 0, 1), 1 - t], axis=1)
    pcd.colors = o3d.utility.Vector3dVector(cols)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True, help="scene dir with scan000.pcd")
    ap.add_argument("--radius", type=float, default=0.286, help="drum radius m (200L=0.286)")
    ap.add_argument("--height", type=float, default=0.85, help="drum height m (200L=0.85)")
    ap.add_argument("--axis", type=float, nargs=3, default=[0.0, 0.0, 1.0],
                    help="drum axis (default vertical +Z)")
    ap.add_argument("--candidates", default=None,
                    help="optional cap_candidates.json to print as a picking guide")
    ap.add_argument("--out", default=None, help="output gt.json (default <scene>/gt.json)")
    ap.add_argument("--source", default="real_survey_lidar (manual cap-center annotation)")
    args = ap.parse_args()

    scene_dir = args.scene
    scene = os.path.basename(os.path.normpath(scene_dir))
    out = args.out or os.path.join(scene_dir, "gt.json")

    pcd = load_cloud(scene_dir)
    color_by_height(pcd)
    pts = np.asarray(pcd.points)

    if args.candidates and os.path.isfile(args.candidates):
        cj = json.load(open(args.candidates))
        print(f"\nReference candidates from {args.candidates}:")
        for c in cj.get("candidates", []):
            print(f"  {c.get('center')}  capØ={c.get('cap_diam')}")

    print("\nShift+click each drum cap center, then press Q / close the window.")
    vis = o3d.visualization.VisualizerWithEditing()
    vis.create_window(window_name=f"annotate {scene} — Shift+click cap centers")
    vis.add_geometry(pcd)
    vis.run()
    vis.destroy_window()
    picked = vis.get_picked_points()

    if not picked:
        sys.exit("no points picked — nothing written.")

    barrels = []
    for i, idx in enumerate(picked):
        c = pts[idx]
        barrels.append(dict(id=i, radius_m=args.radius, axis=list(args.axis),
                            center=[round(float(c[0]), 4), round(float(c[1]), 4),
                                    round(float(c[2]), 4)],
                            height_m=args.height, occlusion_frac=None))
    gt = dict(scene=scene, source=args.source, sensor="survey_lidar",
              units="m", frame="local_meters (de-offset site coords; z up)",
              barrels=barrels)
    json.dump(gt, open(out, "w"), indent=2)
    print(f"\nwrote {len(barrels)} barrel(s) -> {out}")


if __name__ == "__main__":
    main()
