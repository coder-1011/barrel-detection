# Progress Presentation — DRAFT

**Thesis (working title):** *Detection and Manipulation of Semi-Occluded Objects*
**Topic:** Barrel / cylinder detection in 3D point clouds — and a systematic comparison of detection methods, especially under occlusion and partial burial.
**Format:** ~15 min progress talk · 14 slides · ~1 min/slide

> DRAFT for the student to review and edit. Speaker notes are one line each.
> Numbers are pulled from the project memory as of 2026-06-30 — placeholders are flagged with **[FILL]**.

---

## Slide 1 — Title

- *Detection and Manipulation of Semi-Occluded Objects*
- Barrel / cylinder detection in 3D LiDAR & depth point clouds
- Master's thesis — progress review
- [Your name], [supervisor], [date]

_Speaker notes:_ One sentence: "My thesis is about detecting barrels in 3D point clouds and fairly comparing the methods that can do it, with a focus on occlusion."

---

## Slide 2 — The Problem & Why It Matters

- Goal: find barrels (cylinders) in 3D point clouds and recover their pose (center, axis, radius)
- Real-world setting: drums that are **partially buried in sand** and **mutually occluding** in a pile
- Application context: industrial / environmental survey of drum sites (Bilfinger-facing use case)
- Hard part: from one viewpoint you often see only a thin arc of each barrel, not the whole surface

_Speaker notes:_ Motivate with the buried/occluded drum pile — that is the scenario that makes naive cylinder fitting fail.

---

## Slide 3 — Background: 3D Point Clouds & the Occlusion Challenge

- A point cloud = unordered set of 3D points from a depth/LiDAR sensor; no connectivity, variable density
- Single-viewpoint scans give **partial coverage**: top caps, short wall sections, radial scan-shadows
- Occlusion ⇒ each barrel may show only ~120–200° of arc → ambiguous radius/axis
- Burial removes the bottom of the cylinder; clutter and ground make segmentation hard
- This is exactly where methods diverge — so it is the right axis to benchmark on

_Speaker notes:_ Emphasize that occlusion is not an edge case here, it is the central difficulty and the variable I want to measure against.

---

## Slide 4 — Sensors & Data Sources

- **Asus Xtion Pro** depth camera — lab captures, range 0.5–3.5 m; small ~8.5 cm-diameter test barrel
- **Terrestrial / HV survey LiDAR** — a real occluded scene: a tumbled pile of **standard 200 L oil drums** (r = 0.286 m), partially buried, arbitrary orientations (~1.23 M pts, single station)
- **Synthetic cylinders** — analytically generated arcs + noise sweep for controlled tests
- **Future: NVIDIA Isaac Sim** — RTX LiDAR + co-registered camera with full ground truth (planned)

_Speaker notes:_ Three real/synthetic sources today, simulation is the planned fourth that unlocks perfect ground truth.

---

## Slide 5 — Research Aim & Questions

- This is an **empirical, systematic comparison** — NOT defending one predetermined hypothesis
- RQ1: Which method detects barrels best, especially under occlusion / partial burial?
- RQ2: How do precision/recall and pose error move as occlusion increases, per method?
- RQ3: When (if ever) does camera+LiDAR fusion beat LiDAR-only? Geometric vs learned once annotation cost is counted?
- Trade-offs are findings to **measure**, not assume

_Speaker notes:_ Stress the framing correction: the deliverable is the comparison itself, every "X beats Y" claim is a measurement.

---

## Slide 6 — Methods Being Compared (Three Families)

- **LiDAR-only geometric:** randomized Hough, RANSAC cylinder, least-squares fit, region-growing, clustering+fit
- **LiDAR-only learned:** PointNet++, BarrelNet-style, voxel detectors (CenterPoint / PV-RCNN via OpenPCDet)
- **Camera+LiDAR fusion:** camera-first (YOLO → frustum → fit, Frustum-PointNet); LiDAR-first (3D proposals → image verification, PointPainting)
- Closest prior work: **BarrelNet** (Yan et al., OCEANS 2024) — PointNet on synthetic occluded/buried cylinders (no public code)
- Backed by a 9-page literature survey: 18-method comparison table + occlusion-suitability rubric

_Speaker notes:_ Point to the survey PDF; note the families and that BarrelNet is the nearest neighbour to my problem.

---

## Slide 7 — Architecture & Method Contract

- Key design split: **proposer** ("a barrel is here") separated from the **metric fit** (radius/axis/pose)
- Fit is reusable: `points_of_one_barrel → cylinder_pose`; proposer can be swapped (clustering → camera frustum)
- Uniform method contract: `run_detection.sh <scene-dir>` → `results/<scene>/predictions.json` (meters)
- All methods read the same `data/` and emit the same schema ⇒ the evaluation is method-agnostic and fair

_Speaker notes:_ This is the engineering backbone that makes a fair comparison possible — every method plugs into the same harness.

---

## Slide 8 — Evaluation Pipeline

- Shared schema: `gt.json` (ground truth) vs `predictions.json` (per method), both in meters
- `eval/evaluate.py` matches predictions to GT and reports:
  - Detection: **Precision / Recall / F1** (and AP@IoU planned)
  - Pose: **radius RMSE**, **axis-angle error (deg)**, center error
  - **Runtime** per scan; **annotation/training cost** kept as a column so geometric vs learned compare fairly
- Recall-vs-occlusion% curve is the headline metric once the occlusion sweep exists

_Speaker notes:_ Highlight that I explicitly track annotation/training cost — otherwise learned methods look "free."

---

## Slide 9 — What Works Today: Four Geometric Detectors

