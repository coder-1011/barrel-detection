# station1_pit_barrels — drum candidates & verified annotations (2026-07-02)

Semi-automatic annotation of the tumbled 200 L drum pile: a **fixed-radius
(r = 0.286 m) sliding-window RANSAC** proposed 42 cylinder candidates over the
scene; the strongest 21 were **human-verified in CloudCompare** (all confirmed as
real drums) and stored as the scene's `../gt.json` plus per-point labels here.

**PARTIAL coverage:** the pile contains more drums than these 21 — user estimate
is that only **~30 %** of the drums were detected. So:
- fine as **positive training samples** (per-object patches, instance labels);
- **not** an exhaustive GT — do not count detections on unlabeled drums as false
  positives when evaluating on this scene.

## Files

| file | what |
|---|---|
| `../gt.json` | 21 verified barrels (center/axis/radius/height/occlusion, provenance per entry). id 0 = the original CloudCompare-segment fit (a 2-coaxial-drum blob, h 1.11 m); ids 1–20 = verified detector fits. |
| `point_labels.npz` | per-point instance labels for `../scan000.pcd` (`labels`: int array, −1 = background, else barrel id; 21,870 labeled wall points of 106,905). |
| `segments_auto/barrel_NN.xyz` | each barrel's wall points (ASCII xyz, meters) — ready for `common/fit_from_segments.py` or per-object training (BarrelNet-style). |
| `drum_candidates.json` | all 42 raw detector candidates (center/axis/inliers/rms/arc-coverage/extent) incl. the ~21 not yet reviewed/weaker ones. |
| `scan000_drums_colored.ply` + `legend.{png,json}` | the CloudCompare verification cloud (each candidate's wall points colored) and its color↔ID legend. |
| `drum_map_topdown.png`, `barrels_view_*.png`, `colored_preview.png` | rendered figures (top-down candidate map, 3D cylinder overlays). |
| `tools/` | the scripts that produced everything (run with `.venv/bin/python`): `find_drums.py` (search) → `verify_drums.py` (scoring/inlier check) → `color_drums.py` (verification PLY) → `show_barrels.py` (3D renders) → `store_annotations.py` (gt.json + labels + segments). NB they were written to run from the session scratchpad — check the hardcoded paths at the top before re-running. |

## Method (short)

Grid of 0.35 m-spaced windows (1.1 m square) over the pile → per window, RANSAC a
radius-locked cylinder from point-pair normals (axis = n_i × n_j, center =
p_i ± R·n_i, inliers within 2.5 cm of the R-shell with radial normals) → refine
axis (normal-covariance smallest eigenvector) + center (fixed-R Gauss–Newton
circle) → gate on inliers/RMS/arc-coverage/extent → merge within 0.35 m.
Independent corroboration: the cap-disc prototype hits
(`methods/efficient_ransac/results/station1_pit_barrels/cap_candidates.json`);
9 candidates agree within ≤ 0.2 m. Detector re-found the pre-existing manual GT
drum 0.13 m off its annotated center.

## Known gaps / next steps

- ~70 % of drums undetected: mostly heavily buried / cap-only / deep-shadow ones
  the wall-fit can't see. Options: lower the inlier/coverage gates and review the
  weaker `drum_candidates.json` entries; cap-disc search for near-vertical buried
  drums; manual CloudCompare crops for the rest.
- Detector fits are radius-locked but axes from partial arcs — a few degrees /
  cm of error is expected; re-fit any barrel from its `segments_auto/` points if
  higher precision GT is needed.
