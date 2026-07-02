#!/usr/bin/env python3
"""BarrelNet-style drum pose regressor (PointNet, pure PyTorch — CPU-friendly,
fully offline). Predicts drum axis (sign-symmetric) + nearest point-on-axis from a
single-drum patch. Checkpoints + resumes automatically; evaluates against the 21
human-verified real drums (station1 segments_auto + gt.json) every few epochs.

Usage (unattended):
  .venv/bin/python methods/barrelnet/train.py \
      --data data/synth_patches/train --run methods/barrelnet/runs/run1 \
      --max-hours 6
"""
import argparse, glob, json, os, time
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

MASTERS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCALE = 0.5   # meters -> normalized units


class PatchSet(Dataset):
    def __init__(self, files, train=True):
        Ps, As, Cs = [], [], []
        for f in files:
            z = np.load(f)
            Ps.append(z["points"]); As.append(z["axis"]); Cs.append(z["point_on_axis"])
        self.P = np.concatenate(Ps); self.A = np.concatenate(As)
        self.C = np.concatenate(Cs); self.train = train

    def __len__(self):
        return len(self.P)

    def __getitem__(self, i):
        pts = self.P[i].copy(); ax = self.A[i].copy(); ctr = self.C[i].copy()
        cen = pts.mean(0)
        pts, ctr = (pts - cen) / SCALE, (ctr - cen) / SCALE
        if self.train:   # augment: random rotation about z + jitter
            th = np.random.uniform(0, 2 * np.pi)
            c, s = np.cos(th), np.sin(th)
            Rz = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], np.float32)
            pts, ax, ctr = pts @ Rz.T, ax @ Rz.T, ctr @ Rz.T
            pts = pts + np.random.normal(0, 0.004, pts.shape).astype(np.float32)
        return pts.astype(np.float32), ax.astype(np.float32), ctr.astype(np.float32)


class PointNetReg(nn.Module):
    def __init__(self):
        super().__init__()
        self.enc = nn.Sequential(
            nn.Conv1d(3, 64, 1), nn.BatchNorm1d(64), nn.ReLU(),
            nn.Conv1d(64, 128, 1), nn.BatchNorm1d(128), nn.ReLU(),
            nn.Conv1d(128, 256, 1), nn.BatchNorm1d(256), nn.ReLU(),
            nn.Conv1d(256, 512, 1), nn.BatchNorm1d(512), nn.ReLU())
        self.head = nn.Sequential(
            nn.Linear(512, 256), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(256, 128), nn.ReLU(),
            nn.Linear(128, 6))          # 3 axis + 3 point-on-axis

    def forward(self, x):               # x: (B, N, 3)
        f = self.enc(x.transpose(1, 2)).max(dim=2).values
        o = self.head(f)
        ax = nn.functional.normalize(o[:, :3], dim=1)
        return ax, o[:, 3:]


def axis_loss(pred, gt):                # sign-symmetric
    return (1.0 - (pred * gt).sum(1).abs()).mean()


def load_real():
    """The 21 verified station1 drums -> (patch, axis, center) in meters."""
    scene = os.path.join(MASTERS, "data/real/station1_pit_barrels")
    gt = json.load(open(os.path.join(scene, "gt.json")))["barrels"]
    out = []
    for b in gt:
        f = os.path.join(scene, "candidates/segments_auto", f"barrel_{b['id']:02d}.xyz")
        if not os.path.exists(f):
            continue
        pts = np.loadtxt(f, dtype=np.float32)
        if pts.ndim != 2 or len(pts) < 60:
            continue
        out.append((pts, np.array(b["axis"], np.float32),
                    np.array(b["center"], np.float32)))
    return out


