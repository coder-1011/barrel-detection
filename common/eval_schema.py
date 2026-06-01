#!/usr/bin/env python3
"""
Shared evaluation schema for the barrel-detection method comparison.

Every method writes a predictions.json in this format; every scene carries a
gt.json in the same geometric convention. That makes the evaluation
method-agnostic: swap the proposer/method, keep the metric code.

Fixed project convention:
  units : meters
  frame : camera_optical  (x right, y down, z forward)
  a cylinder is (radius, axis unit-vector, a point on the axis, extent/height)

File shapes:
  gt.json          {scene, source, sensor, units, frame, barrels:[Barrel...]}
  predictions.json {scene, method, units, frame, runtime_s, detections:[Detection...]}
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, fields

import numpy as np


@dataclass
class Barrel:
    radius_m: float
    axis: list            # 3-vector (need not be unit length)
    center: list          # a point on the axis, meters
    height_m: float | None = None
    occlusion_frac: float | None = None   # 0=fully visible; fill from sim
    id: int | None = None


@dataclass
class Detection:
    radius_m: float
    axis: list
    center: list          # a point on the axis, meters
    extent_m: float | None = None
    score: float | None = None
    lateral_pts: int | None = None


# --------------------------------------------------------------------------- #
# geometry helpers
# --------------------------------------------------------------------------- #
def _unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


def axis_angle_deg(a, b):
    """Smallest angle between two *undirected* axes, in degrees."""
    c = abs(float(np.dot(_unit(a), _unit(b))))
    c = min(1.0, max(-1.0, c))
    return float(np.degrees(np.arccos(c)))


def axis_point_distance(center_pred, axis_pred, center_gt):
    """Perpendicular distance (m) from the gt center to the predicted axis."""
    p = np.asarray(center_gt, float) - np.asarray(center_pred, float)
    u = _unit(axis_pred)
    return float(np.linalg.norm(p - np.dot(p, u) * u))


# --------------------------------------------------------------------------- #
# IO
# --------------------------------------------------------------------------- #
def _only(cls, d):
    keys = {f.name for f in fields(cls)}
    return {k: v for k, v in d.items() if k in keys}


def load_gt(path):
    with open(path) as f:
        d = json.load(f)
    d["barrels"] = [Barrel(**_only(Barrel, b)) for b in d.get("barrels", [])]
    return d


def load_pred(path):
    with open(path) as f:
        d = json.load(f)
    d["detections"] = [Detection(**_only(Detection, x))
                       for x in d.get("detections", [])]
    return d


def save_pred(path, scene, method, detections, runtime_s=None,
              units="m", frame="camera_optical"):
    obj = dict(scene=scene, method=method, units=units, frame=frame,
               runtime_s=runtime_s,
               detections=[asdict(x) for x in detections])
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)
    return obj


# --------------------------------------------------------------------------- #
# matching + metrics
# --------------------------------------------------------------------------- #
@dataclass
class MatchConfig:
    max_center_dist_m: float = 0.10   # gt center must lie within 10 cm of axis
    max_axis_angle_deg: float = 30.0


def match(gt_barrels, detections, cfg=MatchConfig()):
    """Greedy one-to-one match. For each gt barrel, take the closest unused
    detection that passes the axis-angle and axis-distance gates.
    Returns (pairs, unmatched_gt, unmatched_det) with pairs as (gi, di)."""
    pairs, used = [], set()
    for gi, g in enumerate(gt_barrels):
        best, best_d = None, None
        for di, d in enumerate(detections):
            if di in used:
                continue
            if axis_angle_deg(d.axis, g.axis) > cfg.max_axis_angle_deg:
                continue
            dist = axis_point_distance(d.center, d.axis, g.center)
            if dist > cfg.max_center_dist_m:
                continue
            if best_d is None or dist < best_d:
                best, best_d = di, dist
        if best is not None:
            used.add(best)
            pairs.append((gi, best))
    matched_gt = {gi for gi, _ in pairs}
    unmatched_gt = [i for i in range(len(gt_barrels)) if i not in matched_gt]
    unmatched_det = [i for i in range(len(detections)) if i not in used]
    return pairs, unmatched_gt, unmatched_det


def metrics(gt_barrels, detections, cfg=MatchConfig()):
    pairs, ug, ud = match(gt_barrels, detections, cfg)
    tp, fp, fn = len(pairs), len(ud), len(ug)
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    r_err = [detections[di].radius_m - gt_barrels[gi].radius_m for gi, di in pairs]
    a_err = [axis_angle_deg(detections[di].axis, gt_barrels[gi].axis)
             for gi, di in pairs]
    return dict(
        tp=tp, fp=fp, fn=fn, precision=prec, recall=rec, f1=f1,
        radius_rmse_m=(float(np.sqrt(np.mean(np.square(r_err)))) if r_err else None),
        radius_bias_m=(float(np.mean(r_err)) if r_err else None),
        axis_angle_mean_deg=(float(np.mean(a_err)) if a_err else None),
    )
