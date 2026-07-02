#!/usr/bin/env python3
"""
Render proper 3D Open3D views (point cloud + fitted cylinder mesh) to PNG,
matching common/view_cloud.py (prediction = red, ground truth = green).

Headless via Open3D OffscreenRenderer (EGL). Output -> assets/.
"""
import os
import json
import numpy as np
import open3d as o3d
import open3d.visualization.rendering as rendering

HERE = os.path.dirname(os.path.abspath(__file__))
MASTERS = os.path.abspath(os.path.join(HERE, "..", ".."))
ASSETS = os.path.join(HERE, "assets")
os.makedirs(ASSETS, exist_ok=True)

W, H = 1500, 1100


def P(*a):
    return os.path.join(MASTERS, *a)


def load_cloud(scene_dir):
    pcd = os.path.join(scene_dir, "scan000.pcd")
    if os.path.isfile(pcd):
        return o3d.io.read_point_cloud(pcd)
    txt = os.path.join(scene_dir, "scan000.3d")
    xyz = np.loadtxt(txt)[:, :3] / 100.0
    p = o3d.geometry.PointCloud()
    p.points = o3d.utility.Vector3dVector(xyz)
    return p


def color_by_depth(pcd):
    """Colour points by z (depth) with a viridis-like ramp for a richer look."""
    xyz = np.asarray(pcd.points)
    z = xyz[:, 2]
    t = (z - z.min()) / (np.ptp(z) + 1e-9)
    # simple blue->green->yellow ramp
    cmap = np.array([[0.27, 0.00, 0.33], [0.13, 0.57, 0.55],
                     [0.99, 0.91, 0.14]])
    idx = t * (len(cmap) - 1)
    lo = np.floor(idx).astype(int)
    hi = np.minimum(lo + 1, len(cmap) - 1)
    f = (idx - lo)[:, None]
    cols = cmap[lo] * (1 - f) + cmap[hi] * f
    pcd.colors = o3d.utility.Vector3dVector(cols)
    return pcd


def cyl_from(center, axis, radius, length, color, shrink=0.001):
    radius = max(radius - shrink, 0.001)   # sit just inside the measured points
    a = np.asarray(axis, float)
    a = a / (np.linalg.norm(a) + 1e-12)
    start = np.asarray(center, float) - a * length / 2
    end = np.asarray(center, float) + a * length / 2
    v = end - start
    h = float(np.linalg.norm(v))
    m = o3d.geometry.TriangleMesh.create_cylinder(radius=radius, height=h,
                                                  resolution=48)
    m.compute_vertex_normals()
    m.paint_uniform_color(color)
    d = v / h
    z = np.array([0.0, 0.0, 1.0])
    cr = np.cross(z, d); s = np.linalg.norm(cr); c = float(np.dot(z, d))
    if s < 1e-9:
        R = np.eye(3) if c > 0 else -np.eye(3)
    else:
        K = np.array([[0, -cr[2], cr[1]], [cr[2], 0, -cr[0]],
                      [-cr[1], cr[0], 0]])
        R = np.eye(3) + K + K @ K * ((1 - c) / (s * s))
    m.rotate(R, center=(0, 0, 0))
    m.translate(start + v / 2)
    return m


