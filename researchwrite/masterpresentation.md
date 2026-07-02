# Prompt: build the methods-comparison presentation

You are working in `~/masters` (barrel/cylinder detection thesis repo). Read
`CLAUDE.md` and the memory index at
`/home/bharath/.claude/projects/-home-bharath-masters/memory/MEMORY.md` first —
they hold the full project plan, repo layout, and the live results scoreboard
(`methods-status-and-results.md`). This file is the brief for a presentation
the student will give and talk over live, so the deck itself must stay sparse;
all the explaining happens out loud.

## Deliverables (two files)

1. **Main deck** — a `.pptx` under `researchwrite/`, e.g.
   `researchwrite/evaluation_presentation.pptx`. **Minimal wording**: short
   headline + a few bullet fragments per slide, no full sentences/paragraphs.
   Every slide that refers to a method, a result, or a scene must show the
   actual picture or table, not just describe it in words — the student talks,
   the slide shows.
2. **Reader notes** — a companion Markdown file,
   `researchwrite/evaluation_presentation_notes.md`, one section per slide,
   written in full sentences: the detail, caveats, and numbers that don't fit
   on the slide. Mirror the existing pattern in
   `researchwrite/progress_presentation_draft.md` (speaker-notes style) but
   go deeper — this is the version the student reads to prepare, not a
   teleprompter script.

(If a from-scratch `.pptx` build turns out to be more natural as two slide
decks instead of deck+notes — e.g. a short "talking" deck and a longer
"appendix/backup" deck — that's an acceptable substitute. Pick whichever is
less awkward to build and say which you picked.)

Reuse the existing scripted-deck scaffold rather than building python-pptx
calls from zero: `researchwrite/bilfinger_slides/build_deck.py` (deck
construction: blank layout, title/body helpers, image placement) and
`make_figures.py` (matplotlib → PNG, headless `Agg` backend) show the
project's conventions for colours, fonts, and figure style. Match that look.

## Slide structure (9 content slides + title)

**Title slide:** "Detection and Robotic Manipulation of Partially Occluded
Object(s)" — this is the official/registered thesis title, keep it verbatim.
Add presenter/supervisor/date as placeholders if not supplied — ask the user
for these rather than guessing; don't invent a date or name.

**Slide 1 — Problem statement.** Use this as the subtitle/framing line under
the title (refine the phrasing if it reads better split across title+sub):
"Detecting Partially Occluded Cylindrical Objects for Robotic Manipulation: A
Multi-Method Comparison in 3D Point Clouds." One supporting image: the
occluded/buried real drum pile (`station1_pit_barrels` cloud render, or
`researchwrite/bilfinger_slides/assets/real_3d_raw.png`) to make "partially
occluded" concrete at a glance.

**Slide 2 — Existing solutions.** Pull from the literature survey
(`researchwrite/methods_survey.tex`, the 18-method landscape table + the
occlusion-suitability rubric). For each method family (LiDAR geometric /
LiDAR learned / camera+LiDAR fusion) — or for the handful of closest
individual methods if that reads better on one slide — give:
  - advantage(s) and disadvantage(s), **specifically with respect to occluded
    data** (e.g. Hough needs the whole accumulator vote, RANSAC tolerates
    partial arcs but needs a good proposer, learned methods need labelled
    occlusion examples they don't have, fusion can compensate occlusion in
    one modality with the other but fails together when calibration drifts).
  - **why these methods were chosen for this thesis** — pull the actual
    rationale from `barrel-detection-project` memory and the survey's
    "Purpose and scope" + "suggested shortlist" sections (breadth-first,
    no-training-data-required first, reuse existing code not reimplement,
    proposer/fit separation enables fair swapping, BarrelNet as nearest
    learned prior with no public code).
  Use the survey's existing colour-coded occlusion-suitability rating if it
  renders cleanly as a small table image; otherwise build a condensed
  pros/cons table directly in the slide.

**Slide 3 — Methods chosen to evaluate.** The 4 implemented geometric
detectors: `3dtk_hough` (baseline, randomized 2-step Hough), `ransac_cylinder`
(proposer + normals2step fit), `ls_cylinder` (proposer + nonlinear LS fit),
`efficient_ransac` (Schnabel RANSAC via CGAL, no proposer — removes the
shared-proposer confound). One line each + the architecture diagram
(`researchwrite/presentation_assets/architecture_diagram.png` or
`method_families.png`) showing the proposer/fit split.

