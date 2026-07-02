"""Store the human-verified drum candidates as scene annotations:
- expanded (PARTIAL) gt.json for data/real/station1_pit_barrels
- per-point instance labels (point_labels.npz)
- per-drum point segments (candidates/segments_auto/*.xyz)
User verified ALL colored candidates in CloudCompare 2026-07-02; D22 duplicates the
original barrel_00 annotation and is merged into it.
"""
import json, os
import numpy as np
import open3d as o3d

ROOT = "/home/bharath/Projects/masters/data/real/station1_pit_barrels"
SCR = os.path.dirname(os.path.abspath(__file__))
CAND = f"{ROOT}/candidates"
SEG = f"{CAND}/segments_auto"
os.makedirs(SEG, exist_ok=True)
R = 0.286

pts = np.asarray(o3d.io.read_point_cloud(f"{ROOT}/scan000.pcd").points)
pc = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(pts))
pc.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=0.06, max_nn=30))
N = np.asarray(pc.normals)
cands = json.load(open(f"{CAND}/drum_candidates.json"))
gt0 = json.load(open(f"{ROOT}/gt.json"))["barrels"][0]

# ordered verified list: (source, tier). barrel_00 keeps its CloudCompare-segment fit
# and absorbs detector hit D22 (0.13 m away). All others come from the detector fits.
ORDER = ([("gt0", "annotation-fit (absorbs D22)")] +
         [(i, "detector, GT-adjacent") for i in (40, 16)] +
         [(i, "detector+cap agreement") for i in (2, 3, 5, 15, 21, 24, 31, 37, 38)] +
         [(i, "detector wall-fit") for i in (1, 4, 6, 7, 9, 11, 19, 20)] +
         [(0, "detector wall-fit (near scan nadir)")])

barrels, label = [], np.full(len(pts), -1, int)
for bid, (src, tier) in enumerate(ORDER):
    if src == "gt0":
        ctr = np.array(gt0["center"]); a = np.array(gt0["axis"], float)
        half = gt0["height_m"] / 2
        entry = dict(gt0)
    else:
        c = cands[src]
        ctr = np.array(c["center"]); a = np.array(c["axis"], float)
        half = max(0.45, c["extent"] / 2)
        entry = {
            "id": None, "radius_m": R,
            "axis": [round(float(v), 4) for v in a],
            "center": [round(float(v), 4) for v in ctr],
            "height_m": round(float(min(c["extent"], 1.2)), 3),
            "occlusion_frac": round(1.0 - float(c["coverage"]), 2),
            "fit_rms_m": round(float(c["rms"]), 4),
        }
    a = a / np.linalg.norm(a)
    d = pts - ctr
    t = d @ a
    perp = d - np.outer(t, a)
    rd = np.linalg.norm(perp, axis=1)
    rdir = perp / np.where(rd[:, None] < 1e-9, 1e-9, rd[:, None])
    inl = (np.abs(rd - R) < 0.03) & (np.abs(np.einsum('ij,ij->i', rdir, N)) > 0.7) \
          & (np.abs(t) < half) & (label < 0)
    label[inl] = bid
    entry["id"] = bid
    entry["source"] = ("CloudCompare segment + radius-locked fit" if src == "gt0"
                       else f"fixed-R sliding-window RANSAC candidate D{src}")
    entry["provenance"] = tier
    entry["verified"] = "human (CloudCompare, 2026-07-02)"
    entry["n_wall_points"] = int(inl.sum())
    barrels.append(entry)
    np.savetxt(f"{SEG}/barrel_{bid:02d}.xyz", pts[label == bid], fmt="%.4f")
    tag = "barrel_00" if src == "gt0" else f"D{src}"
    print(f"id {bid:2d} <- {tag:<9} wall_pts={inl.sum():5d} tilt="
          f"{np.degrees(np.arccos(min(1, abs(a[2])))):3.0f}deg")

gt = {
    "scene": "station1_pit_barrels",
    "source": "real_survey_lidar (annotation pipeline + verified detector candidates)",
    "sensor": "survey_lidar",
    "units": "m",
    "frame": "local_meters (de-offset site coords; z up)",
    "partial": True,
    "note": ("PARTIAL ground truth: 21 human-verified drums (CloudCompare review of "
             "detector candidates, 2026-07-02), but the pile contains MORE unannotated "
             "drums (user estimate: only ~30% detected). Use as positive training/eval "
             "samples; do NOT treat detections on unlabeled drums as false positives. "
             "id 0 is the original 2-coaxial-drum annotation (h=1.11 m). Detector-fit "
             "axes/centers are radius-locked RANSAC fits, typical center accuracy a "
             "few cm; per-point instance labels in candidates/point_labels.npz."),
    "drum_prior": {"radius_m": R, "nominal_height_m": 0.85},
    "barrels": barrels,
}
json.dump(gt, open(f"{ROOT}/gt.json", "w"), indent=1)
np.savez_compressed(f"{CAND}/point_labels.npz", labels=label,
                    ids=np.array([b["id"] for b in barrels]))
print(f"\n{len(barrels)} barrels -> gt.json; labeled pts: {(label >= 0).sum():,} "
      f"of {len(pts):,}; segments in candidates/segments_auto/")
