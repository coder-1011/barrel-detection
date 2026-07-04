#!/usr/bin/env python3
"""Render two clean inspection figures for the barrelnet method (headless / Agg,
no grid/panes/axes):
  1) synth_patches_sample.png  — synthetic training patches with the GT cylinder
     surface overlaid, so each clearly reads as a (partial) barrel.
  2) station_detection.png     — the WHOLE station pile (106k pts, gray) with the 21
     annotated drums coloured and BarrelNet's predicted cylinders overlaid
     (green = gate hit, red = miss).
Outputs -> methods/barrelnet/figures/.
"""
import argparse, json, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import cm  # noqa: E402
import open3d as o3d  # noqa: E402
import torch  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MASTERS = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from train import PointNetReg, SCALE  # noqa: E402

FIGDIR = os.path.join(HERE, "figures")
os.makedirs(FIGDIR, exist_ok=True)
SCENE = os.path.join(MASTERS, "data/real/station1_pit_barrels")
R_DRUM = 0.286


def basis(a):
    a = a / (np.linalg.norm(a) + 1e-9)
    t = np.array([0, 0, 1.0]) if abs(a[2]) < 0.9 else np.array([1.0, 0, 0])
    u = np.cross(a, t); u /= np.linalg.norm(u)
    v = np.cross(a, u)
    return a, u, v


def cyl_surface(c, a, r, t0, t1, ntheta=48, nt=2):
    a, u, v = basis(a)
    th = np.linspace(0, 2*np.pi, ntheta)
    tt = np.linspace(t0, t1, nt)
    T, TH = np.meshgrid(tt, th)
    P = (c[None, None, :] + T[..., None]*a
         + r*(np.cos(TH)[..., None]*u + np.sin(TH)[..., None]*v))
    return P[..., 0], P[..., 1], P[..., 2]


def clean3d(ax):
    ax.set_axis_off()
    ax.grid(False)


def equal_aspect(ax, pts):
    r = np.ptp(pts, axis=0)
    ax.set_box_aspect(tuple(r + 1e-6))


def extent_along(pts, c, a):
    a = a / (np.linalg.norm(a) + 1e-9)
    t = (pts - c) @ a
    return float(t.min()), float(t.max())


