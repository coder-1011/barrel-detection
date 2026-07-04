# barrelnet — learned drum-pose regressor (method #5)

BarrelNet-style (Yan et al., OCEANS 2024) supervised fit: a pure-PyTorch PointNet
regresses the drum **axis** (sign-symmetric) and the **nearest point on the axis**
from a single-drum patch. Radius stays the 0.286 m prior. Trained on synthetic
patches, evaluated against the 21 human-verified station1 drums. Runs on CPU
(laptop) or CUDA (A100 conda env `barrelnet`, cu121 wheels).

```
gen_synth_patches.py   # randomized patches: tilt/arc 60-300°/noise/burial/caps/
                       # clutter/scan-line spacing  -> data/synth_patches/ (gitignored)
train.py               # trains, checkpoints (last.pt/best.pt), RESUMES automatically,
                       # logs runs/<run>/train_log.csv; --finetune-real = 6/15 stage
infer.py               # shared inference: TTA ensemble + hybrid center refine
predict_station.py     # per-drum table on the 21 real drums (--tta/--hybrid-center/--split)
detect.py              # FULL-SCENE detector: proposer -> net -> refine -> predictions.json
run_detection.sh       # method contract wrapper around detect.py
run_offline.sh         # unattended synth-only training (stage 1)
run_finetune.sh        # unattended 6-real finetune (stage 2, label-efficiency exp)
real_split.json        # FIXED 6 finetune / 15 eval drum split — do not change
```

## Results on the 21 verified real drums (A100 synth-only ckpt, ep180)

| inference | gate hits (axis≤30°, dist≤10 cm) | med axis | med dist |
|---|---|---|---|
| single pass (legacy)             | 12/21 | 14.1° | 8.6 cm |
| + TTA-32 (subsample+rot ensemble)| 14/21 | 14.9° | 7.4 cm |
| + hybrid center (`--hybrid-center`) | **18/21** | 14.9° | **3.1 cm** |

The net's axis is its strength (19/21 within 30° with TTA); its position head is
the bottleneck. The **hybrid center** = radius-locked Gauss-Newton circle fit in
the plane ⊥ the predicted axis (falls back to the net's point-on-axis under 200
pts). Remaining misses: drum 1 (115 pts, sparse), drums 5/20 (axis > 30°,
merged/hard). Caveat: GT centers were themselves produced by radius-locked fits
(different axis source), so center agreement is partly methodological.

## Full-scene detection (`run_detection.sh`, 2026-07-04)

Sliding-window fixed-R RANSAC proposer (generalized from
`candidates/tools/find_drums.py`) → shell patch → net pose (TTA-32) → hybrid
center → re-score against the cloud (inliers/coverage/extent) → NMS.

On `station1_pit_barrels`: **recall 16/21 (0.76), mean axis 12.7°, ~96 s** — the
first non-zero full-pile score by any method (the 4 geometric methods were F1=0
even on the segmented single drum). 64 detections total ≈ the user's ~70-drum
pile estimate; precision is NOT measurable here (GT is ~30 % partial — unlabeled
detections are often real drums). Map: `figures/station_full_detect.png`.

## Training plan (fixed with the user 2026-07-02 — don't change silently)

1. **Stage 1 — synth only.** The 21 verified station1 drums are the held-out real
   test set, never trained on. (Done: A100 200-epoch run, converged.)
2. **Stage 2 — label-efficiency finetune** (`--finetune-real`): start from the
   stage-1 checkpoint, train on the 6 drums in `real_split.json` (heavy
   augmentation + synth mix against forgetting), evaluate ONLY on the 15
   held-out drums. best.pt is selected on the real gate-hit metric (synth
   val-loss is a bad synth→real proxy). NB: selection uses the same 15 drums it
   reports (no third split at n=21) — quote last.pt as the selection-free number.
3. Runs anywhere: trainer auto-picks CUDA and auto-resumes from `runs/<run>/last.pt`.

Launch stage 2 on the A100 (synth ckpt lives in `runs/run1` there):
```bash
PY=/media/students/bharath/miniforge3/envs/barrelnet/bin/python \
  nohup methods/barrelnet/run_finetune.sh > methods/barrelnet/runs/finetune.log 2>&1 &
tail -f methods/barrelnet/runs/finetune6/train_log.csv
```
On the laptop use `INIT=methods/barrelnet/runs/a100/best.pt` instead.

Baselines the finetune must beat on the eval-15 (synth-only ckpt): 9/15
single-pass, 10/15 TTA-32, **14/15 TTA-32 + hybrid center** (only sparse drum 1
missing — with hybrid inference the gate metric is nearly saturated, so judge
the finetune mainly on median axis error / dist and on drum 1). A 3-epoch CPU
smoke test already reached 12/15 with TTA alone.

## Finetune RESULTS (A100 60-epoch run `runs/finetune6`, 2026-07-05)

On the 15 held-out drums (best.pt ≡ last.pt): **median axis 13.1°→11.3°**, net
position clearly better (TTA dist median 7.3→6.1 cm; TTA gate 10→11/15), drum 1
closer (26→23 cm). Under TTA+hybrid the gate reads 13/15 vs 14/15 — borderline
drum 15 slipped 9.6→10.9 cm; medians are equal (2.3 vs 2.2 cm). **Where it
clearly pays: the full-pile detector — recall 18/21 (0.86) vs 16/21 synth-only**
(caveat: 6 of the 21 are its finetune drums). Figure:
`figures/station_full_detect_3d.png` (top-down + 3D, green = matched GT,
orange = candidate drums on the unannotated ~70 %).
