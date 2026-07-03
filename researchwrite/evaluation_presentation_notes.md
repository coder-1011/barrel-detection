# Evaluation Presentation — Reader Notes (v3)

Companion to `researchwrite/evaluation_presentation.pptx` (rebuilt 2026-07-03). One
section per slide, written in full sentences — the detail, caveats, and numbers that do
**not** fit on the (deliberately sparse, big-font) slides. This is the version to *read
to prepare*, not a teleprompter. Numbers pulled from the project memory, `eval/*.csv`,
and `methods/barrelnet/runs/*/train_log.csv` as of 2026-07-02. Title-slide presenter /
supervisor / date are left as `[FILL]`.

> Deck pairing: `python3 researchwrite/make_eval_figures.py` (intro/fitting/pipeline/
> synth-data/BarrelNet-epoch figures), `python3 eval/plot_noise_sweep.py` (big-font
> sweep chart), then `python3 researchwrite/build_eval_deck.py`. The F1 numbers on the
> synthetic-results slide are read live from `eval/<method>.csv` (`sweep_*` rows).

## What changed vs the 2026-07-01 draft (supervisor feedback applied)

- **Fonts**: body text is now ≥17 pt (mostly 18–22 pt); all regenerated figures use
  ≥13 pt text at render size so graph labels survive projection.
- **One point per bullet**, plain language; method jargon ("accumulator mass",
  "normals2step") removed from slides (kept here in the notes).
- **New general intro**: the bin-picking problem first, then "the objects are also
  covered". If the supervisor's two AI-generated images are saved as
  `presentation_assets/binpicking_ai_1.png` / `binpicking_ai_2.png`, the build script
  uses them on slide 1 automatically; until then a schematic (`binpicking_intro.png`)
  stands in.
- **"Fitting" explained from scratch** (line-fit example → cylinder parameters → why a
  thin arc is ambiguous) on its own slide with a dedicated figure.
- **Family pros/cons split** into separate +/− bullets, each family's idea given in one
  plain sentence.
- Key subtitle content promoted into highlighted **key-line strips**.
- **Evaluation bullets integrated into the pipeline graphic** itself.
- **Synthetic experiment split** into setup (with pictures of the data) + results
  (full-width plot). **Real data split** into two slides (clean lab / occluded drum).
- **Risks slide now pairs each risk with a mitigation**; the deck ends on a positive
  summary slide.
- **NEW: three BarrelNet slides** — the learned method + its synthetic training data,
  the training-progress epoch comparison (laptop CPU vs A100), and the detection
  visualisation on the real pile.

## What changed in v3 (2026-07-03, second feedback round)

- **Intro de-duplicated**: slide 1 said the bin-picking message three times (subtitle +
  figure titles + key line) — now title + images + one key line.
- **Flow fixed, general → specific**: "what fitting means" now comes BEFORE "our drums
  are covered" (slides 2/3 swapped); the "a small patch fits many cylinders" message
  now lands on the pile slide, where it belongs.
- **Data before methods**: a new "test data" slide (synthetic barrel / lab barrel /
  drum pile — `test_data_overview.png`) sits before the methods slide; the separate
  synthetic-experiment *setup* slide is merged into the results slide.
- **Methods slide slimmed**: the small architecture diagram and the "details on
  request" subtitle are gone; four bigger bullets remain.
- **Pipeline chart minimal**: the italic per-box footnotes were removed from
  `pipeline_flow.png`; the boxes are bigger. The key line (accuracy gate) stays.
- Later slides de-duplicated (BarrelNet caption vs bullet; the limits slide now
  references Experiment 2 instead of restating its noise finding).

---

## Title slide

The registered thesis title is **"Detection and Robotic Manipulation of Partially
Occluded Object(s)"** — kept verbatim. Open by saying the thesis is an **empirical
comparison of detection methods**, with manipulation as the eventual second half (not
yet started — be honest about that when slide 16 comes up).

---

## Slide 1 — The bin-picking problem

General audience intro, no project specifics yet. Bin picking: a robot must take
objects out of an unordered pile. To grasp anything it needs, per object, the **pose**
— where the object is and how it lies. Challenges even in the standard setting: objects
overlap and touch, the 3D sensor only ever sees the surfaces facing it, and poses are
arbitrary. The slide's key line: *before the robot can grasp anything, it must know
exactly where each object is and how it lies.*

