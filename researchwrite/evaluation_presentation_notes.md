# Evaluation Presentation — Reader Notes

Companion to `researchwrite/evaluation_presentation.pptx`. One section per slide,
written in full sentences — the detail, caveats, and numbers that do **not** fit on
the (deliberately sparse) slides. This is the version to *read to prepare*, not a
teleprompter. Numbers are pulled from the project memory and `eval/*.csv` as of
2026-07-01. Title-slide presenter / supervisor / date are left as `[FILL]`.

> Deck pairing: build the figures with `researchwrite/make_eval_figures.py`, run the
> synthetic noise-sweep job, then `python3 researchwrite/build_eval_deck.py`. Slide 5's
> table is read live from `eval/<method>.csv` (the `sweep_*` rows), so it always matches
> the measured numbers.

---

## Title slide

The registered thesis title is **"Detection and Robotic Manipulation of Partially
Occluded Object(s)"** — kept verbatim. The subtitle reframes it as the concrete research
problem: *detecting partially occluded cylindrical objects for robotic manipulation, a
multi-method comparison in 3D point clouds.* Open by stating plainly that the thesis is an
**empirical comparison of detection methods**, with manipulation as the eventual second
half (not yet started — be honest about that when it comes up on slide 9). Note for the
talk: the current work is **detection only**; "robotic manipulation" is in the title
because it is the registered scope, but everything shown today is the perception front-end
that manipulation will depend on.

---

## Slide 1 — Problem statement

The picture is the real survey-LiDAR scene (`data/real/station1_pit_barrels`, 106,905
points): a tumbled pile of **standard 200 L oil drums** (radius 0.286 m, diameter 0.57 m),
**partially buried, mutually occluding, lying in arbitrary orientations** on a pit floor at
~z −15 m, captured from a **single terrestrial viewpoint**. Use it to make "partially
occluded" concrete: from one viewpoint you see mostly top caps, short wall sections, and
radial scan-shadow gaps — each barrel exposes only a thin arc, not the whole surface.

The task is to recover, per barrel, the full pose — **centre, axis direction, and radius**
— which is what a manipulation stage would need to grasp a drum. The hard part is that a
thin arc (~120–200° of the circumference) leaves both radius and axis under-constrained, so
naive cylinder fitting is ambiguous. Stress the framing: this is an **empirical, systematic
comparison** to find which method works best under occlusion and to characterise each
method's operating regime — *not* a defence of a predetermined hypothesis. Every "method A
beats method B" statement in this talk is a measurement, not an assumption.

---

## Slide 2 — Existing solutions (three families)

This is distilled from the 9-page literature survey (`methods_survey.tex`: an 18-method
landscape table plus a 1–5 occlusion-suitability rubric). Three families, each with its
occlusion-specific trade-off:

- **LiDAR-only geometric** (Euclidean clustering + fit, region-growing, randomized Hough,
  RANSAC / efficient-RANSAC, robust least-squares). *Advantage under occlusion:* no
  training data, cheap, and a partial arc still produces Hough votes or a fittable inlier
  set — this is the zero-training reference point. *Disadvantage:* Hough needs enough
  accumulator mass, so heavy occlusion thins the votes and clutter creates spurious peaks;
  RANSAC/LS tolerate partial arcs but are only as good as the **proposer** that hands them
  points, and clustering proposers split or merge adjacent/touching drums. Survey rates
  most of these **2–3 / 5** for occlusion.

- **LiDAR-only learned** (PointNet++ segment-then-fit, VoteNet, voxel/pillar detectors,
  BtcDet). *Advantage:* they learn partial-shape cues and can fire from partial evidence —
  centre-voting and occlusion-aware occupancy prediction are *built* for occlusion, and the
  one published barrel-specific study, **BarrelNet** (Yan et al., OCEANS 2024), trains on
  synthetically occluded/buried cylinders and **beats a classical least-squares fit**.
  *Disadvantage:* they need labelled occluded examples — which this project does **not have
  yet** — plus a sim-to-real gap and real annotation/training cost. Survey rates these
  **4 / 5**, but conditional on data.