@torch.no_grad()
def eval_real(model, real, npoints, dev):
    model.eval()
    angs, dists = [], []
    for pts, ax_gt, ctr_gt in real:
        idx = np.random.default_rng(0).choice(
            len(pts), npoints, replace=len(pts) < npoints)
        p = pts[idx]
        cen = p.mean(0)
        x = torch.from_numpy((p - cen)[None] / SCALE).float().to(dev)
        ax, poa = model(x)
        ax = ax[0].cpu().numpy()
        poa = poa[0].cpu().numpy() * SCALE + cen
        ang = np.degrees(np.arccos(min(1.0, abs(float(ax @ ax_gt)))))
        d = ctr_gt - poa                                  # gt center -> pred axis line
        dist = float(np.linalg.norm(d - (d @ ax) * ax))
        angs.append(ang); dists.append(dist)
    hits = sum(1 for a, d in zip(angs, dists) if a <= 30 and d <= 0.10)
    return float(np.mean(angs)), float(np.median(angs)), float(np.mean(dists)), \
        float(np.median(dists)), hits, len(angs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="dir with patches_*.npz")
    ap.add_argument("--run", required=True, help="output dir (ckpts, log)")
    ap.add_argument("--epochs", type=int, default=200)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--val-frac", type=float, default=0.1)
    ap.add_argument("--max-hours", type=float, default=8.0)
    ap.add_argument("--threads", type=int, default=12)
    args = ap.parse_args()
    torch.set_num_threads(args.threads)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {dev}", flush=True)
    os.makedirs(args.run, exist_ok=True)
    log = open(os.path.join(args.run, "train_log.csv"), "a", buffering=1)
    if log.tell() == 0:
        log.write("epoch,train_loss,val_loss,val_axis_deg,real_axis_deg_med,"
                  "real_dist_m_med,real_hits,elapsed_min\n")

    files = sorted(glob.glob(os.path.join(args.data, "patches_*.npz")))
    assert files, f"no patches_*.npz in {args.data} — run gen_synth_patches.py first"
    full = PatchSet(files, train=True)
    n_val = max(64, int(len(full) * args.val_frac))
    g = torch.Generator().manual_seed(0)
    tr, va = torch.utils.data.random_split(full, [len(full) - n_val, n_val], generator=g)
    va.dataset = PatchSet(files, train=False)   # no augmentation on val
    print(f"train {len(tr)}  val {n_val}  real {len(load_real())} drums", flush=True)
    tl = DataLoader(tr, batch_size=args.batch, shuffle=True, num_workers=2)
    vl = DataLoader(va, batch_size=args.batch, num_workers=2)
    real = load_real()

    model = PointNetReg().to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    sched = torch.optim.lr_scheduler.StepLR(opt, 40, 0.5)
    start_ep, best = 0, 1e9
    ck = os.path.join(args.run, "last.pt")
    if os.path.exists(ck):                       # resume
        st = torch.load(ck, map_location=dev)
        model.load_state_dict(st["model"]); opt.load_state_dict(st["opt"])
        sched.load_state_dict(st["sched"]); start_ep = st["epoch"] + 1
        best = st.get("best", 1e9)
        print(f"resumed at epoch {start_ep}", flush=True)

    t0 = time.time()
    npoints = full.P.shape[1]
    for ep in range(start_ep, args.epochs):
        model.train(); tot = 0.0
        for pts, ax, ctr in tl:
            pts, ax, ctr = pts.to(dev), ax.to(dev), ctr.to(dev)
            opt.zero_grad()
            pax, poa = model(pts)
            loss = axis_loss(pax, ax) + 0.5 * nn.functional.mse_loss(poa, ctr)
            loss.backward(); opt.step()
            tot += float(loss.detach()) * len(pts)
        sched.step()
        tr_loss = tot / len(tr)

        model.eval(); vtot, vang = 0.0, []
        with torch.no_grad():
            for pts, ax, ctr in vl:
                pts, ax, ctr = pts.to(dev), ax.to(dev), ctr.to(dev)
                pax, poa = model(pts)
                vtot += float(axis_loss(pax, ax)
                              + 0.5 * nn.functional.mse_loss(poa, ctr)) * len(pts)
                vang += np.degrees(np.arccos(np.clip(
                    (pax * ax).sum(1).abs().cpu().numpy(), 0, 1))).tolist()
        v_loss = vtot / n_val
        am, amed, dm, dmed, hits, nreal = eval_real(model, real, npoints, dev)
        el = (time.time() - t0) / 60
        log.write(f"{ep},{tr_loss:.4f},{v_loss:.4f},{np.mean(vang):.2f},"
                  f"{amed:.2f},{dmed:.3f},{hits}/{nreal},{el:.1f}\n")
        print(f"ep {ep:3d} train {tr_loss:.4f} val {v_loss:.4f} "
              f"val-axis {np.mean(vang):5.2f}°  REAL med-axis {amed:5.1f}° "
              f"med-dist {dmed*100:4.1f}cm gate-hits {hits}/{nreal}  [{el:.0f} min]",
              flush=True)
        st = dict(model=model.state_dict(), opt=opt.state_dict(),
                  sched=sched.state_dict(), epoch=ep, best=best)
        torch.save(st, ck)
        if v_loss < best:
            best = v_loss; st["best"] = best
            torch.save(st, os.path.join(args.run, "best.pt"))
        if el > args.max_hours * 60:
            print("time budget reached — stopping cleanly", flush=True)
            break
    print("done", flush=True)


if __name__ == "__main__":
    main()
