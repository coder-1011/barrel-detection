#!/usr/bin/env python3
"""
Evaluate one method's predictions against per-scene ground truth.

Walks methods/<method>/results/<scene>/predictions.json, pairs each with the
scene's data/<group>/<scene>/gt.json, matches detections to barrels, and prints
a per-scene + aggregate table (precision/recall/F1, radius RMSE, axis-angle).
Scenes without a gt.json are skipped (e.g. real captures pending measurement).

Usage (from ~/masters):
  python3 eval/evaluate.py --method 3dtk_hough
  python3 eval/evaluate.py --method 3dtk_hough --csv eval/3dtk_hough.csv
"""
import argparse
import csv
import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "common"))
from eval_schema import load_gt, load_pred, metrics  # noqa: E402

MASTERS = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       ".."))


def find_gt_for_scene(scene):
    for grp in ("real", "synth"):
        p = os.path.join(MASTERS, "data", grp, scene, "gt.json")
        if os.path.isfile(p):
            return p
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", required=True, help="folder under methods/")
    ap.add_argument("--csv", default=None, help="optional CSV output path")
    args = ap.parse_args()

    results_root = os.path.join(MASTERS, "methods", args.method, "results")
    pred_files = sorted(glob.glob(os.path.join(results_root, "*", "predictions.json")))
    if not pred_files:
        sys.exit(f"no predictions.json under {results_root} "
                 f"(run methods/{args.method}/run_detection.sh first)")

    rows = []
    agg = dict(tp=0, fp=0, fn=0)
    hdr = (f"{'scene':<30} {'TP':>3} {'FP':>3} {'FN':>3} "
           f"{'prec':>5} {'rec':>5} {'F1':>5} {'rRMSE_cm':>9} {'axis_deg':>9}")
    print(hdr)
    print("-" * len(hdr))
    for pf in pred_files:
        scene = os.path.basename(os.path.dirname(pf))
        gtp = find_gt_for_scene(scene)
        if not gtp:
            print(f"{scene:<30} (no gt.json - skipped)")
            continue
        gt = load_gt(gtp)
        pred = load_pred(pf)
        m = metrics(gt["barrels"], pred["detections"])
        for k in ("tp", "fp", "fn"):
            agg[k] += m[k]
        rr = "" if m["radius_rmse_m"] is None else f"{m['radius_rmse_m'] * 100:9.2f}"
        aa = "" if m["axis_angle_mean_deg"] is None else f"{m['axis_angle_mean_deg']:9.2f}"
        print(f"{scene:<30} {m['tp']:>3} {m['fp']:>3} {m['fn']:>3} "
              f"{m['precision']:5.2f} {m['recall']:5.2f} {m['f1']:5.2f} {rr:>9} {aa:>9}")
        rows.append(dict(scene=scene, **m))

    tp, fp, fn = agg["tp"], agg["fp"], agg["fn"]
    P = tp / (tp + fp) if (tp + fp) else 0.0
    R = tp / (tp + fn) if (tp + fn) else 0.0
    F = 2 * P * R / (P + R) if (P + R) else 0.0
    print("-" * len(hdr))
    print(f"{'AGGREGATE':<30} {tp:>3} {fp:>3} {fn:>3} {P:5.2f} {R:5.2f} {F:5.2f}")

    if args.csv and rows:
        os.makedirs(os.path.dirname(os.path.abspath(args.csv)), exist_ok=True)
        with open(args.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {args.csv}")


if __name__ == "__main__":
    main()