def wireframe_cyl(center, axis, radius, length, color, nseg=40, nvert=12):
    """Green/red wireframe: top+bottom circles + vertical struts (a LineSet)."""
    a = np.asarray(axis, float); a = a / (np.linalg.norm(a) + 1e-12)
    # orthonormal basis in the plane perpendicular to a
    t = np.array([1.0, 0, 0]) if abs(a[0]) < 0.9 else np.array([0, 1.0, 0])
    u = np.cross(a, t); u /= np.linalg.norm(u)
    w = np.cross(a, u)
    c = np.asarray(center, float)
    pts, lines = [], []
    for k, off in enumerate((-length / 2, length / 2)):
        base = len(pts)
        for j in range(nseg):
            ang = 2 * np.pi * j / nseg
            pts.append(c + a * off + radius * (np.cos(ang) * u + np.sin(ang) * w))
        for j in range(nseg):
            lines.append([base + j, base + (j + 1) % nseg])
    for j in range(0, nseg, max(1, nseg // nvert)):
        lines.append([j, nseg + j])
    ls = o3d.geometry.LineSet()
    ls.points = o3d.utility.Vector3dVector(np.array(pts))
    ls.lines = o3d.utility.Vector2iVector(np.array(lines))
    ls.colors = o3d.utility.Vector3dVector(np.tile(color, (len(lines), 1)))
    return ls


def read_dets(path, key, rkey, hkey):
    with open(path) as f:
        d = json.load(f)
    out = []
    for x in d.get(key, []):
        out.append((x["center"], x["axis"], x[rkey],
                    x.get(hkey) or x.get("extent_m") or x.get("height_m") or 0.4))
    return out


def autocrop(path, thresh=25, pad=45):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    arr = np.asarray(im).astype(int)
    d = np.abs(arr - arr[2, 2]).sum(2)
    # flatten the near-uniform background to pure white so it blends on slides
    arr[d <= thresh] = 255
    ys, xs = np.where(d > thresh)
    if len(xs) == 0:
        Image.fromarray(arr.astype("uint8")).save(path)
        return
    l = max(0, xs.min() - pad); r = min(arr.shape[1], xs.max() + pad)
    t = max(0, ys.min() - pad); b = min(arr.shape[0], ys.max() + pad)
    Image.fromarray(arr.astype("uint8")).crop((l, t, r, b)).save(path)


def render(geoms, out, direction, dist=0.55, up=(0, -1, 0), lookat=None,
           bg=(1, 1, 1, 1)):
    r = rendering.OffscreenRenderer(W, H)
    r.scene.set_background(list(bg))
    r.scene.scene.set_sun_light([0.3, -0.6, -0.7], [1, 1, 1], 90000)
    r.scene.scene.enable_sun_light(True)
    pmat = rendering.MaterialRecord(); pmat.shader = "defaultUnlit"
    pmat.point_size = 5.0
    for i, (g, kind) in enumerate(geoms):
        if kind == "cloud":
            r.scene.add_geometry(f"g{i}", g, pmat)
        elif kind == "line":
            lm = rendering.MaterialRecord(); lm.shader = "unlitLine"
            lm.line_width = 4.0
            r.scene.add_geometry(f"g{i}", g, lm)
        else:
            mm = rendering.MaterialRecord(); mm.shader = "defaultLit"
            col = np.asarray(g.vertex_colors)[0] if len(g.vertex_colors) else [1, 0, 0]
            mm.base_color = [float(col[0]), float(col[1]), float(col[2]), 1.0]
            mm.base_roughness = 0.65
            r.scene.add_geometry(f"g{i}", g, mm)
    center = np.asarray(lookat if lookat is not None
                        else r.scene.bounding_box.get_center(), float)
    d = np.asarray(direction, float); d = d / np.linalg.norm(d)
    r.scene.camera.look_at(center, center + d * dist, list(up))
    img = r.render_to_image()
    o3d.io.write_image(out, img, 9)
    del r
    autocrop(out)
    print("wrote", out)


RED = (0.90, 0.16, 0.16)
GREEN = (0.18, 0.75, 0.25)


def main():
    # ---- REAL: cloud + detection (ransac) ----
    sc = P("data", "real", "xtion02_crop")
    pcd = color_by_depth(load_cloud(sc)).voxel_down_sample(0.005)
    dets = read_dets(P("methods", "ransac_cylinder", "results", "xtion02_crop",
                       "predictions.json"), "detections", "radius_m", "extent_m")
    geoms = [(pcd, "cloud")]
    for cen, ax, r_, h_ in dets:
        geoms.append((cyl_from(cen, ax, r_, h_, RED), "cyl"))
    ctr = pcd.get_center()
    render(geoms, os.path.join(ASSETS, "real_3d_det.png"),
           direction=(0.4, -0.5, -1.0), dist=0.5, lookat=ctr)

    # ---- SYNTH: cloud + detection (red) + gt (green outer shell) ----
    sc = P("data", "synth", "synth_half")
    pcd = color_by_depth(load_cloud(sc)).voxel_down_sample(0.005)
    dets = read_dets(P("methods", "ransac_cylinder", "results",
                       "synth_half", "predictions.json"),
                     "detections", "radius_m", "extent_m")
    gts = read_dets(P("data", "synth", "synth_half", "gt.json"),
                    "barrels", "radius_m", "height_m")
    geoms = [(pcd, "cloud")]
    for cen, ax, r_, h_ in dets:
        geoms.append((cyl_from(cen, ax, r_, h_, RED), "cyl"))
    _ = gts  # GT/fit agreement is shown crisply in the 2D overlay figure
    ctr = pcd.get_center()
    render(geoms, os.path.join(ASSETS, "synth_3d_det_gt.png"),
           direction=(0.45, -0.45, -1.0), dist=0.55, lookat=ctr)

    # ---- REAL raw cloud only ----
    sc = P("data", "real", "xtion02_crop")
    pcd = color_by_depth(load_cloud(sc))
    render([(pcd, "cloud")], os.path.join(ASSETS, "real_3d_raw.png"),
           direction=(0.4, -0.5, -1.0), dist=0.5, lookat=pcd.get_center())


if __name__ == "__main__":
    main()