Image note: the supervisor supplied two AI-generated illustrations in his feedback
mail. Save them as `presentation_assets/binpicking_ai_1.png` and `binpicking_ai_2.png`
and rebuild — the deck will pick them up automatically. Until then a hand-drawn
schematic (open bin vs sand-covered bin, sensor above) is used.

---

## Slide 2 — What "fitting" means

Comes BEFORE the project-specific pile (v3 flow fix: stay general first). Supervisor
asked not to assume the audience knows fitting. Three-panel figure
(`fitting_explained.png`):

1. **Line fit** — the simplest model: choose slope + offset so the line matches the
   measured points best (residual sticks drawn in grey). "Fitting = choosing model
   parameters that minimise the mismatch to the measurements."
2. **The cylinder model** — what has to be found per drum: **centre** (a point),
   **axis direction** (a 3D direction), **radius**. That pose triple is exactly what a
   grasp planner needs.
3. **Why occlusion breaks it** — a thin visible arc of a circle is consistent with many
   different circles (three shown through the same points).

Key line bridges to the next slide: with a full view fitting is easy — the difficulty
starts when most of the object is hidden.

---

## Slide 3 — Our case is harder: the drums are covered

Transition from the general task to this project: the objects are **200-litre steel
drums** (radius 0.286 m), tumbled into a pile and **partially buried in sand/debris**,
scanned by a survey LiDAR from a **single viewpoint** (`data/real/station1_pit_barrels`,
106,905 points). Each drum shows the sensor only a small patch of its surface — mostly
top caps, short wall strips, and scan-shadow gaps. Key line ties back to panel 3 of the
fitting slide: a small patch fits many different cylinders — that ambiguity is the core
difficulty of this thesis.

---

## Slide 4 — Existing solutions: three families

Distilled from the 18-method literature survey (`methods_survey.tex`). Each family gets
one plain-language idea sentence, one advantage bullet, one disadvantage bullet:

- **Geometry-based** — search the points directly for cylinder shapes (voting,
  random-sampling, least-squares). *+* works out of the box, no training data.
  *−* needs enough visible points; touching drums get merged. (In survey terms: Hough
  needs enough votes in its accumulator, RANSAC/LS are only as good as the point
  proposer — but the slide deliberately avoids that vocabulary.)
- **Learning-based** — a neural network learns what partial barrels look like from many
  examples (PointNet++, BtcDet, BarrelNet). *+* can recognise a barrel from a small
  fragment — built for occlusion. *−* needs many labelled training examples first;
  sim-to-real gap. Closest prior work: **BarrelNet** (Yan et al., OCEANS 2024,
  arXiv:2410.01061) — PointNet trained on synthetically occluded/buried cylinders,
  beats least-squares fitting; no public code, so we reproduce it ourselves (slide 11).
- **Camera + LiDAR** — combine colour images with 3D points (frustum, point painting).
  *+* one sensor covers for the other when blocked. *−* both must be precisely
  calibrated; miscalibration makes them fail together.

Key line = the plan: all three families are compared on the same data; geometry first,
since it needs no training data. Breadth-first, reuse existing code.

---

## Slide 5 — The data we test every method on  ← NEW (v3)

Introduced BEFORE the methods (user feedback): three panels in
`test_data_overview.png`, difficulty increasing left to right:

1. **Synthetic barrel** (`data/synth/sweep_*`) — generated by
   `common/synth_cylinder.py`, so the true cylinder is known *exactly*; best-case
   conditions and perfect ground truth.
2. **Real lab barrel** (`data/real/xtion02_crop`) — small barrel (r = 4.25 cm), Asus
   Xtion depth camera, fully visible; real sensor noise but no occlusion.
3. **Real drum pile** (`data/real/station1_pit_barrels`) — the survey-LiDAR pile from
   slide 3; tumbled, buried 200 L drums, 21 hand-verified ground-truth drums (~30% of
   the pile).

Key line: synthetic clouds tell us the best case; the real pile tells us the truth.
The three experiments (slides 8–10) walk exactly this ladder.

---

## Slide 6 — Four geometry-based methods implemented

