"""Render the station1 pile with fitted drum cylinders overlaid, multiple views."""
import json, os
import numpy as np
import open3d as o3d
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = "/home/bharath/Projects/masters/data/real/station1_pit_barrels"
SCR = os.path.dirname(os.path.abspath(__file__))
OUT = f"{ROOT}/candidates"
os.makedirs(OUT, exist_ok=True)
R = 0.286
DRUM_H = 0.85

pts = np.asarray(o3d.io.read_point_cloud(f"{ROOT}/scan000.pcd").points)
cands = json.load(open(f"{SCR}/drum_candidates.json"))
gt = json.load(open(f"{ROOT}/gt.json"))["barrels"][0]

GREEN = [0.10, 0.75, 0.20]   # GT / confirmed cluster
RED = [0.85, 0.10, 0.10]     # high confidence (wall fit + cap agreement)
ORANGE = [0.95, 0.55, 0.05]  # probable (strong wall arc only)
TIERS = [(GREEN, [22, 40, 16]),
         (RED, [2, 3, 5, 15, 21, 24, 31, 37, 38]),
         (ORANGE, [1, 4, 6, 7, 9, 11, 19, 20])]

def make_cyl(center, axis, color, h=DRUM_H):
    cyl = o3d.geometry.TriangleMesh.create_cylinder(radius=R, height=h, resolution=40)
    cyl.compute_vertex_normals()
    a = np.asarray(axis, float); a /= np.linalg.norm(a)
    z = np.array([0.0, 0.0, 1.0])
    v = np.cross(z, a); s = np.linalg.norm(v); c = float(z @ a)
    if s < 1e-8:
        Rm = np.eye(3) if c > 0 else -np.eye(3)
    else:
        vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
        Rm = np.eye(3) + vx + vx @ vx * ((1 - c) / s**2)
    cyl.rotate(Rm, center=(0, 0, 0))
    cyl.translate(np.asarray(center, float))
    cyl.paint_uniform_color(color)
    return cyl

# shaded pile points (crop to region of interest)
m = (pts[:, 0] > -1.3) & (pts[:, 0] < 4.0) & (pts[:, 1] > -3.0) & (pts[:, 1] < 3.0)
pcd = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(pts[m]))
pcd.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=0.06, max_nn=30))
pcd.orient_normals_towards_camera_location(np.array([1.1, 0.75, -5.0]))
nn = np.asarray(pcd.normals)
l1 = np.array([0.5, 0.3, 0.81]); l1 /= np.linalg.norm(l1)
l2 = np.array([-0.6, -0.5, 0.62]); l2 /= np.linalg.norm(l2)
sh = 0.65 * np.clip(nn @ l1, 0, 1) + 0.35 * np.clip(nn @ l2, 0, 1)
pcd.colors = o3d.utility.Vector3dVector(plt.get_cmap("bone")(0.25 + 0.65 * sh)[:, :3])

cyls = [(f"gt", make_cyl(gt["center"], gt["axis"], GREEN, h=gt["height_m"]))]
for color, ids in TIERS:
    for i in ids:
        c = cands[i]
        cyls.append((f"D{i}", make_cyl(c["center"], c["axis"], color,
                                       h=min(DRUM_H, max(0.5, c["extent"])))))

center = np.array([1.2, 0.2, -15.3])
views = [("view_sw", 215, 35, 8.0), ("view_ne", 55, 30, 8.0), ("view_top", 270, 75, 9.0)]
for tag, az, el, dist in views:
    rend = o3d.visualization.rendering.OffscreenRenderer(1800, 1300)
    rend.scene.set_background([1, 1, 1, 1])
    pmat = o3d.visualization.rendering.MaterialRecord()
    pmat.shader = "defaultUnlit"; pmat.point_size = 3.0
    rend.scene.add_geometry("pts", pcd, pmat)
    cmat = o3d.visualization.rendering.MaterialRecord()
    cmat.shader = "defaultLitTransparency"
    for name, cyl in cyls:
        mat = o3d.visualization.rendering.MaterialRecord()
        mat.shader = "defaultLitTransparency"
        col = np.asarray(cyl.vertex_colors)[0]
        mat.base_color = [float(col[0]), float(col[1]), float(col[2]), 0.55]
        rend.scene.add_geometry(name, cyl, mat)
    azr, elr = np.radians(az), np.radians(el)
    eye = center + dist * np.array([np.cos(elr) * np.cos(azr),
                                    np.cos(elr) * np.sin(azr), np.sin(elr)])
    rend.setup_camera(33, center, eye, [0, 0, 1])
    o3d.io.write_image(f"{OUT}/barrels_{tag}.png", rend.render_to_image())
    del rend
    print(f"{OUT}/barrels_{tag}.png")

# also copy candidates json + map into the scene folder
import shutil
shutil.copy(f"{SCR}/drum_candidates.json", f"{OUT}/drum_candidates.json")
shutil.copy(f"{SCR}/drum_map.png", f"{OUT}/drum_map_topdown.png")
print("done")