**Slide 4 — Evaluation method.** How evaluation is currently carried out:
the shared schema (`gt.json` vs `predictions.json`, both in metres,
documented in `data/GT_TEMPLATE.json`), the method contract
(`run_detection.sh <scene> → results/<scene>/predictions.json`), and
`eval/evaluate.py`'s matching + metrics (precision/recall/F1, radius RMSE,
axis-angle error, runtime). Diagram: pipeline flow (capture/synth → crop →
run_detection.sh → evaluate.py) — describe in `barrel-pipeline-flow` memory;
draw a simple box diagram if no figure exists yet.

**Slide 5 — Evaluating the methods (synthetic).** This slide needs **new
work**, not just transcription — see "New evaluation task" below. End state:
a table and/or chart of all 4 methods' precision/recall/F1 and radius/axis
error **as a function of noise level**, built from an expanded synthetic
sweep (current set is only 10 scenes, effectively one occlusion level — not
enough to show a trend).

**Slide 6 — Methods on real data.** Do **not** regenerate these — reuse the
pictures that already exist:
  - `researchwrite/presentation_assets/real_fits_ransac_ls.png` (per-method
    cross-sections vs the true circle)
  - `researchwrite/presentation_assets/real_fits_on_cloud.png` (GT/RANSAC/LS
    cylinders rendered on the actual `station1_pit_barrels` cloud, 2 angles)
  - `researchwrite/bilfinger_slides/assets/real_raw_vs_det.png`,
    `real_3d_det.png`, `methods_grid_real.png` (Xtion `xtion02_crop` results)
  Pair with the two real-data result tables already in memory
  (`methods-status-and-results.md`): `xtion02_crop` (all 4 detect, P/R/F1≈1.0,
  3dtk_hough phantom 2nd cylinder) and `station1_pit_barrels_seg00` (all 4
  score F1=0 out of the box — but `ls_cylinder` is a near-miss by 1.1 cm,
  which is the actual finding worth a slide).

**Slide 7 — Problems with the pipeline.** Focus on **data/methodology
limitations**, not engineering/tooling friction:
  - The synthetic generator (`common/synth_cylinder.py`) can only produce a
    single idealized arc + Gaussian noise — it **cannot generate genuinely
    occluded scenes** (multiple mutually-occluding barrels, burial, clutter,
    multipath/sensor artefacts) the way the real survey scan shows them, so
    synthetic results don't transfer to occlusion claims.
  - Synthetic data is **not representative of real-world data**: real Xtion
    and survey-LiDAR noise is structured (multipath, range-dependent,
    occlusion-shadow gaps), not i.i.d. Gaussian — the station1 results
    (real radius error ~6–8× the synthetic error; all 4 methods F1=0
    untuned on the first real occluded scan) are the evidence for this gap.
  - **Not enough data to train/validate AI (learned) methods**: no labelled
    occluded real scenes exist yet, and the synthetic set is essentially one
    pose/occlusion level — nowhere near enough for a PointNet++/BarrelNet-
    style model, which is why the learned-method family is still blocked.
  - **Cannot yet accurately measure the geometric methods either**: only one
    real occluded ground-truth exists so far (`station1_pit_barrels_seg00`),
    and even that GT is suspect (the coarse crop caught two coaxial drums as
    one blob — see `station1-pit-barrels-scan` memory) — so current P/R/F1
    numbers rest on a thin, partly-unreliable evaluation set, not a
    statistically meaningful sample.
  - Net effect: today's pipeline can demonstrate the harness works, but
    can't yet support either "method A beats method B under occlusion" or
    "this is ready to train a learned detector" — both need the Isaac Sim
    data plan (slide 8) to close the gap.
  Source the specific numbers from `methods-status-and-results` and
  `station1-pit-barrels-scan` memory; don't invent figures not already
  measured.

