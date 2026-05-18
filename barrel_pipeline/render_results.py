#!/usr/bin/env python3
"""
Render a multi-page PDF showing, for each data*/ scan directory:
  - the raw point cloud  (front + top 2D projections)
  - the same cloud with the detected cylinder(s) overlaid

Output: ~/masters/barrel_detection_results.pdf (one page per scan).

Loads either scan000.pcd (meters) or scan000.3d (cm) — whichever is present —
and normalizes everything to meters internally. Cylinder.2d is always in cm.
For each scan dir, the script picks the best cylinder.2d available in this
order of preference: normals_o3d/ > normals/ > <dir>/.

Coordinate convention (camera optical):  x right, y down, z forward.
"Front view" plots x vs y; "Top view" plots x vs z.
"""
import os
import re
import glob
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Circle, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PDF = os.path.expanduser("~/masters/barrel_detection_results.pdf")

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
        pts = load_pcd_ascii(pcd)
        if pts.size:
            return pts
    txt = os.path.join(dirpath, "scan000.3d")
    if os.path.isfile(txt):
        pts = load_3d(txt)
        if pts.size:
            return pts / 100.0
    return None


def find_cylinder_file(dirpath):
    candidates = [
        (os.path.join(dirpath, "normals_o3d", "detectCylinder", "cylinder.2d"), "normals_o3d"),
        (os.path.join(dirpath, "normals",     "detectCylinder", "cylinder.2d"), "normals"),
        (os.path.join(dirpath, "detectCylinder", "cylinder.2d"),                "(root)"),
    ]
    for p, label in candidates:
        if os.path.isfile(p):
            return p, label
    return None, None


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
                axis=np.array([float(x) for x in parts[2].split()]),
                start=np.array([float(x) for x in parts[3].split()]),
                end=np.array([float(x) for x in parts[4].split()]),
            ))
    return out


def project_cylinder(c, plane):
    """Return a list of matplotlib patches projecting cylinder c onto a 2D plane.
    plane in {"xy","xz"}. All cylinder coords come in cm; we return them in m.
    """
    s = c["start"] / 100.0; e = c["end"] / 100.0; r = c["radius"] / 100.0
    axis = e - s
    h = np.linalg.norm(axis)
    if h < 1e-9:
        return []

    if plane == "xy":
        i0, i1 = 0, 1
    else:
        i0, i1 = 0, 2

    # Project the axis to the chosen plane and compute the projected width.
    a2 = np.array([axis[i0], axis[i1]])
    h2 = np.linalg.norm(a2)

    s2 = np.array([s[i0], s[i1]]); e2 = np.array([e[i0], e[i1]])

    # End caps (apparent ellipses); cheap approximation: circles of radius r
    # at each end. Then a band between them for the side surface.
    patches = [Circle(s2, r, fill=False, edgecolor="red", linewidth=1.2),
               Circle(e2, r, fill=False, edgecolor="red", linewidth=1.2)]

    if h2 > 1e-6:
        # Build a rotated rectangle covering the side projection.
        u = a2 / h2          # along projected axis
        n = np.array([-u[1], u[0]])  # perpendicular
        corners = np.array([
            s2 + n * r,
            e2 + n * r,
            e2 - n * r,
            s2 - n * r,
        ])
        patches.append(plt.Polygon(corners, closed=True, fill=True,
                                   facecolor="red", edgecolor="darkred",
                                   alpha=0.18, linewidth=0.8))
    return patches


def plot_panel(ax, pts, cyls, plane, title):
    if plane == "xy":
        i0, i1, xl, yl = 0, 1, "x (m)", "y (m)"
    else:
        i0, i1, xl, yl = 0, 2, "x (m)", "z (m)"

    if pts.shape[0] > MAX_PLOT_POINTS:
        idx = np.random.choice(pts.shape[0], MAX_PLOT_POINTS, replace=False)
        ps = pts[idx]
    else:
        ps = pts

    ax.scatter(ps[:, i0], ps[:, i1], s=0.5, c=ps[:, 2],
               cmap="viridis", linewidths=0, alpha=0.6)

    for c in cyls or []:
        for patch in project_cylinder(c, plane):
            ax.add_patch(patch)

    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xlabel(xl, fontsize=8); ax.set_ylabel(yl, fontsize=8)
    ax.tick_params(labelsize=7)
    ax.set_title(title, fontsize=9)
    ax.grid(True, alpha=0.25)
    if plane == "xy":
        # camera optical: +y is down. invert so the picture matches what you'd see.
        ax.invert_yaxis()


def page_for_dir(pdf, dirpath, name):
    pts = load_cloud_meters(dirpath)
    if pts is None or pts.shape[0] == 0:
        print(f"  [skip] {name}: no cloud")
        return False
    cyl_path, src = find_cylinder_file(dirpath)
    cyls = parse_cylinder_2d(cyl_path) if cyl_path else []

    fig, axes = plt.subplots(2, 2, figsize=(11.5, 9))

    plot_panel(axes[0, 0], pts, None, "xy",
               f"raw front view (x–y)   {pts.shape[0]:,} pts")
    plot_panel(axes[0, 1], pts, None, "xz", "raw top view (x–z)")

    if cyls:
        info = ", ".join(f"r={c['radius']:.2f}cm" for c in cyls)
        det_title = f"detected: {len(cyls)} cyl ({info})   [src: {src}]"
    else:
        det_title = "no cylinder.2d found"

    plot_panel(axes[1, 0], pts, cyls, "xy", f"detection front view  —  {det_title}")
    plot_panel(axes[1, 1], pts, cyls, "xz", "detection top view")

    fig.suptitle(name, fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    pdf.savefig(fig, dpi=130)
    plt.close(fig)
    print(f"  [page] {name}: {pts.shape[0]} pts, {len(cyls)} cyl")
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
            if page_for_dir(pdf, d, name):
                n += 1
    print(f"done: {n} pages.")


if __name__ == "__main__":
    main()
