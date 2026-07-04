#!/usr/bin/env python3
"""Shared BarrelNet inference: load checkpoint(s) and predict (axis,
point-on-axis) from a single-drum patch, optionally with test-time
augmentation (TTA): ensemble over random point subsamples x random rotations
about z (the training augmentation), aggregated sign-invariantly.

With tta=0 this reproduces the original single-pass predict_station.py
behaviour bit-for-bit (fixed rng(0) subsample, no rotation).
"""
import os
import sys

import numpy as np
import torch

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "..", "common"))
from train import PointNetReg, SCALE  # noqa: E402
from fit_from_segments import fixed_radius_circle, plane_basis  # noqa: E402


def load_models(ckpts, dev):
    """ckpts: iterable of checkpoint paths -> list of eval-mode models."""
    models = []
    for c in ckpts:
        st = torch.load(c, map_location=dev)
        m = PointNetReg().to(dev)
        m.load_state_dict(st["model"])
        m.eval()
        models.append(m)
    return models


@torch.no_grad()
def predict_patch(models, pts, npoints=512, dev="cpu", tta=0, seed=0):
    """Predict (unit axis, point-on-axis [m]) for one patch (N,3 meters).

    tta=0: single pass, fixed subsample (legacy behaviour).
    tta=K: K passes, each a fresh random subsample + random z-rotation;
           axis = principal eigenvector of the axis scatter (sign-invariant),
           point-on-axis = component-wise median of the K estimates.
    """
    rng = np.random.default_rng(seed)
    axes, poas = [], []
    for k in range(max(1, tta)):
        if tta == 0:
            idx = np.random.default_rng(0).choice(
                len(pts), npoints, replace=len(pts) < npoints)
            Rz = np.eye(3, dtype=np.float32)
        else:
            idx = rng.choice(len(pts), npoints, replace=len(pts) < npoints)
            th = rng.uniform(0, 2 * np.pi)
            c, s = np.cos(th), np.sin(th)
            Rz = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], np.float32)
        p = (pts[idx] @ Rz.T).astype(np.float32)
        cen = p.mean(0)
        x = torch.from_numpy((p - cen)[None] / SCALE).float().to(dev)
        for m in models:
            ax, poa = m(x)
            axes.append(ax[0].cpu().numpy() @ Rz)          # back to world
            poas.append((poa[0].cpu().numpy() * SCALE + cen) @ Rz)
    A = np.asarray(axes)
    _, V = np.linalg.eigh(A.T @ A)
    axis = V[:, -1] / np.linalg.norm(V[:, -1])
    poa = np.median(np.asarray(poas), axis=0)
    return axis.astype(np.float32), poa.astype(np.float32)


def refine_center(pts, axis, radius, poa_fallback, min_pts=200):
    """Hybrid center: radius-locked Gauss-Newton circle fit in the plane
    perpendicular to the (net-predicted) axis. The net's axis is its strength;
    its position head is the bottleneck — the geometric fit fixes that.
    Falls back to the net's point-on-axis on sparse patches, where the circle
    fit can diverge. Returns (center, fit_rms_or_None)."""
    if len(pts) < min_pts:
        return np.asarray(poa_fallback, np.float32), None
    u, v = plane_basis(axis)
    o = pts.mean(0)
    q = pts - o
    P2 = np.column_stack([q @ u, q @ v])
    rad = P2 - P2.mean(0)
    rn = np.linalg.norm(rad, axis=1, keepdims=True)
    md = (rad / np.where(rn < 1e-9, 1e-9, rn)).mean(0)
    md /= (np.linalg.norm(md) + 1e-9)
    c2, rms = fixed_radius_circle(P2, radius, P2.mean(0) - radius * md)
    center = o + c2[0] * u + c2[1] * v
    return center.astype(np.float32), float(rms)