- **Camera + LiDAR fusion** (camera-first frustum → fit; LiDAR-first proposals → image
  verification / point painting). *Advantage:* one modality can compensate when the other
  is occluded, and fusion gives the best recall on the safety-critical classes.
  *Disadvantage:* the modalities **fail together** when calibration drifts, and (slide 9)
  current fusion stays disproportionately LiDAR-reliant when the LiDAR leg is the one
  occluded.

**Why these were chosen for the thesis** (from the `barrel-detection-project` memory and the
survey's "Purpose and scope" + "Suggested shortlist"): breadth-first — get several methods
running on barrels before deepening any one; **no-training-data methods first** because they
need no labels and form the reference point; **reuse existing code, don't reimplement**; and
keep the **proposer/fit separation** so a single stage can be swapped and methods compared
fairly. BarrelNet is the nearest learned prior but has **no public code**, so the learned
family is deferred until a training set exists.

---

## Slide 3 — Methods chosen to evaluate

Four implemented geometric detectors, all LiDAR-only, all reading the same scene and
emitting the same schema:

1. **3dtk_hough** — the baseline: 3DTK's `detectCylinder`, a randomized 2-step Hough (2D
   Hough on the Gaussian sphere of normals for axis direction, then 3D Hough for centre +
   radius).
2. **ransac_cylinder** — shared clustering proposer + a `normals2step` fit (axis from the
   smallest eigenvector of the normal covariance, then a 2D circle-RANSAC in the
   cross-section). pyRANSAC-3D is kept only as a documented failure baseline.
3. **ls_cylinder** — the *same* shared proposer + a nonlinear least-squares cylinder fit
   (`xingjiepan/cylinder_fitting`).
4. **efficient_ransac** — Schnabel 2007 multi-primitive RANSAC via CGAL; **self-contained,
   no proposer** (it finds cylinders directly).

The architecture diagram shows the **proposer → reusable metric fit** split. The point of
the design: RANSAC and LS share one proposer and differ only in the fit, which makes a
**clean fit-quality comparison** — but that shared proposer is a confound. Efficient RANSAC
deliberately removes the confound by detecting cylinders without any proposer, which is
exactly why it was added.

---

## Slide 4 — Evaluation method

How evaluation is actually carried out today. Three pieces:

- **Shared schema** — ground truth lives in `gt.json` and each method's output in
  `predictions.json`, **both in metres** (documented in `data/GT_TEMPLATE.json`). Mind the
  unit discipline: 3DTK is internally cm, Open3D / `.pcd` are m, and the standardized schema
  is m — a recurring source of bugs.
- **Method contract** — every detector exposes `run_detection.sh <scene-dir>` and writes
  `results/<scene>/predictions.json`. Because the interface is identical, the evaluation is
  method-agnostic: adding a method means adding a folder, not touching the evaluator.
- **`eval/evaluate.py`** — matches each prediction to the nearest ground-truth barrel under
  a gate (axis ≤ 30°, GT-centre within 10 cm of the predicted axis) and reports
  **precision / recall / F1**, **radius RMSE**, **axis-angle error (deg)**, and **runtime**.
  Annotation/training cost is kept as a column in the wider plan so geometric and learned
  methods will eventually compare fairly.

The pipeline figure traces it end to end: data sources (Xtion capture / survey LiDAR /
`synth_cylinder.py`) → scene + `gt.json` → proposer/crop (geometric methods only) →
`run_detection.sh` → `predictions.json` → `evaluate.py` → metrics.

---

## Slide 5 — Evaluating the methods (synthetic noise sweep)  ← NEW WORK

This slide reports a **new** experiment, not a transcription. The existing synthetic set was
only 10 scenes at effectively one occlusion level, so it could not show a *trend*. For this
talk we generated an expanded sweep that **isolates sensor noise as the single variable**:

- **33 synthetic clouds** (`data/synth/sweep_n<noise>_s<seed>/`), arc fixed at the existing
  120° "half" convention (occlusion_frac 0.667), Gaussian noise swept across
  **0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60 cm**, each at **3 seeds**
  for genuine repeats / variance. A `--seed` argument was added to
  `common/synth_cylinder.py` (default 0, backward-compatible — it still reproduces the
  original 10 scenes exactly) because the generator previously hardcoded `rng(0)` and
  produced identical clouds at a given noise level.