One plain sentence per method (the slide's whole point is that a non-expert can follow):

1. **3DTK Hough (baseline)** — every point votes for the cylinders it could lie on; the
   strongest vote wins. (Technically: randomized 2-step Hough — Gaussian-sphere vote
   for the axis, then 3D Hough for centre+radius.)
2. **RANSAC fit** — try many random small point samples, keep the cylinder most points
   agree with. (Technically: shared clustering proposer + normals2step fit.)
3. **Least-squares fit** — start from a rough guess, adjust the cylinder until it
   matches the points best (nonlinear LS, `xingjiepan/cylinder_fitting`).
4. **Efficient RANSAC** — an optimised RANSAC that searches the whole scene for shapes
   in one pass (Schnabel 2007 via CGAL; needs no proposer).

The architecture diagram was removed in v3 (small + redundant with the pipeline
slide). If asked about internals: RANSAC and LS share one proposer (clean fit
comparison, but a shared confound); Efficient RANSAC removes that confound by finding
cylinders directly. Key line: all four are LiDAR-only, no training data, identical
input/output — directly comparable.

---

## Slide 7 — How we evaluate

The pipeline graphic is deliberately minimal in v3: six boxes — data → ground truth →
detection → predictions → scoring → metrics — bold header + one short line each, no
footnotes. The detail that used to sit under the boxes lives here instead: one shared
format, everything in metres; identical command `run_detection.sh <scene>`; the same
matching rule for every method; metrics are found/not-found plus radius & direction
error (precision/recall/F1 in the harness) and runtime per scene. Key line defines the
**accuracy gate** used throughout the talk: a prediction counts as correct if its
**direction is within 30°** and the true centre lies **within 10 cm** of the predicted
axis. Unit discipline if asked: 3DTK is internally cm, Open3D/.pcd are m, the shared
schema is m.

---

## Slide 8 — Experiment 1: the synthetic noise sweep (setup + results, merged in v3)

Setup (now in the subtitle; the data set itself was already shown on slide 5): **33
computer-generated clouds** of one barrel (r = 4.25 cm) showing a **120° visible
strip** (like a half-hidden drum); the **only variable is Gaussian measurement noise**
— 11 levels from 0.0 to 0.6 cm, each with 3 random repeats (`--seed` added to
`common/synth_cylinder.py` for genuine repeats). All four methods run with identical
default flags; scored with the standard harness. Caveat to state out loud: this sweep
varies noise at ONE occlusion level — it is a fit-robustness test, **not** an occlusion
test (that needs Isaac Sim, slide 15). If someone wants to see noisy vs clean clouds,
`presentation_assets/synth_data_example.png` (σ = 0.0/0.3/0.6) is a ready backup slide.

Full-width big-font chart (radius error / axis error / F1 vs noise). Bullets embed the
live-aggregated F1 from `eval/*.csv`. Per-level numbers (mean over 3 seeds, from
`presentation_assets/synth_noise_sweep_table.csv`):

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

Trends to verbalise: **RANSAC + LS hold F1 = 1.0 across the whole sweep**; LS has the
best axis (≤0.09°) but RANSAC the best radius at high noise. **Efficient RANSAC
degrades fastest** (axis ~3.8° by σ=0.2, drops detections mid-range — it needs its
tolerance ≈ noise scale, and sometimes explains the arc as planes). **3DTK Hough is
erratic, not monotonic** — misses clean scenes (F1=0 at σ=0.0/0.05/0.20) and only locks
on at high noise; a little noise helps populate its voting bins. Frame as brittleness
of the baseline's own binning, not noise-robustness. Runtime (full wall-clock per
scene): Hough ~1.4 s, Efficient RANSAC ~2.3 s, RANSAC ~3.3 s, **LS ~16.6 s** (5–10×
slower — it buys precision with runtime).

---

## Slide 9 — Experiment 2 (real): clean lab barrel

`xtion02_crop`: a small lab barrel (r = 4.25 cm, ~180° visible) seen by an Asus Xtion
depth camera; render `bilfinger_slides/assets/real_3d_det.png`. Table (P/R details):
all four methods find the barrel (recall 1.0); radius error 0.09–0.94 cm, direction
error 0.1–1.9°. The wrinkle: **3DTK Hough also emits a phantom second cylinder**
(r ≈ 2.1 cm) → precision 0.50, and it is non-deterministic (unseeded randomized Hough).
Second bullet is the important one: real errors ran **~6–8× the synthetic** figures —
real sensor noise is structured (range-dependent, shadow gaps), not the clean i.i.d.
noise we simulate.

