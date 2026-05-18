#!/usr/bin/env python3
"""
Simple per-scan results PDF: one page per scan, two side-by-side panels
(raw point cloud / cloud with detected cylinder overlay), each captioned
with the terminal command to reproduce that view from ~/masters/.

Output: ~/masters/barrel_detection_simple.pdf
"""
import os
import re
import glob
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PDF = os.path.expanduser("~/masters/barrel_detection_simple.pdf")

MAX_PLOT_POINTS = 30000


def load_pcd_ascii(path):
    pts = []
    with open(path) as f:
        in_data = False
        for line in f:
            if in_data:
                parts = line.strip().split()
                if len(parts) >= 3:
                    pts.append([float(parts[0]), float(parts[1]), float(parts[2])])
            elif line.startswith("DATA"):
                in_data = True
    return np.array(pts, dtype=float)


def load_3d(path):
    return np.loadtxt(path)[:, :3]


def load_cloud_meters(dirpath):
    pcd = os.path.join(dirpath, "scan000.pcd")
    if os.path.isfile(pcd):
        return load_pcd_ascii(pcd), True
    txt = os.path.join(dirpath, "scan000.3d")
    if os.path.isfile(txt):
        return load_3d(txt) / 100.0, False
    return None, False


def find_cylinder_file(dirpath):
    """Return (absolute path, repo-relative path from ~/masters, sub-label)."""
    masters = os.path.expanduser("~/masters")
    candidates = [
        (os.path.join(dirpath, "normals_o3d", "detectCylinder", "cylinder.2d"), "normals_o3d"),
        (os.path.join(dirpath, "normals",     "detectCylinder", "cylinder.2d"), "normals"),
        (os.path.join(dirpath, "detectCylinder", "cylinder.2d"),                "(root)"),
    ]
    for p, label in candidates:
        if os.path.isfile(p):
            return p, os.path.relpath(p, masters), label
    return None, None, None


def parse_cylinder_2d(path):
    out = []
    with open(path) as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = [p.strip() for p in s.split(";")]
            if len(parts) < 5:
                continue
            out.append(dict(
                radius=float(parts[1]),
                start=np.array([float(x) for x in parts[3].split()]),
                end=np.array([float(x) for x in parts[4].split()]),
            ))
    return out


def draw_cloud(ax, pts):
    if pts.shape[0] > MAX_PLOT_POINTS:
        idx = np.random.choice(pts.shape[0], MAX_PLOT_POINTS, replace=False)
        pts = pts[idx]
    ax.scatter(pts[:, 0], pts[:, 1], s=0.6, c=pts[:, 2],
               cmap="viridis", linewidths=0, alpha=0.7)


def draw_cylinders(ax, cyls):
    """Side projection on xy: rectangle along the axis + end-cap circles."""
    for c in cyls:
        s = c["start"] / 100.0; e = c["end"] / 100.0; r = c["radius"] / 100.0
        s2 = np.array([s[0], s[1]]); e2 = np.array([e[0], e[1]])
        a = e2 - s2; h = np.linalg.norm(a)
        ax.add_patch(plt.Circle(s2, r, fill=False, edgecolor="red", linewidth=1.4))
        ax.add_patch(plt.Circle(e2, r, fill=False, edgecolor="red", linewidth=1.4))
        if h > 1e-6:
            u = a / h
            n = np.array([-u[1], u[0]])
            corners = np.array([s2 + n * r, e2 + n * r, e2 - n * r, s2 - n * r])
            ax.add_patch(plt.Polygon(corners, closed=True, fill=True,
                                     facecolor="red", edgecolor="darkred",
                                     alpha=0.22, linewidth=0.9))


def style_axes(ax, title):
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xlabel("x (m)", fontsize=8); ax.set_ylabel("y (m)", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.set_title(title, fontsize=10)
    ax.grid(True, alpha=0.25)
    ax.invert_yaxis()  # camera optical: +y is down


def page(pdf, dirpath, name):
    pts, has_pcd = load_cloud_meters(dirpath)
    if pts is None or pts.shape[0] == 0:
        return False
    cyl_abs, cyl_rel, src = find_cylinder_file(dirpath)
    cyls = parse_cylinder_2d(cyl_abs) if cyl_abs else []

    fig = plt.figure(figsize=(11.5, 7.0))

    # left: raw
    ax1 = fig.add_axes([0.05, 0.30, 0.42, 0.58])
    draw_cloud(ax1, pts)
    style_axes(ax1, f"raw point cloud  ({pts.shape[0]:,} pts)")

    # right: with detection
    ax2 = fig.add_axes([0.53, 0.30, 0.42, 0.58])
    draw_cloud(ax2, pts)
    if cyls:
        draw_cylinders(ax2, cyls)
        radii = ", ".join(f"r={c['radius']:.2f}cm" for c in cyls)
        ax2.set_title(f"with detection  ({len(cyls)} cyl: {radii})", fontsize=10)
    else:
        ax2.set_title("with detection  (none found)", fontsize=10)
    style_axes(ax2, ax2.get_title())

    # title
    fig.text(0.5, 0.95, name, ha="center", fontsize=14, fontweight="bold")

    # commands below each panel (paths relative to ~/masters)
    pcd_rel = f"barrel_pipeline/{name}/scan000.pcd"
    if has_pcd:
        cmd_raw = f"$ python3 barrel_pipeline/view_cloud.py --pcd {pcd_rel}"
        if cyls and cyl_rel:
            cmd_det = (f"$ python3 barrel_pipeline/view_cloud.py --pcd {pcd_rel} \\\n"
                       f"      --cylinders {cyl_rel}")
        else:
            cmd_det = "# no cylinder.2d available for this scan"
    else:
        cmd_raw = f"# no scan000.pcd in this dir (only scan000.3d in cm)"
        cmd_det = "# view_cloud.py needs a PCD file; regenerate one if needed"

    fig.text(0.05, 0.22, "View from ~/masters/ :", fontsize=9, fontweight="bold")
    fig.text(0.05, 0.16, cmd_raw, fontsize=9, family="monospace")
    fig.text(0.53, 0.22, "View from ~/masters/ :", fontsize=9, fontweight="bold")
    fig.text(0.53, 0.16, cmd_det, fontsize=9, family="monospace")

    pdf.savefig(fig, dpi=130)
    plt.close(fig)
    return True


def natural_key(s):
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", s)]


def main():
    np.random.seed(0)
    dirs = sorted(glob.glob(os.path.join(HERE, "data*")),
                  key=lambda p: natural_key(os.path.basename(p)))
    real  = [d for d in dirs if not os.path.basename(d).startswith("data_synth")]
    synth = [d for d in dirs if     os.path.basename(d).startswith("data_synth")]
    ordered = real + synth

    print(f"writing {OUT_PDF}")
    n = 0
    with PdfPages(OUT_PDF) as pdf:
        for d in ordered:
            name = os.path.basename(d)
            if page(pdf, d, name):
                n += 1
                print(f"  [page] {name}")
            else:
                print(f"  [skip] {name}: no cloud")
    print(f"done: {n} pages.")


if __name__ == "__main__":
    main()