- All four methods were run on every scene with the same flags as the existing
  `synth_half*` set (clean single barrel → no crop), then scored with
  `eval/evaluate.py --csv eval/<method>.csv`.

**Result figure:** `presentation_assets/synth_noise_sweep.png` — radius error, axis error,
and F1/recall vs noise, one line per method. The slide's table is read **live from
`eval/*.csv`** (the `sweep_*` rows), so it always reflects the measured values.

**Measured results (mean over 3 seeds; full per-level table in
`presentation_assets/synth_noise_sweep_table.csv`):**

| metric | method | σ=0.00 | σ=0.20 | σ=0.40 | σ=0.60 |
|---|---|---|---|---|---|
| **F1** | RANSAC fit | 1.00 | 1.00 | 1.00 | 1.00 |
| | Least-squares | 1.00 | 1.00 | 1.00 | 1.00 |
| | Efficient RANSAC | 1.00 | 0.22 | 0.67 | 0.67 |
| | 3DTK Hough | 0.00 | 0.00 | 0.67 | 1.00 |
| **radius RMSE (cm)** | RANSAC fit | 0.00 | 0.25 | 0.41 | 0.31 |
| | Least-squares | 0.00 | 0.29 | 0.78 | 1.07 |
| | Efficient RANSAC | 0.00 | 0.65 | 0.69 | 2.30 |
| | 3DTK Hough | – | – | 0.72 | 1.19 |
| **axis err (deg)** | RANSAC fit | 0.00 | 0.40 | 1.01 | 1.52 |
| | Least-squares | 0.00 | 0.03 | 0.06 | 0.09 |
| | Efficient RANSAC | 0.01 | 3.79 | 2.67 | 5.03 |
| | 3DTK Hough | – | – | 0.10 | 0.10 |

(– = no true positives at that level → radius/axis undefined.) The slide's aggregate table
is auto-read from `eval/*.csv`; the aggregate hides the *shape* of these curves, so use this
per-level table when narrating.

**Headline trends to verbalise:**

- **Most robust: RANSAC fit and Least-squares** — both hold **F1 = 1.0 across the entire
  sweep** (they detect the barrel at every noise level and seed). LS has the lowest axis
  error everywhere (≤0.09°); RANSAC actually keeps the lowest radius RMSE at high noise
  (~0.3 cm at σ=0.6, edging out LS, whose radius error grows roughly linearly to ~1.1 cm).
- **Degrades fastest: Efficient RANSAC (Schnabel/CGAL)** — axis error blows up to ~3.8° by
  σ=0.2 and ~5° by σ=0.6, radius RMSE reaches ~2.3 cm, and it **drops detections mid-range**
  (detection rate falls to 0.33 at σ=0.2). This matches the known behaviour that it needs
  `epsilon ≈ noise scale` and at intermediate noise sometimes explains the arc as *planes*
  rather than a cylinder.
- **3DTK Hough is erratic, not monotonic** — counter-intuitively it *misses* the clean and
  low-noise scenes (F1 = 0 at σ=0.0, 0.05, 0.20) and only locks on reliably at higher noise
  (F1 = 1.0 at σ=0.6). This is a quirk of its default Gaussian-sphere / Hough binning on a
  clean 120° arc — a little noise actually helps it populate the accumulator. When it does
  fire, its axis error is tiny (~0.1°). Frame this as a *finding about the baseline's
  brittleness to its own binning*, not as noise-robustness.

**Runtime (single lightweight wall-clock pass around `run_detection.sh`, 3 scenes/method):**
3DTK Hough ≈ **1.4 s**, Efficient RANSAC ≈ **2.3 s**, RANSAC fit ≈ **3.3 s**, Least-squares
≈ **16.6 s** (slowest by ~5–10×). So LS buys its low axis error and perfect recall at a large
runtime cost. (These full wall-clock figures supersede the older algorithm-core numbers
~0.7 s / ~0.05 s in the scoreboard, which timed only the fit, not the whole call.)