---

## Slide 10 — Experiment 3 (real): occluded survey drum

`station1_pit_barrels_seg00`: one tilted, half-buried 200 L drum segmented out of the
pile. **All four methods fail the accuracy gate** (F1 = 0 untuned) — and the failure
modes are the finding:

- **Least-squares is by far the closest**: radius 31.4 cm, direction 17.1° (inside the
  30° gate), but the true centre sits **11.1 cm** from the predicted axis — a
  **1.1 cm near-miss** on the 10 cm gate. The fit genuinely lies along the drum.
- **RANSAC fit**: good radius (25.9 cm) but direction 69° off (its axis estimate from
  surface normals breaks on the partial tilted arc).
- **Efficient RANSAC**: fits a huge ~1.0–1.5 m radius to the gently curved patch →
  rejected. **3DTK Hough**: no detection (its config is tuned to the 4.25 cm lab
  barrel; its normal orientation assumption is invalid for this de-offset survey
  cloud).

GT caveat to disclose if asked: this drum's reference axis came from a coarse crop that
caught two coaxial drums as one blob, so even the good LS fit is judged against a
slightly suspect reference. Key line: occlusion is exactly where the classical methods
break — the motivation for the learned method on the next slide.

---

## Slide 11 — BarrelNet: the first learning-based method  ← NEW

Method #5, `methods/barrelnet/` — a from-scratch reproduction of the BarrelNet idea
(Yan et al. 2024 has no public code). What it is: a **PointNet-style neural network**
that takes the ~hundreds of LiDAR points of ONE drum patch and directly outputs the
drum's **pose**: axis direction (sign-symmetric loss) + a point on the axis. Radius is
not regressed — the drum type is known (r = 0.286 m).

Training data (figure `synth_patches_sample.png`): **12,000 randomly generated
synthetic patches** from `gen_synth_patches.py` — axis uniformly random, visible arc
60–300°, survey-LiDAR-like scan-grid spacing, dropout, optional cap disc, burial-plane
clipping, sand clutter, 2–15 mm noise. The generator's randomisation is the
augmentation.

**The key methodological point (key line, green):** training uses **no real data at
all**. The **21 hand-verified real drums** (semi-automatic annotation + CloudCompare
review, 2026-07-02) are the **held-out test set**, evaluated every epoch and never
trained on — so every real-drum number in this talk is an honest measure of
synthetic-to-real transfer, a core thesis result in itself.

---

## Slide 12 — BarrelNet: training progress (epoch comparison)  ← NEW

Figure `barrelnet_epochs.png`: score on the 21 held-out real drums vs training epoch,
for **two runs of the same network** — the laptop CPU run (stopped at epoch 148 by its
8 h budget) and the A100 GPU run (full 200-epoch schedule). Three panels: drums within
the accuracy gate (of 21), median centre error (cm, with the 10 cm gate line), median
direction error (deg, with the 30° gate line).

What to narrate:

- **Finishing the schedule nearly doubled the score: 7/21 → 12/21.** The laptop run
  plateaued at 7/21 (epoch 148); the A100 run reaches 12/21 (best.pt epoch 180 ≈
  last.pt epoch 199).
- **Direction is learned early** (median ~15–16° well inside the 30° gate from
  mid-training; 16/21 drums within the direction gate). **Centre position is the
  bottleneck** — median centre error crosses the 10 cm gate only around epoch ~110
  as the learning-rate steps down, ending at ~8 cm.
- **Training has converged**: the curve is flat after ~epoch 130 (LR decayed /16 by
  epoch 200) — further gains need better data or fine-tuning, not more epochs.
- Checkpoint-selection lesson (if asked): the checkpoint with the lowest *synthetic*
  validation loss is NOT the best on real data — select on the real metric.
- Persistent failures across both runs: the sparsest drum (115 points) and two drums
  with merged/contaminated segments — data-quality, not capacity, issues.

---

## Slide 13 — BarrelNet on the real drum pile  ← NEW

Figure `station_detection.png` (from `make_figures.py`): the whole survey pile, the 21
annotated drums coloured by instance, BarrelNet's predicted cylinders overlaid on a few
drums — green = within the accuracy gate, red = miss (checkpoint: A100 epoch 180).

- **12 of 21 real drums located within the gate** (direction ≤ 30° AND centre ≤ 10 cm);
  median direction error ~15°, median centre error ~8 cm; 16/21 within the direction
  gate alone.
