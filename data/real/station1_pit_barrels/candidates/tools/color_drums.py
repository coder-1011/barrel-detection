"""Export scan000 with per-drum-candidate inlier points colored, for CloudCompare."""
import json, os
import numpy as np
import open3d as o3d
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = "/home/bharath/Projects/masters/data/real/station1_pit_barrels"
SCR = os.path.dirname(os.path.abspath(__file__))
OUT = f"{ROOT}/candidates"
R = 0.286

pts = np.asarray(o3d.io.read_point_cloud(f"{ROOT}/scan000.pcd").points)
pc = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(pts))
pc.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=0.06, max_nn=30))
N = np.asarray(pc.normals)
cands = json.load(open(f"{SCR}/drum_candidates.json"))

# tiers: (ids, label)  -- D0 included but flagged 'suspect' in the legend
GT_IDS = [22, 40, 16]
HI_IDS = [2, 3, 5, 15, 21, 24, 31, 37, 38]
PR_IDS = [1, 4, 6, 7, 9, 11, 19, 20]
SUS_IDS = [0]
ORDER = [(i, "GT-cluster") for i in GT_IDS] + [(i, "high") for i in HI_IDS] + \
        [(i, "probable") for i in PR_IDS] + [(i, "suspect") for i in SUS_IDS]

# 21 well-separated saturated colors (tab20 minus its two greys, which would
# disappear against the grey background; add black + yellow + magenta instead)
pal = [c for c in plt.get_cmap("tab20").colors
       if abs(c[0] - c[1]) + abs(c[1] - c[2]) > 0.05]
pal += [(0.0, 0.0, 0.0), (1.0, 0.85, 0.0), (0.9, 0.1, 0.5)]
pal = [tuple(round(v, 3) for v in c) for c in pal]

colors = np.full((len(pts), 3), 0.62)          # grey background
label = np.full(len(pts), -1, int)
legend = []
for k, (i, tier) in enumerate(ORDER):
    c = cands[i]
    a = np.array(c["axis"]); ctr = np.array(c["center"])
    d = pts - ctr
    t = d @ a
    perp = d - np.outer(t, a)
    rd = np.linalg.norm(perp, axis=1)
    rdir = perp / np.where(rd[:, None] < 1e-9, 1e-9, rd[:, None])
    half = max(0.45, c["extent"] / 2)
    inl = (np.abs(rd - R) < 0.03) & (np.abs(np.einsum('ij,ij->i', rdir, N)) > 0.7) \
          & (np.abs(t) < half) & (label < 0)
    col = pal[k % len(pal)]
    colors[inl] = col
    label[inl] = i
    legend.append(dict(id=f"D{i}", tier=tier, color_rgb=[int(255 * v) for v in col],
                       n_pts=int(inl.sum()),
                       center=[round(float(x), 3) for x in ctr],
                       tilt_deg=round(float(np.degrees(np.arccos(min(1, abs(a[2]))))), 0)))
    print(f"D{i:<3} {tier:<10} pts={inl.sum():5d} rgb={[int(255*v) for v in col]}")

pc.colors = o3d.utility.Vector3dVector(colors)
pc.normals = o3d.utility.Vector3dVector()      # keep the PLY lean
o3d.io.write_point_cloud(f"{OUT}/scan000_drums_colored.ply", pc, write_ascii=False)
json.dump(legend, open(f"{OUT}/legend.json", "w"), indent=1)

# legend card
fig, ax = plt.subplots(figsize=(6, 8))
for r_, e in enumerate(legend):
    y = 1 - (r_ + 1) / (len(legend) + 1)
    ax.add_patch(plt.Rectangle((0.02, y), 0.07, 0.028,
                               color=np.array(e["color_rgb"]) / 255))
    ax.text(0.12, y, f"{e['id']:<5} {e['tier']:<11} tilt={int(e['tilt_deg']):>2}°  "
            f"({e['center'][0]:+.2f},{e['center'][1]:+.2f})  {e['n_pts']} pts",
            fontsize=9, family="monospace", va="bottom")
ax.axis("off"); ax.set_title("scan000_drums_colored.ply — legend")
fig.tight_layout(); fig.savefig(f"{OUT}/legend.png", dpi=130); plt.close(fig)

# quick render so we can preview what CloudCompare will show
rend = o3d.visualization.rendering.OffscreenRenderer(1800, 1300)
rend.scene.set_background([1, 1, 1, 1])
mat = o3d.visualization.rendering.MaterialRecord()
mat.shader = "defaultUnlit"; mat.point_size = 3.5
core = (pts[:, 0] > -1.3) & (pts[:, 0] < 4.0) & (pts[:, 1] > -3.0) & (pts[:, 1] < 3.0)
pcc = pc.select_by_index(np.where(core)[0])
rend.scene.add_geometry("pc", pcc, mat)
ctr = np.array([1.2, 0.2, -15.3])
eye = ctr + np.array([-4.6, -4.0, 4.6])
rend.setup_camera(33, ctr, eye, [0, 0, 1])
o3d.io.write_image(f"{OUT}/colored_preview.png", rend.render_to_image())
print("wrote", f"{OUT}/scan000_drums_colored.ply")