# ------------------------------------------------------------------ synth fig
def fig_synth(n=4):
    z = np.load(os.path.join(MASTERS, "data/synth_patches/train/patches_s0.npz"))
    P, A, C = z["points"], z["axis"], z["point_on_axis"]
    idx = np.linspace(0, len(P)-1, n).astype(int)
    fig = plt.figure(figsize=(5*n, 5.4))
    for k, i in enumerate(idx):
        pts, a, c = P[i], A[i], C[i]
        ax = fig.add_subplot(1, n, k+1, projection="3d")
        t0, t1 = extent_along(pts, c, a)
        X, Y, Z = cyl_surface(c, a, R_DRUM, t0, t1, nt=2)
        ax.plot_surface(X, Y, Z, color="steelblue", alpha=0.22,
                        linewidth=0, shade=True, zorder=1)
        ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2], s=6, c="crimson",
                   depthshade=False, zorder=5)
        clean3d(ax); equal_aspect(ax, pts)
        ax.view_init(elev=8, azim=-70)
        ax.set_title(f"synth patch #{i}", fontsize=12, y=0.96)
    fig.suptitle("Synthetic training patches — LiDAR points (red) on the true drum "
                 "surface (blue, r=0.286 m)", fontsize=14, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    out = os.path.join(FIGDIR, "synth_patches_sample.png")
    fig.savefig(out, dpi=140); plt.close(fig)
    return out


# ---------------------------------------------------------------- station fig
def fig_station(ckpt, cyl_drums):
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = PointNetReg().to(dev)
    st = torch.load(ckpt, map_location=dev)
    model.load_state_dict(st["model"]); model.eval()

    full = np.asarray(o3d.io.read_point_cloud(
        os.path.join(SCENE, "scan000.pcd")).points)
    lab = np.load(os.path.join(SCENE, "candidates/point_labels.npz"))["labels"]
    gt = {b["id"]: b for b in json.load(open(os.path.join(SCENE, "gt.json")))["barrels"]}

    # crop the whole scene to a tight box around the drum cluster so the pile fills
    # the frame (the raw survey floor extends far and dwarfs the drums otherwise)
    drum_pts = full[lab != -1]
    lo = drum_pts.min(0) - 0.5
    hi = drum_pts.max(0) + 0.5
    inbox = np.all((full >= lo) & (full <= hi), axis=1)
    bg = full[(lab == -1) & inbox]
    rng = np.random.default_rng(0)
    if len(bg) > 30000:
        bg = bg[rng.choice(len(bg), 30000, replace=False)]

    fig = plt.figure(figsize=(16, 12))
    ax = fig.add_subplot(111, projection="3d")
    ax.scatter(bg[:, 0], bg[:, 1], bg[:, 2], s=2, c="0.75",
               alpha=0.30, depthshade=False, zorder=0)

    cmap = matplotlib.colormaps["tab20"].resampled(21)
    for did in gt:
        dp = full[lab == did]
        if len(dp) == 0:
            continue
        ax.scatter(dp[:, 0], dp[:, 1], dp[:, 2], s=5, color=cmap(did),
                   depthshade=False, zorder=3)

    # overlay BarrelNet's predicted cylinders on a representative subset
    for did in cyl_drums:
        f = os.path.join(SCENE, "candidates/segments_auto", f"barrel_{did:02d}.xyz")
        pts = np.loadtxt(f, dtype=np.float32)
        ii = np.random.default_rng(0).choice(len(pts), 512, replace=len(pts) < 512)
        p = pts[ii]; cen = p.mean(0)
        with torch.no_grad():
            a, poa = model(torch.from_numpy((p-cen)[None]/SCALE).float().to(dev))
        a = a[0].cpu().numpy(); poa = poa[0].cpu().numpy()*SCALE + cen
        b = gt[did]
        ang = np.degrees(np.arccos(min(1.0, abs(float(a @ np.array(b["axis"]))))))
        d = np.array(b["center"]) - poa
        dist = float(np.linalg.norm(d - (d @ a)*a))
        hit = ang <= 30 and dist <= 0.10
        t0, t1 = extent_along(pts, poa, a)
        X, Y, Z = cyl_surface(poa, a, R_DRUM, t0, t1, nt=2)
        ax.plot_surface(X, Y, Z, color=("limegreen" if hit else "red"),
                        alpha=0.30, linewidth=0, shade=True, zorder=6)

    clean3d(ax)
    ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
    ax.set_box_aspect(tuple(hi - lo), zoom=1.5)
    ax.view_init(elev=32, azim=-60)
    ax.set_position([0.0, 0.0, 1.0, 0.93])
    ep = st.get("epoch", "?")
    fig.suptitle(f"BarrelNet on the station pile — annotated drums coloured, "
                 f"predicted cylinders overlaid\n"
                 f"(green = gate hit, red = miss; ckpt epoch {ep})",
                 fontsize=15, y=0.97)
    out = os.path.join(FIGDIR, "station_detection.png")
    fig.savefig(out, dpi=140); plt.close(fig)
    return out


# ------------------------------------------------- full-pile detections fig
def fig_full_detections(pred_json):
    """3D view of the pile with EVERY run_detection.sh cylinder overlaid:
    green = matched to a verified GT drum (std gate), orange = detection on the
    unannotated ~70% of the pile (candidate drum, not countable as FP)."""
    sys.path.insert(0, os.path.join(MASTERS, "common"))
    from eval_schema import load_gt, load_pred, match

    full = np.asarray(o3d.io.read_point_cloud(
        os.path.join(SCENE, "scan000.pcd")).points)
    lab = np.load(os.path.join(SCENE, "candidates/point_labels.npz"))["labels"]
    gt = load_gt(os.path.join(SCENE, "gt.json"))
    pred = load_pred(pred_json)
    pairs, _, unmatched = match(gt["barrels"], pred["detections"])
    matched_di = {di for _, di in pairs}

    drum_pts = full[lab != -1]
    lo = drum_pts.min(0) - 0.5
    hi = drum_pts.max(0) + 0.5
    inbox = np.all((full >= lo) & (full <= hi), axis=1)
    bg = full[(lab == -1) & inbox]
    rng = np.random.default_rng(0)
    if len(bg) > 30000:
        bg = bg[rng.choice(len(bg), 30000, replace=False)]

    fig = plt.figure(figsize=(22, 11))

    # ---- left: top-down map (clearest read of what was found where) ----
    ax = fig.add_subplot(121)
    ax.scatter(bg[:, 0], bg[:, 1], s=1.0, c=bg[:, 2], cmap="Greys_r",
               linewidths=0)
    ax.scatter(drum_pts[:, 0], drum_pts[:, 1], s=1.5, c="0.45", linewidths=0)
    th = np.linspace(0, 2 * np.pi, 60)
    for di, d in enumerate(pred["detections"]):
        c = d.center
        col, lw = ("limegreen", 2.2) if di in matched_di else ("darkorange", 1.4)
        ax.plot(c[0] + d.radius_m * np.cos(th), c[1] + d.radius_m * np.sin(th),
                color=col, lw=lw)
    for b in gt["barrels"]:
        ax.plot(b.center[0], b.center[1], "+", color="crimson", ms=11, mew=2.2)
    ax.plot([], [], "-", color="limegreen", lw=2.2, label="detection matched to GT")
    ax.plot([], [], "-", color="darkorange", lw=1.4, label="candidate (unannotated)")
    ax.plot([], [], "+", color="crimson", ms=11, mew=2.2,
            label="verified GT drum center")
    ax.legend(loc="lower left", fontsize=11)
    ax.set_aspect("equal"); ax.set_axis_off()
    ax.set_title("top-down", fontsize=13)

    # ---- right: 3D view, matched drums emphasized ----
    ax = fig.add_subplot(122, projection="3d")
    ax.scatter(bg[:, 0], bg[:, 1], bg[:, 2], s=2, c="0.8",
               alpha=0.25, depthshade=False, zorder=0)
    cmap = matplotlib.colormaps["tab20"].resampled(21)
    for b in gt["barrels"]:
        dp = full[lab == b.id]
        if len(dp):
            ax.scatter(dp[:, 0], dp[:, 1], dp[:, 2], s=4, color=cmap(b.id),
                       depthshade=False, zorder=3)
    for di, d in enumerate(pred["detections"]):
        c, a = np.array(d.center), np.array(d.axis)
        h = (d.extent_m or 0.85) / 2
        X, Y, Z = cyl_surface(c, a, d.radius_m, -h, h, nt=2)
        if di in matched_di:
            ax.plot_surface(X, Y, Z, color="limegreen", alpha=0.35,
                            linewidth=0, shade=True, zorder=6)
        else:
            ax.plot_surface(X, Y, Z, color="darkorange", alpha=0.10,
                            linewidth=0, shade=False, zorder=2)
    clean3d(ax)
    ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
    ax.set_box_aspect(tuple(hi - lo), zoom=1.35)
    ax.view_init(elev=50, azim=-60)
    ax.set_title("3D (matched cylinders solid green)", fontsize=13)

    nm, nd, ng = len(matched_di), len(pred["detections"]), len(gt["barrels"])
    fig.suptitle(f"BarrelNet full-pile detection — {nd} detections, "
                 f"{nm}/{ng} verified drums matched "
                 f"(GT covers only ~30% of the pile)", fontsize=16, y=0.98)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out = os.path.join(FIGDIR, "station_full_detect_3d.png")
    fig.savefig(out, dpi=140); plt.close(fig)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default=os.path.join(HERE, "runs/run1/last.pt"))
    ap.add_argument("--full-detections", default=None, metavar="PRED_JSON",
                    help="render ONLY the full-pile detections figure from a "
                         "run_detection.sh predictions.json")
    args = ap.parse_args()
    if args.full_detections:
        print("wrote:", fig_full_detections(args.full_detections))
    else:
        o1 = fig_synth(4)
        o2 = fig_station(args.ckpt, cyl_drums=[0, 15, 16, 5])
        print("wrote:", o1)
        print("wrote:", o2)