- Context: the four geometric methods scored **0** on their occluded test drum
  (slide 10) — synthetic-only training already beats them on exactly the hard case.
- **Honest limitation (grey bullet):** BarrelNet is a **pose estimator, not a
  detector** — it is *given* a segmented drum patch and estimates that drum's pose. It
  cannot find the ~70% of the pile that is unannotated. Full-pile detection needs a
  proposer/segmentation front-end (the planned `run_detection.sh` wrapper) plus more
  annotation — orthogonal to how well the pose network works.

---

## Slide 14 — What limits the evaluation today

One limitation per bullet, plain language:

1. The synthetic scene generator still cannot imitate a truly buried, cluttered pile
   (single idealised arc + noise; no mutual occlusion/burial/multipath).
2. Real sensor noise is structured, not the clean i.i.d. noise we simulate (evidence:
   the 6–8× error jump on slide 9).
3. Only 21 real drums are labelled (~30% of the pile) — too few for strong statistics.
4. Some labels are imperfect (two coaxial drums annotated as one blob — the slide-10
   caveat).

Key line stays constructive: the evaluation machinery works; what is missing is more
and better ground-truth data → segue to Isaac Sim.

---

## Slide 15 — Next step: simulation closes the data gap

NVIDIA Isaac Sim as a ground-truthed data engine: every simulated drum comes with exact
pose and exact burial/occlusion fraction — labels for free (Replicator; RTX LiDAR
matched to the real sensor; co-registered camera; scripted sweeps of count, spacing,
burial, mutual occlusion). That enables (bullets deliberately do not repeat the roadmap
graphic): the **occlusion sweep** (detection quality vs how much of the drum is hidden
— the headline thesis experiment), more learned methods trained at scale, and
camera+LiDAR fusion incl. a calibration-noise-injection experiment.

---

## Slide 16 — Open risks, and how we deal with them

Feedback: don't end on problems without answers → each risk is paired with a
mitigation in a two-column table:

1. **Accuracy collapses under occlusion** (field-wide: PointRCNN loses ~11.5 pts car AP
   across KITTI's occlusion tiers, 88.88 → 78.63 → 77.38 [Shi'19, arXiv:1812.04244];
   LiDAR-only mAP 64.7 → 34.1 (−47.3%) under controlled heavy occlusion [Kumar'25,
   arXiv:2511.04347]) → **we measure it systematically per method instead of assuming;
   that comparison IS the thesis.**
2. **One sensor may never be reliable enough** → **fusion is planned**; [Kumar'25]:
   fusion beats LiDAR-only even clean (68.5 vs 64.7 mAP) and loses only 4.1 pts to
   camera occlusion vs the 47.3-pt LiDAR-only collapse. Honest caveat if asked: fusion
   still loses 26.8 pts when the LiDAR leg itself is occluded — it mitigates, not
   eliminates, the failure mode ([Wang'25], Sensors 25(9):2794, same qualitative
   conclusion).
3. **Sim-trained models may not transfer** → **BarrelNet already measures exactly this
   transfer** (12/21 on real drums, slide 13); next experiment: fine-tune on ~6 real
   drums, evaluate on the remaining 15 (the label-efficiency experiment).
4. **Manipulation not started** → detection outputs exactly the pose a grasp planner
   needs; manipulation follows the method comparison.

> **Verification note (kept from v1):** an MDPI Sensors 25(13):3865 / PMC12251959
> "+4.1%/+29.2%" fusion figure was previously proposed and **rejected** — that paper is
> V2V LiDAR-only cooperative fusion, and its percentages are vs a prior SOTA baseline,
> not LiDAR-only. Only [Shi'19], [Kumar'25], [Wang'25] (all verifiable in
> `methods_survey.tex` §4/§6) are cited on the slide.

---

## Slide 17 — Summary

End positive: (1) one fair evaluation pipeline — every method, same data, same score;
(2) four geometry-based methods work well on visible barrels and all fail on a truly
occluded one — measured, not assumed; (3) **BarrelNet, trained only on synthetic
drums, already finds 12 of 21 real occluded drums**; (4) next: simulated data for the
occlusion sweep, real-drum fine-tuning, sensor fusion. Key line: learned + simulated is
the promising path for occluded drums — and we can now measure exactly how promising.
