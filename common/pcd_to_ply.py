#!/usr/bin/env python3
"""
Convert a scene's scan000.pcd to scan000.ply (binary).

The apt (Ubuntu jammy/universe) build of CloudCompare has no PCD reader, but reads PLY
natively — so before annotating a scene in the container (docker-3dtk-show), make a PLY.
Open3D / .pcd are meters; PLY keeps the same coordinates.

USAGE (host, project .venv):
  .venv/bin/python common/pcd_to_ply.py data/real/station1_pit_barrels
  .venv/bin/python common/pcd_to_ply.py <scene_dir> [--out scan000.ply]
"""
import argparse
import os
import sys

import open3d as o3d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene_dir", help="scene dir containing scan000.pcd")
    ap.add_argument("--out", default="scan000.ply", help="output filename in scene dir")
    args = ap.parse_args()

    pcd_path = os.path.join(args.scene_dir, "scan000.pcd")
    if not os.path.isfile(pcd_path):
        sys.exit(f"no scan000.pcd in {args.scene_dir}")
    p = o3d.io.read_point_cloud(pcd_path)
    if not len(p.points):
        sys.exit(f"empty cloud: {pcd_path}")
    out = os.path.join(args.scene_dir, args.out)
    o3d.io.write_point_cloud(out, p, write_ascii=False)
    print(f"wrote {len(p.points)} pts -> {out}")


if __name__ == "__main__":
    main()