**Caveat to state out loud:** this sweep varies *noise at one occlusion level*. It is a
controlled fit-robustness test, **not** an occlusion test — the occlusion sweep is future
work (slide 8), and the synthetic noise model is i.i.d. Gaussian, which is not how real
sensors behave (slide 7).

---

## Slide 6 — Methods on real data

Two real scenes, deliberately reusing existing renders (no regeneration):

- **`xtion02_crop`** — a clean, single Asus Xtion barrel (r = 4.25 cm, ~180° visible). **All
  four methods detect it** (recall 1.0). Radius error ranges 0.09–0.94 cm and axis error
  0.10–1.85° across methods — i.e. radius to ~1 cm and axis to ~2°. The one wrinkle:
  **3dtk_hough emits a phantom second cylinder** (r ≈ 2.1 cm, 572 pts) → precision drops to
  0.50, and it is **non-deterministic** (unseeded randomized Hough — the committed run had 1
  detection, a re-run had 2); the other three are seeded and reproducible. Note the
  sim-to-real gap: real radius error is **~6–8× the synthetic** figure, attributable to real
  Xtion noise.

- **`station1_pit_barrels_seg00`** — the first **occluded survey-LiDAR drum** (a single
  tilted 200 L drum segmented from the pile, r = 0.286 m). The renders are
  `real_fits_ransac_ls.png` (per-method cross-sections vs the true circle) and
  `real_fits_on_cloud.png` (GT / RANSAC / LS cylinders on the actual cloud, two angles).
  **All four score F1 = 0 out of the box** under the standard gate — and *the failure modes
  are the finding*:
  - **ls_cylinder is by far the closest** — radius 31.4 cm, axis error 17.1° (inside the
    30° gate), but the GT centre sits **11.1 cm** from the predicted axis versus the 10 cm
    gate, so it misses by **1.1 cm**. The fit genuinely lies along the drum. This near-miss
    is the slide's real takeaway.
  - **ransac_cylinder** got a good radius (25.9 cm) but the normals2step axis from the
    partial tilted arc is **69°** off → false positive.
  - **efficient_ransac** fits a huge ~1.0–1.5 m radius to the gently curved single-viewpoint
    patch across every tuning → rejected by the radius filter (0 detections).
  - **3dtk_hough** — 0 detections (its cfg radius band is tuned for the 4.25 cm lab barrel,
    and its Open3D normals are oriented toward the origin, invalid for this de-offset survey
    cloud → the axis vote fails).

  **GT caveat to disclose:** the `gt.json` axis came from a *coarse* crop that caught ~2
  **coaxial** drums as one blob (height 1.11 m), so the reference axis is itself a two-drum
  composite — part of why even the good single-drum LS fit lands just outside the centre
  gate. A clean quantitative win needs a multi-position registered scan and/or per-drum
  (non-coaxial) ground truth.

---

## Slide 7 — Problems with the pipeline (data & methodology)

Focus on **data / methodology limitations**, not engineering friction:

1. **The synthetic generator can't produce genuinely occluded scenes.**
   `common/synth_cylinder.py` makes a single idealized arc plus Gaussian noise — it cannot
   generate multiple mutually-occluding barrels, burial, clutter, or multipath/sensor
   artefacts the way the real survey scan shows them. So synthetic results don't transfer to
   occlusion claims.
2. **Synthetic data isn't representative of real data.** Real Xtion and survey-LiDAR noise is
   *structured* (multipath, range-dependent, occlusion-shadow gaps), not i.i.d. Gaussian. The
   evidence: real radius error ran **~6–8×** the synthetic error, and **all four methods
   scored F1 = 0** untuned on the first real occluded scan.
3. **Not enough data to train/validate learned methods.** No labelled occluded real scenes
   exist yet, and the synthetic set is essentially one pose/occlusion level — nowhere near
   enough for a PointNet++/BarrelNet-style model, which is why the learned family is blocked.
4. **Can't yet accurately measure the geometric methods either.** Only **one** real occluded
   ground truth exists (`station1_pit_barrels_seg00`), and even that GT is suspect (the coarse
   crop caught two coaxial drums as one blob). Current P/R/F1 rests on a thin, partly
   unreliable evaluation set — not a statistically meaningful sample.
