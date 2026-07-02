#!/usr/bin/env python3
"""Run a trained BarrelNet checkpoint on the 21 verified station1 drums and print a
per-drum result table (axis error, GT-center->pred-axis distance, gate hit/miss).
Reuses PointNetReg / load_real / SCALE from train.py so inference matches training.

  python methods/barrelnet/predict_station.py --ckpt methods/barrelnet/runs/run1/best.pt
"""
import argparse, os, sys
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from train import PointNetReg, load_real, SCALE  # noqa: E402


@torch.no_grad()
def predict(model, pts, npoints, dev):
    idx = np.random.default_rng(0).choice(len(pts), npoints, replace=len(pts) < npoints)
    p = pts[idx]
    cen = p.mean(0)
    x = torch.from_numpy((p - cen)[None] / SCALE).float().to(dev)
    ax, poa = model(x)
    ax = ax[0].cpu().numpy()
    poa = poa[0].cpu().numpy() * SCALE + cen
    return ax, poa


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="methods/barrelnet/runs/run1/best.pt")
    ap.add_argument("--npoints", type=int, default=512)
    args = ap.parse_args()

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = PointNetReg().to(dev)
    st = torch.load(args.ckpt, map_location=dev)
    model.load_state_dict(st["model"])
    model.eval()
    print(f"ckpt {args.ckpt}  epoch {st.get('epoch','?')}  device {dev}\n")

    real = load_real()
    print(f"{'drum':>4} {'npts':>6} {'axis_err°':>9} {'dist_cm':>8}  gate")
    print("-" * 38)
    angs, dists, hits = [], [], 0
    for i, (pts, ax_gt, ctr_gt) in enumerate(real):
        ax, poa = predict(model, pts, args.npoints, dev)
        ang = np.degrees(np.arccos(min(1.0, abs(float(ax @ ax_gt)))))
        d = ctr_gt - poa
        dist = float(np.linalg.norm(d - (d @ ax) * ax))
        hit = ang <= 30 and dist <= 0.10
        hits += hit
        angs.append(ang); dists.append(dist)
        print(f"{i:>4} {len(pts):>6} {ang:>9.1f} {dist*100:>8.1f}  {'HIT' if hit else '.'}")

    a, dd = np.array(angs), np.array(dists)
    print("-" * 38)
    print(f"n={len(real)}  gate-hits={hits}/{len(real)}  "
          f"(axis<=30deg AND dist<=10cm)")
    print(f"axis_err  median {np.median(a):.1f}deg  mean {a.mean():.1f}deg  "
          f"max {a.max():.1f}deg")
    print(f"dist      median {np.median(dd)*100:.1f}cm  mean {dd.mean()*100:.1f}cm  "
          f"max {dd.max()*100:.1f}cm")
    print(f"axis-only pass (<=30deg): {(a<=30).sum()}/{len(real)}   "
          f"dist-only pass (<=10cm): {(dd<=0.10).sum()}/{len(real)}")


if __name__ == "__main__":
    main()
