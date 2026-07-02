# barrelnet — learned drum-pose regressor (method #5, WIP)

BarrelNet-style (Yan et al., OCEANS 2024) supervised fit: a pure-PyTorch PointNet
regresses the drum **axis** (sign-symmetric) and the **nearest point on the axis**
from a single-drum patch. Radius stays the 0.286 m prior. Trained on synthetic
patches, evaluated against the 21 human-verified station1 drums. CPU-only
(AMD laptop) and fully offline once `.venv` has torch.

```
gen_synth_patches.py   # randomized patches: tilt/arc 60-300°/noise/burial/caps/
                       # clutter/scan-line spacing  -> data/synth_patches/ (gitignored)
train.py               # trains, checkpoints (last.pt/best.pt), RESUMES automatically,
                       # logs runs/<run>/train_log.csv, evals the 21 real drums/epoch
run_offline.sh         # unattended: generate 4x3000 patches if missing -> train 8 h
```

Run unattended:
```bash
nohup methods/barrelnet/run_offline.sh > methods/barrelnet/runs/offline.log 2>&1 &
tail -f methods/barrelnet/runs/run1/train_log.csv   # progress
```

Real-drum eval columns: `real_axis_deg_med` (median axis error vs GT),
`real_dist_m_med` (median GT-center→predicted-axis distance),
`real_hits` = drums passing the project's standard gate (axis ≤30°, dist ≤10 cm) —
the same gate all four geometric methods scored **0/1** on for barrel_00.

## Training plan (fixed with the user 2026-07-02 — don't change silently)

1. **Train on synthetic patches only.** The generator's randomization + dataloader
   augmentation is the data variety; the **21 verified station1 drums are the
   held-out real test set** (evaluated every epoch) and must **never** enter
   training — they are the project's only measure of synth→real transfer.
2. Optional later stage: **finetune on a small real split** (e.g. 6 drums augmented,
   evaluate on the remaining 15) = the label-efficiency experiment
   (`--finetune-real`, not yet implemented).
3. Runs anywhere: trainer auto-picks CUDA (A100: venv + `pip install torch numpy`,
   then the same `run_offline.sh` line with `nohup … & disown` or tmux) and
   auto-resumes from `runs/<run>/last.pt` on rerun.

TODO to make it a full method: `run_detection.sh` contract wrapper (proposer →
patch → net → predictions.json) so `eval/evaluate.py` can score it.
