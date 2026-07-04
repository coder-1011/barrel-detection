#!/usr/bin/env python3
"""Run a trained BarrelNet checkpoint on the 21 verified station1 drums and print a
per-drum result table (axis error, GT-center->pred-axis distance, gate hit/miss).
Reuses load_real from train.py + infer.py so inference matches training.

  python methods/barrelnet/predict_station.py --ckpt methods/barrelnet/runs/run1/best.pt
  # TTA ensemble (32 subsample+rotation passes), two checkpoints:
  python methods/barrelnet/predict_station.py --tta 32 \
      --ckpt methods/barrelnet/runs/a100/best.pt,methods/barrelnet/runs/a100/last.pt
  # score only the held-out drums of a finetune split:
  python methods/barrelnet/predict_station.py --ckpt <ft.pt> \
      --split methods/barrelnet/real_split.json --subset eval
"""
import argparse, json, os, sys
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from train import load_real  # noqa: E402
from infer import load_models, predict_patch, refine_center  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="methods/barrelnet/runs/run1/best.pt",
                    help="checkpoint path, or comma-separated list to ensemble")
    ap.add_argument("--npoints", type=int, default=512)
    ap.add_argument("--tta", type=int, default=0,
                    help="test-time-augmentation passes (0 = single legacy pass)")
    ap.add_argument("--split", default=None, help="real_split.json to filter drums")
    ap.add_argument("--subset", default="eval", choices=["eval", "finetune"],
                    help="which side of --split to score")
    ap.add_argument("--hybrid-center", action="store_true",
                    help="replace the net's point-on-axis with a radius-locked "
                         "circle fit perpendicular to the predicted axis "
                         "(falls back to the net on sparse patches)")
    args = ap.parse_args()

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    ckpts = args.ckpt.split(",")
    models = load_models(ckpts, dev)
    print(f"ckpt {args.ckpt}  tta {args.tta}  device {dev}\n")

    real = load_real()
    if args.split:
        keep = set(json.load(open(args.split))[args.subset])
        real = [r for r in real if r[0] in keep]
        print(f"split {args.split} [{args.subset}]: {len(real)} drums\n")
    print(f"{'drum':>4} {'npts':>6} {'axis_err°':>9} {'dist_cm':>8}  gate")
    print("-" * 38)
    angs, dists, hits = [], [], 0
    for i, pts, ax_gt, ctr_gt in real:
        ax, poa = predict_patch(models, pts, args.npoints, dev, tta=args.tta)
        if args.hybrid_center:
            poa, _ = refine_center(pts, ax, 0.286, poa)
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
