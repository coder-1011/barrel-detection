"""Sliding-window fixed-radius cylinder search over the station1 drum pile.

For each x-y grid window: RANSAC a r=0.286 m cylinder from point-pair normals
(axis = n_i x n_j, center = p_i +/- R n_i), then refine axis (normal-covariance)
+ center (fixed-R Gauss-Newton circle) and score by inliers / RMS / arc coverage
/ axial extent. Merge nearby hits, plot map + cross-sections.
"""
import json, os, sys
import numpy as np
import open3d as o3d
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, "/home/bharath/Projects/masters/common")
from fit_from_segments import fixed_radius_circle, angular_coverage, plane_basis

R = 0.286
ROOT = "/home/bharath/Projects/masters/data/real/station1_pit_barrels"
OUT = os.path.dirname(os.path.abspath(__file__))
rng = np.random.default_rng(0)

pts = np.asarray(o3d.io.read_point_cloud(f"{ROOT}/scan000.pcd").points)
pc = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(pts))
pc.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=0.06, max_nn=30))
N = np.asarray(pc.normals)
print(f"{len(pts):,} pts, normals done")

def refine(win_pts, win_N, inl):
    """Refine axis+center on inlier set; return candidate dict or None."""
    P, Nn = win_pts[inl], win_N[inl]
    if len(P) < 120:
        return None
    # axis = smallest eigvec of normal covariance (cylinder normals span plane perp axis)
    w, V = np.linalg.eigh(Nn.T @ Nn)
    axis = V[:, 0]
    u, v = plane_basis(axis)
    o = P.mean(0); q = P - o
    P2 = np.column_stack([q @ u, q @ v])
    rad = P2 - P2.mean(0)
    rn = np.linalg.norm(rad, axis=1, keepdims=True)
    md = (rad / np.where(rn < 1e-9, 1e-9, rn)).mean(0)
    md /= (np.linalg.norm(md) + 1e-9)
    c2, rms = fixed_radius_circle(P2, R, P2.mean(0) - R * md)
    cov = angular_coverage(P2, c2)
    t = q @ axis
    ext = float(t.max() - t.min())
    center = o + c2[0] * u + c2[1] * v + axis * float(t.mean())
    return dict(center=center, axis=axis, n_inl=int(len(P)), rms=float(rms),
                coverage=float(cov), extent=ext)

# ---- sliding windows ----
xs = np.arange(-1.6, 3.8, 0.35)
ys = np.arange(-2.2, 3.0, 0.35)
cands = []
for cx in xs:
    for cy in ys:
        m = (np.abs(pts[:, 0] - cx) < 0.55) & (np.abs(pts[:, 1] - cy) < 0.55)
        if m.sum() < 250:
            continue
        W, WN = pts[m], N[m]
        n = len(W)
        best = (0, None)
        for _ in range(800):
            i, j = rng.integers(0, n, 2)
            ax = np.cross(WN[i], WN[j]); na = np.linalg.norm(ax)
            if na < 0.3:
                continue
            ax /= na
            for s in (1, -1):
                a0 = W[i] + s * R * WN[i]
                d = W - a0
                perp = d - np.outer(d @ ax, ax)
                rd = np.linalg.norm(perp, axis=1)
                rdir = perp / np.where(rd[:, None] < 1e-9, 1e-9, rd[:, None])
                inl = (np.abs(rd - R) < 0.025) & \
                      (np.abs(np.einsum('ij,ij->i', rdir, WN)) > 0.75)
                c = int(inl.sum())
                if c > best[0]:
                    best = (c, inl)
        if best[0] < 150:
            continue
        cand = refine(W, WN, best[1])
        if cand is None:
            continue
        if cand["rms"] < 0.030 and cand["coverage"] > 0.28 and 0.25 < cand["extent"] < 1.4:
            cands.append(cand)

print(f"{len(cands)} raw window hits")

