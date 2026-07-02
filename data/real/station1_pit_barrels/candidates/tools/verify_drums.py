"""Verify drum candidates: inlier-only views, cap-candidate agreement, shaded 3D render."""
import json, os, sys
import numpy as np
import open3d as o3d
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, "/home/bharath/Projects/masters/common")
from fit_from_segments import plane_basis

R = 0.286
ROOT = "/home/bharath/Projects/masters/data/real/station1_pit_barrels"
OUT = os.path.dirname(os.path.abspath(__file__))

pts = np.asarray(o3d.io.read_point_cloud(f"{ROOT}/scan000.pcd").points)
pc = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(pts))
pc.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=0.06, max_nn=30))
N = np.asarray(pc.normals)

cands = json.load(open(f"{OUT}/drum_candidates.json"))
caps = json.load(open("/home/bharath/Projects/masters/methods/efficient_ransac/results/"
                      "station1_pit_barrels/cap_candidates.json"))["candidates"]
gt = json.load(open(f"{ROOT}/gt.json"))["barrels"][0]

# recompute inliers of each candidate against the full cloud
scored = []
for i, c in enumerate(cands):
    a = np.array(c["axis"]); ctr = np.array(c["center"])
    d = pts - ctr
    t = d @ a
    perp = d - np.outer(t, a)
    rd = np.linalg.norm(perp, axis=1)
    rdir = perp / np.where(rd[:, None] < 1e-9, 1e-9, rd[:, None])
    half = max(0.45, c["extent"] / 2)
    inl = (np.abs(rd - R) < 0.025) & (np.abs(np.einsum('ij,ij->i', rdir, N)) > 0.75) \
          & (np.abs(t) < half)
    capd = min(np.linalg.norm(np.array(cp["center"][:2]) - ctr[:2]) for cp in caps)
    gtd = np.linalg.norm(np.array(gt["center"][:2]) - ctr[:2])
    scored.append(dict(idx=i, inl_mask=inl, n=int(inl.sum()), cap_d=float(capd),
                       gt_d=float(gtd), **{k: c[k] for k in
                       ("center", "axis", "rms", "coverage", "extent")}))
    print(f"D{i}: full-cloud inl={inl.sum():5d} nearest-cap={capd:.2f}m gt-dist={gtd:.2f}m")

# ---- inlier-only cross-section + longitudinal for the 12 best by full-cloud inliers ----
top = sorted(scored, key=lambda s: -s["n"])[:12]
th = np.linspace(0, 2 * np.pi, 60)
fig, axes = plt.subplots(3, 8, figsize=(30, 11), squeeze=False)
for k, s in enumerate(top):
    a = np.array(s["axis"]); ctr = np.array(s["center"])
    P = pts[s["inl_mask"]]
    d = P - ctr; t = d @ a
    u, v = plane_basis(a)
    P2 = np.column_stack([d @ u, d @ v])
    r_, c_ = (k // 4), (k % 4) * 2
    ax1, ax2 = axes[r_][c_], axes[r_][c_ + 1]
    ax1.scatter(P2[:, 0], P2[:, 1], s=2.0, c=t, cmap="viridis", linewidths=0)
    ax1.plot(R * np.cos(th), R * np.sin(th), "r-", lw=1)
    ax1.set_title(f"D{s['idx']} xsec  inl={s['n']} cov={s['coverage']:.2f} "
                  f"cap_d={s['cap_d']:.2f}", fontsize=9)
    ax1.set_aspect("equal"); ax1.set_xlim(-0.5, 0.5); ax1.set_ylim(-0.5, 0.5)
    ax2.scatter(t, P2 @ np.array([1, 0]), s=2.0, c=P2[:, 1], cmap="viridis", linewidths=0)
    ax2.set_title(f"D{s['idx']} along-axis ext={s['extent']:.2f}m", fontsize=9)
    ax2.set_aspect("equal")
fig.tight_layout(); fig.savefig(f"{OUT}/drum_inliers.png", dpi=95); plt.close(fig)

# ---- shaded oblique 3D render of pile core (EGL offscreen) ----
try:
    core = (pts[:, 0] > -1.0) & (pts[:, 0] < 3.6) & (pts[:, 1] > -2.6) & (pts[:, 1] < 2.8)
    pcc = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(pts[core]))
    pcc.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=0.06, max_nn=30))
    pcc.orient_normals_towards_camera_location(np.array([1.1, 0.75, -5.0]))
    # lambert shade from two lights
    nn = np.asarray(pcc.normals)
    l1 = np.array([0.5, 0.3, 0.81]); l1 /= np.linalg.norm(l1)
    l2 = np.array([-0.6, -0.5, 0.62]); l2 /= np.linalg.norm(l2)
    sh = 0.65 * np.clip(nn @ l1, 0, 1) + 0.35 * np.clip(nn @ l2, 0, 1)
    col = plt.get_cmap("copper")(0.15 + 0.8 * sh)[:, :3]
    pcc.colors = o3d.utility.Vector3dVector(col)
    for az, el, tag in [(210, 30, "a"), (120, 25, "b")]:
        W, H = 1600, 1200
        rend = o3d.visualization.rendering.OffscreenRenderer(W, H)
        mat = o3d.visualization.rendering.MaterialRecord()
        mat.shader = "defaultUnlit"; mat.point_size = 3.0
        rend.scene.set_background([1, 1, 1, 1])
        rend.scene.add_geometry("pc", pcc, mat)
        bb = pcc.get_axis_aligned_bounding_box(); c = bb.get_center()
        azr, elr = np.radians(az), np.radians(el)
        eye = c + 6.5 * np.array([np.cos(elr) * np.cos(azr),
                                  np.cos(elr) * np.sin(azr), np.sin(elr)])
        rend.setup_camera(35, c, eye, [0, 0, 1])
        img = rend.render_to_image()
        o3d.io.write_image(f"{OUT}/pile_shaded_{tag}.png", img)
        del rend
    print("3D renders done")
except Exception as e:
    print("3D render failed:", e)
