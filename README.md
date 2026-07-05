# barrel-detection

Master's-thesis workspace for **barrel/cylinder detection in 3D point clouds**: an
empirical comparison of detection methods (LiDAR-only geometric today; learned and
camera+LiDAR fusion methods planned) with a shared, method-agnostic evaluation
pipeline. Current focus: how well each method handles partial views and occlusion,
from single Asus Xtion Pro depth frames up to a terrestrial survey-LiDAR scan of a
partially buried 200 L drum pile.

## Layout

```
masters/
├── common/            # method-agnostic tooling
│   ├── capture_one_frame.py   # ROS 2 → scan000.{pcd,3d,pose}
│   ├── synth_cylinder.py      # synthetic barrel scenes (+ exact gt.json, --seed, --arc-deg)
│   ├── eval_schema.py         # shared GT/prediction schema + matching + metrics
│   ├── view_cloud.py          # Open3D viewer (pred=red, gt=green overlays)
│   ├── pcd_to_ply.py          # export for CloudCompare annotation
│   ├── fit_from_segments.py   # segment → radius-locked cylinder fit → gt.json
│   ├── annotate_barrels.py    # GUI cap-click GT for vertical drums (needs a display)
│   ├── detections_to_ply.py   # predictions → colored cylinder-mesh PLY (CloudCompare)
│   └── render_fit.py          # headless fit-inspection PNGs → <scene>/renders/
├── data/
│   ├── real/<scene>/          # raw clouds: scan000.{pcd,3d,pose} + optional gt.json
│   ├── synth/<scene>/         # synthetic scenes incl. sweep_n<σ>_s<seed> noise sweep
│   └── GT_TEMPLATE.json       # documents the gt.json format
├── methods/<name>/    # one detection method per folder (contract below)
│   ├── 3dtk_hough/            # baseline: 3DTK detectCylinder (randomized Hough)
│   ├── ransac_cylinder/       # shared proposer + normals2step RANSAC fit
│   ├── ls_cylinder/           # shared proposer + nonlinear least-squares fit
│   ├── efficient_ransac/      # Schnabel 2007 via CGAL (self-contained, C++)
│   └── barrelnet/             # learned: PointNet pose regressor + sliding-window proposer
├── eval/              # evaluate.py + per-method result CSVs + plot_noise_sweep.py
├── researchwrite/     # thesis-writing material: survey, decks, notes, figures
└── docker-3dtk-show/  # Docker recipe for 3DTK `show` viewer + CloudCompare annotation
```

Vendored, gitignored, expected as siblings inside the working tree: `3DTK/` (built
toolkit, binaries in `3DTK/bin/`) and `openni2_camera/` (ROS 2 Xtion driver — see its
`CAMERA_USAGE.md`).

## The method contract

Every method is a folder `methods/<name>/` with:

```bash
methods/<name>/run_detection.sh <data-scene-dir> [method-specific options]
```

which writes `methods/<name>/results/<scene>/predictions.json` in the project-standard
schema (meters), plus `run.log` / `run_meta.json`. Derived artifacts (normals,
`cylinder.2d`, …) also stay under `results/<scene>/` — `data/` holds raw clouds only.

## Quick start

```bash
# generate a synthetic partial-view barrel scene (exact gt.json included)
python3 common/synth_cylinder.py --out data/synth/synth_half --arc-deg 120 --write-pcd

# run any method on any scene
methods/3dtk_hough/run_detection.sh       data/synth/synth_half
methods/ransac_cylinder/run_detection.sh  data/synth/synth_half
methods/ls_cylinder/run_detection.sh      data/synth/synth_half
methods/efficient_ransac/build.sh         # once (CGAL, g++)
methods/efficient_ransac/run_detection.sh data/synth/synth_half
methods/barrelnet/run_detection.sh        data/real/station1_pit_barrels  # learned; see its README

# score a method across all scenes that have gt.json (add --csv eval/<method>.csv
# to refresh its scoreboard file)
python3 eval/evaluate.py --method ransac_cylinder

# visualize a fit vs ground truth
python3 common/view_cloud.py --pcd data/synth/synth_half/scan000.pcd \
    --pred methods/ransac_cylinder/results/synth_half/predictions.json \
    --gt   data/synth/synth_half/gt.json
```

Python deps live in the uv venv `.venv/` (Open3D, numpy, sklearn, matplotlib,
pyransac3d, cylinder-fitting) — run pipeline python via `.venv/bin/python` or put
`.venv/bin` on PATH. The system python has none of them.

## Scenes

- `data/synth/synth_*` — controlled synthetic barrels (r = 4.25 cm, 120° arc variants,
  noise levels); `data/synth/sweep_n<0.00–0.60>_s<0–2>` is the 33-scene noise sweep
  (11 σ levels × 3 seeds) plotted by `eval/plot_noise_sweep.py`.
- `data/real/xtion01–03` (+ `_crop` variants) — single Xtion depth frames of a small
  8.5 cm-diameter lab barrel (renamed 2026-07-02 from `data`, `data2`, `data2_crop`, …).
- `data/real/station1_pit_barrels` — survey-LiDAR sub-scene of a tumbled, partially
  buried 200 L drum pile (r = 0.286 m); `gt.json` holds **21 human-verified drums**
  (semi-auto RANSAC proposals reviewed in CloudCompare — **partial GT, ~30 % of the
  pile: FP/precision are not meaningful on this scene**). Per-point instance labels +
  per-drum patches in `candidates/`. `_seg00` is a single-drum mini-scene cut from it.
  The 111 MB raw parent scan (`station1_deployment1_scan8/`) is local-only.

## Results snapshot (2026-07-05)

- **Synthetic noise sweep** (33 scenes, σ 0–0.6 cm): `ransac_cylinder` and
  `ls_cylinder` hold F1 = 1.0 across the whole sweep; `efficient_ransac` is fastest
  but degrades with noise; `3dtk_hough` is erratic (unseeded randomized Hough).
- **Real occluded pile** (`station1_pit_barrels`, 21-drum partial GT): the geometric
  methods score F1 = 0 untuned even on the single-drum mini-scene; **`barrelnet`
  reaches recall 18/21 (0.86)** with the 6-real-drum finetuned checkpoint
  (16/21 synth-only), matched-axis error ≈ 13°.
- Per-scene numbers: `eval/<method>.csv`; noise-sweep chart via `eval/plot_noise_sweep.py`.

## Units

- Open3D / `.pcd` / `gt.json` / `predictions.json`: **meters**
- 3DTK / `.3d` / `cylinder.2d`: **centimeters** (conversions handled inside the scripts)

## Notes

- 3DTK `detectCylinder` must run with cwd = the `3DTK/` source root (its cfg path is
  cwd-relative); `run_detection.sh` handles this — don't call the binary by hand.
- Do **not** use 3DTK `calc_normals` on small-radius barrels (~39 % flipped normals);
  the pipeline uses Open3D sensor-oriented normals instead.
- `cylinder.2d` may contain phantom duplicates — post-filter on axis extent
  (≥ 10 cm) and lateral-point count before treating a detection as real.
- The cluster proposer (`methods/3dtk_hough/crop_barrel.py`) is tuned for an
  8.5 cm-diameter target; pass `--target-width/--width-tol` for other sizes.
