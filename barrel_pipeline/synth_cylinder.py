#!/usr/bin/env python3
"""
Synthesize a full-cylinder point cloud and write it in 3DTK uos_normal
format so we can sanity-check detectCylinder on an ideal target.

Defaults model the real barrel: r=4.25 cm, h=40 cm, axis along +Y,
centered at (10, -6, 60) cm to match the captured-scene geometry.

Usage:
  python3 synth_cylinder.py --out data_synth
  # then:
  cd ~/masters/3DTK
  bin/detectCylinder -s 0 -e 0 -f uos_normal ~/masters/barrel_pipeline/data_synth/

  # or, to test the half-shell hypothesis directly:
  python3 synth_cylinder.py --out data_synth_half --arc-deg 120
"""
import argparse, os
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--radius-cm", type=float, default=4.25)
    ap.add_argument("--height-cm", type=float, default=40.0)
    ap.add_argument("--cx-cm", type=float, default=10.0)
    ap.add_argument("--cy-cm", type=float, default=-6.0)
    ap.add_argument("--cz-cm", type=float, default=60.0)
    ap.add_argument("--n-theta", type=int, default=180,
                    help="samples around the circumference (full 360)")
    ap.add_argument("--n-h", type=int, default=120,
                    help="samples along the axis")
    ap.add_argument("--arc-deg", type=float, default=360.0,
                    help="<360 keeps only that arc -- simulates a partial view")
    ap.add_argument("--noise-cm", type=float, default=0.1,
                    help="Gaussian noise on each axis, cm (Xtion ~1mm)")
    ap.add_argument("--write-pcd", action="store_true",
                    help="also write scan000.pcd in meters for view_cloud.py")
    args = ap.parse_args()

    arc = np.deg2rad(args.arc_deg)
    theta = np.linspace(-arc / 2, arc / 2, args.n_theta, endpoint=(arc < 2*np.pi))
    h = np.linspace(-args.height_cm / 2, args.height_cm / 2, args.n_h)
    T, H = np.meshgrid(theta, h)

    x = args.cx_cm + args.radius_cm * np.cos(T)
    y = args.cy_cm + H
    z = args.cz_cm + args.radius_cm * np.sin(T)

    # outward normals are radial in the xz plane
    nx = np.cos(T)
    ny = np.zeros_like(T)
    nz = np.sin(T)

    pts = np.stack([x.ravel(), y.ravel(), z.ravel()], axis=1)
    nrm = np.stack([nx.ravel(), ny.ravel(), nz.ravel()], axis=1)

    if args.noise_cm > 0:
        pts += np.random.default_rng(0).normal(0, args.noise_cm, pts.shape)

    os.makedirs(args.out, exist_ok=True)

    # 3DTK uos_normal: x y z nx ny nz, in cm
    uos = np.hstack([pts, nrm])
    np.savetxt(os.path.join(args.out, "scan000.3d"), uos, fmt="%.4f")
    with open(os.path.join(args.out, "scan000.pose"), "w") as f:
        f.write("0 0 0\n0 0 0\n")

    if args.write_pcd:
        xyz_m = pts / 100.0
        n = xyz_m.shape[0]
        with open(os.path.join(args.out, "scan000.pcd"), "w") as f:
            f.write("# .PCD v0.7\nVERSION 0.7\nFIELDS x y z\nSIZE 4 4 4\n"
                    "TYPE F F F\nCOUNT 1 1 1\n"
                    f"WIDTH {n}\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\n"
                    f"POINTS {n}\nDATA ascii\n")
            np.savetxt(f, xyz_m, fmt="%.6f")

    print(f"wrote {pts.shape[0]} pts to {args.out}/scan000.3d  "
          f"(arc={args.arc_deg} deg, r={args.radius_cm}cm, h={args.height_cm}cm)")


if __name__ == "__main__":
    main()