# ---- merge (greedy NMS by inlier count, 0.35 m center distance) ----
cands.sort(key=lambda c: -c["n_inl"])
kept = []
for c in cands:
    if all(np.linalg.norm(c["center"] - k["center"]) > 0.35 for k in kept):
        kept.append(c)
print(f"{len(kept)} merged candidates")

caps = json.load(open(
    "/home/bharath/Projects/masters/methods/efficient_ransac/results/"
    "station1_pit_barrels/cap_candidates.json"))["candidates"]
gt = json.load(open(f"{ROOT}/gt.json"))["barrels"][0]

# ---- map ----
fig, ax = plt.subplots(figsize=(12, 10))
sub = pts[pts[:, 2] > -15.9]
ax.scatter(sub[:, 0], sub[:, 1], s=0.8, c=sub[:, 2], cmap="Greys_r", linewidths=0)
th = np.linspace(0, 2 * np.pi, 60)
for i, c in enumerate(kept):
    x0, y0 = c["center"][0], c["center"][1]
    tilt = np.degrees(np.arccos(min(1, abs(c["axis"][2]))))
    ax.plot(x0 + R * np.cos(th), y0 + R * np.sin(th), "r-", lw=1.4)
    ax.annotate(f"D{i}", (x0, y0), color="red", fontsize=11, weight="bold")
for cp in caps:
    ax.plot(cp["center"][0], cp["center"][1], "b^", ms=6, alpha=0.6)
ax.plot(gt["center"][0], gt["center"][1], "g+", ms=16, mew=3)
ax.annotate("GT barrel_00", (gt["center"][0], gt["center"][1]), color="green",
            textcoords="offset points", xytext=(8, 8))
ax.set_title("Drum candidates: red circles = fixed-R cylinder hits (D#), "
             "blue ^ = old cap prototype, green + = GT")
ax.set_aspect("equal")
fig.tight_layout(); fig.savefig(f"{OUT}/drum_map.png", dpi=110); plt.close(fig)

# ---- per-candidate cross-sections (top 10) ----
top = kept[:10]
rows = int(np.ceil(len(top) / 5))
fig, axes = plt.subplots(rows, 5, figsize=(22, 4.5 * rows), squeeze=False)
for i, c in enumerate(top):
    axp = axes[i // 5][i % 5]
    a, ctr = c["axis"], c["center"]
    d = pts - ctr
    t = d @ a
    perp = d - np.outer(t, a)
    m = (np.linalg.norm(perp, axis=1) < 0.55) & (np.abs(t) < max(0.6, c["extent"]))
    u, v = plane_basis(a)
    P2 = np.column_stack([d[m] @ u, d[m] @ v])
    axp.scatter(P2[:, 0], P2[:, 1], s=1.2, c=t[m], cmap="viridis", linewidths=0)
    axp.plot(R * np.cos(th), R * np.sin(th), "r-", lw=1.2)
    tilt = np.degrees(np.arccos(min(1, abs(a[2]))))
    axp.set_title(f"D{i}: inl={c['n_inl']} rms={c['rms']*100:.1f}cm "
                  f"cov={c['coverage']:.2f}\next={c['extent']:.2f}m tilt={tilt:.0f}°",
                  fontsize=9)
    axp.set_aspect("equal")
for j in range(len(top), rows * 5):
    axes[j // 5][j % 5].axis("off")
fig.tight_layout(); fig.savefig(f"{OUT}/drum_xsections.png", dpi=100); plt.close(fig)

for i, c in enumerate(kept):
    tilt = np.degrees(np.arccos(min(1, abs(c["axis"][2]))))
    print(f"D{i}: ctr=({c['center'][0]:+.2f},{c['center'][1]:+.2f},{c['center'][2]:+.2f}) "
          f"inl={c['n_inl']:4d} rms={c['rms']*100:4.1f}cm cov={c['coverage']:.2f} "
          f"ext={c['extent']:.2f}m tilt={tilt:3.0f}deg")
json.dump([{k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in c.items()}
           for c in kept], open(f"{OUT}/drum_candidates.json", "w"), indent=1)