**Slide 8 — Future pipeline idea.** Isaac Sim dataset (full ground truth,
true occlusion %), the occlusion sweep experiment (recall + pose error vs
occlusion %, the thesis's headline result), learned methods once training
data exists, camera+LiDAR fusion, calibration-noise injection experiment.
Source: "Headline experiments" + "Data plan" sections of
`barrel-detection-project` memory.

**Slide 9 — General problems / open risks.** Lead with two literature-backed
points, then the project-specific risks:
  - **Accuracy degrades sharply with occlusion severity** — not unique to
    this project's methods, it's a known pattern across 3D detection
    generally. Cite: KITTI's occlusion-based Easy/Moderate/Hard split shows
    ~11.5-pt AP drop for a standard detector (PointRCNN, CVPR 2019,
    arXiv:1812.04244: 88.9%→78.6%→77.4%); a 2025 controlled occlusion study
    shows LiDAR-only mAP collapsing 64.7%→34.1% (~47% relative) under heavy
    sensor occlusion (Kumar et al., arXiv:2511.04347).
  - **LiDAR-only is not accurate/robust enough alone for mission-critical
    use** — motivates why the thesis roadmap includes fusion, not just
    geometric LiDAR methods. Cite: LiDAR+camera fusion improves accuracy up
    to +4.1% (vehicles) and +29.2% (pedestrians — the safety-critical class)
    over LiDAR-only (MDPI Sensors 25(13):3865, 2025, PMC12251959); the same
    2025 occlusion study shows fusion is far more robust to camera occlusion
    (-4.1% mAP) than LiDAR-only is to LiDAR occlusion (-47% mAP) — but also
    that fusion still degrades substantially (-27%) when the LiDAR leg
    itself is occluded (arXiv:2511.04347), so fusion mitigates but doesn't
    eliminate the LiDAR dependency. Verify these citations (title/venue/DOI)
    before printing them on a slide — pull the full references from this
    session's literature-search agent output rather than re-deriving them.
  - Then the project-specific risks: sim-to-real gap (sim LiDAR is cleaner
    than real survey LiDAR), the manipulation half of the thesis title not
    yet started (current work is detection-only), annotation/training cost
    as a fairness concern for geometric-vs-learned comparison, scope/timeline
    risk. Keep this slide honest rather than padded — it's fine if it's
    short, the two cited points should carry most of the slide's weight.

## New evaluation task (for slide 5) — actually do this work

The student wants real new numbers, not placeholders. **Spawn an agent** (use
the Agent tool) to run this as a self-contained pipeline, since it's a batch
of mechanical compute steps:

1. **Generate ≥30 new synthetic point clouds with varying noise**, extending
   `common/synth_cylinder.py`. Keep arc-deg fixed (use the existing "half"
   convention, `--arc-deg 120`, to isolate noise as the single variable from
   the existing set) and sweep `--noise-cm` over a finer/wider range than the
   current 0.1/0.2/0.3 (e.g. 0.0 to 0.6 cm in steps of ~0.02–0.05 cm gives
   30+ scenes). **Gotcha to handle first:** `synth_cylinder.py` currently
   seeds its noise RNG with a hardcoded `np.random.default_rng(0)`, so
   repeated calls at the same noise level produce identical point clouds —
   add a `--seed` CLI arg (default 0, for backwards compat) before relying on
   noise level alone, or use multiple seeds per noise level to get genuine
   repeats for variance, your call. Each generated scene also needs its own
   `gt.json` (the radius/axis/center/height are exactly the CLI args you
   passed — see `data/synth/synth_half/gt.json` for the template, and
   `data/GT_TEMPLATE.json` for the schema). Put the new scenes under
   `data/synth/` following the existing `synth_half_n<value>` naming, or
   a new `data/synth/noise_sweep/<scene>` subtree if that's cleaner — either
   is fine as long as `eval/evaluate.py`'s `find_gt_for_scene` can find each
   scene under `data/synth/<scene>/gt.json` (flat, one dir per scene; nested
   subdirs won't be found by the current glob, check `eval/evaluate.py`
   before choosing a layout).
2. **Run all 4 methods** on every new scene:
   `methods/{3dtk_hough,ransac_cylinder,ls_cylinder,efficient_ransac}/run_detection.sh data/synth/<scene>`
   (no `--crop` — synthetic scenes are already a clean single barrel, same as
   the existing `synth_half*` set).
3. **Evaluate** with `python3 eval/evaluate.py --method <name> --csv eval/<name>.csv`
   for each of the 4 methods (this will append/overwrite rows for all scenes
   under `methods/<name>/results/`, old and new together — fine, that's the
   existing convention).
4. **Produce the slide 5 artifact(s):** a results table (F1, radius RMSE,
   axis error per method, maybe binned by noise level) and ideally a
   matplotlib line chart of accuracy/error vs noise level, one line per
   method (`Agg` backend, save PNG to
   `researchwrite/presentation_assets/`). This is the figure slide 5 embeds.
5. Run inside the project's `.venv`
   (`export PATH="$PWD/.venv/bin:$PATH"` from `~/masters`, per CLAUDE.md —
   system Python has none of the deps).

Have the agent report back the final per-method numbers and confirm the chart
was written; fold that into both the slide table/chart and the reader-notes
detail for slide 5.

## Housekeeping

- After building both files, update the `researchwrite-materials` memory (and
  its `MEMORY.md` pointer) per CLAUDE.md rule 7 — this is a new addition to
  `researchwrite/` and needs to be indexed like the other decks.
- If the noise-sweep agent changes `common/synth_cylinder.py` (e.g. adding
  `--seed`), keep the change backward-compatible with existing call sites
  (default must reproduce today's scenes) — don't break the 10 already-scored
  synth scenes.
- Don't guess presenter name / supervisor / talk date — ask the user, leave
  `[FILL]` placeholders like the existing `progress_presentation_draft.md`
  does, or both.