- **3dtk_hough** — baseline, 3DTK randomized 2-step Hough
- **ransac_cylinder** — shared proposer + `normals2step` fit (axis from normal covariance + 2D circle-RANSAC)
- **ls_cylinder** — shared proposer + nonlinear least-squares cylinder fit
- **efficient_ransac** — self-contained Schnabel RANSAC via CGAL, **no proposer** (removes the shared-proposer confound)
- All four LiDAR-only geometric, no training data; reuse off-the-shelf code, not from scratch

_Speaker notes:_ Four working methods covers the geometric family; methods 2 and 3 share a proposer (clean fit comparison), method 4 deliberately removes that confound.

---

## Slide 10 — Preliminary Results (Synthetic + First Real)

- **Synthetic set** (10 scenes incl. noise sweep):

  | method | P / R / F1 | radius RMSE | axis err | speed |
  |---|---|---|---|---|
  | ls_cylinder | 1.00/1.00/1.00 | 0.06–0.54 cm | ≤0.01° | ~9 s |
  | ransac_cylinder | 1.00/1.00/1.00 | 0.06–0.40 cm | ≤0.50° | ~0.7 s |
  | efficient_ransac | 1.00/0.80/0.89 | 0.12–1.46 cm | ~2.3° | ~0.05 s |
  | 3dtk_hough | 1.00/0.71/0.83 | up to 0.52 cm | ≤0.49° | — |

- **First real (Xtion `xtion02_crop`):** all 4 detect the barrel (recall 1.0); radius error ~6–8× synthetic (real noise); 3dtk_hough emits a phantom 2nd cylinder (P=0.50) and is non-deterministic
- Caveat: synthetic set is essentially **one occlusion level** so far — does not yet test occlusion

_Speaker notes:_ Be honest: perfect-looking synthetic recall is one easy pose; the real and occlusion stress-tests are the point and aren't done. **[FILL]** with final numbers/plots if updated.

---

## Slide 11 — Data & Annotation Work

- Synthetic generator: analytic cylinder arcs (`--arc-deg`), radial normals, noise variants (n0.1/0.2/0.3)
- Real Xtion captures via ROS 2 driver; cropping pipeline (voxel → multi-plane RANSAC → DBSCAN → barrel priors)
- Real occluded survey scene (`station1_pit_barrels`, 200 L drums) cropped from the 1.23 M-pt scan
- **GT annotation pipeline (works):** CloudCompare-in-Docker crop one drum → `fit_from_segments.py` fits a radius-locked cylinder → `gt.json` (human marks region, code fits)
- First real survey GT done: tilted barrel, R 0.286 m, fit RMS 22 mm

_Speaker notes:_ "Human marks the region, code fits the cylinder" — this is how I get ground truth on arbitrarily-oriented real drums.

---

## Slide 12 — Challenges Encountered

- **No-GUI host:** Wayland laptop can't run 3DTK `show`/CloudCompare natively → Docker + VNC/EGL headless rendering
- **Units:** 3DTK is cm, Open3D/PCD are m, standardized schema is m — a recurring source of bugs
- **Occlusion / viewpoint:** single overhead survey viewpoint = mostly caps & short walls → proposer-free RANSAC over-segments; cluster proposers assume one pre-isolated barrel
- **Annotation cost:** no mouse/right-click on the laptop → cross-section box workflow; coaxial touching drums can't be split cleanly
- **Environment:** system Python 3.14 has no deps → project runs in a uv venv (3.12)

_Speaker notes:_ Frame the survey-scan over-segmentation as a *finding* (hard-occlusion case study), not just a bug — it motivates the simulated multi-position data.

---

## Slide 13 — Future Plan / Roadmap

- **Isaac Sim dataset** with full ground truth: per-barrel pose/axis/radius, 3D bboxes, semantic/instance masks, true occlusion %; sweep barrel count, spacing, burial depth, mutual occlusion
- **Occlusion sweep experiment:** recall + pose error vs true occlusion %, per method (the headline result)
- **Learned LiDAR methods:** PointNet++ / BarrelNet-style, optional BtcDet (occlusion-aware) — needs the sim training set
- **Camera+LiDAR fusion:** one camera-first frustum pipeline + a LiDAR-first/point-painting pipeline
- **Calibration-noise experiment:** perturb sim camera↔LiDAR extrinsics to find where fusion degrades
- Validate top 1–2 methods on a small real scan set (sim-to-real gap)

_Speaker notes:_ Isaac Sim is the unlock — it gives the free perfect ground truth that the learned methods and the occlusion sweep both need.

---

## Slide 14 — Timeline, Next Steps & Summary

- **Done:** comparison harness + schema; 4 geometric LiDAR methods; synthetic + first real scoring; real GT annotation pipeline; literature survey (18 methods)
- **Next (near-term):** run all 4 on the real survey drum segment untuned; occlusion sweep on synthetic data; **[FILL: dates]**
- **Then:** Isaac Sim data → learned methods → fusion → full cross-family comparison
- **Summary:** the contribution is a fair, method-agnostic comparison of barrel detectors under occlusion — four geometric methods benchmarked, simulation + learned + fusion to come

_Speaker notes:_ Close on the contribution: not one detector, but a grounded comparison. **[FILL]** a concrete month-by-month timeline before presenting.

---

### Author checklist before presenting (not a slide)
- **[FILL]** Replace any superseded scores with the latest from `eval/*.csv` / the methods-status memory.
- **[FILL]** Add real figures: a cloud+fit render (synthetic), the real Xtion fit, the station1 drum pile, and a fit-vs-GT overlay. Reusable renders exist under `researchwrite/bilfinger_slides/assets/` and via `common/render_fit.py`.
- **[FILL]** Insert a concrete dated timeline on Slide 14.
- Guessed/assumed items: exact talk date, your/supervisor names, and whether the occlusion sweep has been run yet (memory says planned, not started) — verify before presenting.
