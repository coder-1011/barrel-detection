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

TODO to make it a full method: `run_detection.sh` contract wrapper (proposer →
patch → net → predictions.json) so `eval/evaluate.py` can score it.