5. **Net effect:** today's pipeline can demonstrate the harness works, but it can't yet
   support either "method A beats method B under occlusion" or "this is ready to train a
   learned detector." Both need the Isaac Sim data plan (slide 8).

---

## Slide 8 — Future pipeline

The unlock is **NVIDIA Isaac Sim** as a ground-truthed data engine: per-barrel pose / axis /
radius, 3D boxes and instance/semantic masks for free (Replicator), an RTX LiDAR matched to
the real sensor with a co-registered camera, and scripted scenes sweeping barrel count,
spacing, burial depth, and mutual occlusion — including a computed **true occlusion %** per
barrel (visible/total surface points) for a grounded x-axis. That enables:

- The **occlusion sweep** — recall + pose error vs true occlusion %, per method — which is
  the thesis's **headline result**.
- **Learned methods** (PointNet++ / BarrelNet-style, optionally BtcDet) once the labelled
  training set exists.
- **Camera + LiDAR fusion** — one camera-first frustum pipeline and one LiDAR-first / point-
  painting pipeline.
- A **calibration-noise injection** experiment — perturb the sim-perfect camera↔LiDAR
  extrinsics to find where any fusion advantage degrades (a key real-world failure mode).

The roadmap figure stages this. Frame Isaac Sim as the thing that gives the *free, perfect
ground truth* that both the occlusion sweep and the learned methods depend on.

---

## Slide 9 — General problems & open risks

Lead with two **literature-backed** points (both verifiable in `methods_survey.tex` §4),
then the project-specific risks. Keep it honest rather than padded.

1. **Accuracy degrades sharply with occlusion severity** — a known pattern across 3D
   detection, not unique to this project. On KITTI, whose Easy/Moderate/Hard splits are
   *defined* by occlusion/truncation, **PointRCNN** drops from **88.88 → 78.63 → 77.38%**
   car AP₃D@0.7 across the three tiers — an ~11.5-point gap attributable to visibility alone
   (**[Shi'19]**, *PointRCNN*, CVPR 2019, arXiv:1812.04244). A 2025 controlled-occlusion
   study on nuScenes injects occlusion directly and shows **LiDAR-only mAP collapse from
   64.7% to 34.1% (−47.3%)** under heavy sensor occlusion (**[Kumar'25]**, arXiv:2511.04347).

2. **LiDAR-only alone isn't robust enough for mission-critical use** — which is why the
   roadmap includes fusion, not just geometric LiDAR. In the same study **[Kumar'25]**, fused
   **BEVFusion beats LiDAR-only even on clean data (68.5% vs 64.7% mAP)** and is far more
   robust when one sensor degrades: occluding the **camera** leg costs fusion only **4.1
   points** (68.5 → 65.7), versus the **47.3-point** LiDAR-only collapse above. The honest
   caveat: fusion still loses **26.8 points** (68.5 → 50.1) when the **LiDAR** leg itself is
   occluded — current fusion *mitigates* but does **not** *eliminate* the single-sensor
   occlusion failure mode. A broader fusion survey reaches the same qualitative conclusion
   (**[Wang'25]**, *Sensors* 25(9):2794).

   > **Verification note:** the brief also cited an MDPI *Sensors* 25(13):3865 / PMC12251959
   > figure (fusion +4.1% vehicles, +29.2% pedestrians). That reference is **not present in
   > this repo's bibliography** and could not be verified here, so it is **deliberately not
   > printed on the slide**. The `[Shi'19]`, `[Kumar'25]`, and `[Wang'25]` numbers above are
   > all verifiable in `methods_survey.tex` §4 / §6 with the cited arXiv IDs and venue. If
   > you want the MDPI per-class figure on the slide, verify its title/venue/DOI first.

3. **Project-specific risks:** the **sim-to-real gap** (sim LiDAR is cleaner than real survey
   LiDAR); the **manipulation half** of the thesis title is **not yet started** (current work
   is detection-only); **annotation/training cost** is a fairness concern for the
   geometric-vs-learned comparison (learned methods look "free" only if you ignore it); and
   general **scope / timeline** risk. It is fine for this slide to be short — the two cited
   points should carry most of its weight.
