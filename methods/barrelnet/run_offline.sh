#!/bin/bash
# Unattended offline pipeline: generate synthetic patches (if missing) -> train.
# Safe to re-run: generation is skipped if the shards exist, training resumes
# from methods/barrelnet/runs/run1/last.pt automatically.
#   nohup methods/barrelnet/run_offline.sh > methods/barrelnet/runs/offline.log 2>&1 &
set -e
cd "$(dirname "$0")/../.."
PY=.venv/bin/python
OUT=data/synth_patches/train
RUN=methods/barrelnet/runs/run1
mkdir -p "$RUN"

for seed in 0 1 2 3; do
  if [ ! -f "$OUT/patches_s$seed.npz" ]; then
    echo "=== generating shard seed=$seed (3000 patches) ==="
    $PY methods/barrelnet/gen_synth_patches.py --out "$OUT" --n 3000 --seed $seed
  fi
done

echo "=== training (resumes if interrupted; max 8 h) ==="
$PY methods/barrelnet/train.py --data "$OUT" --run "$RUN" --max-hours 8
