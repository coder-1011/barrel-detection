#!/bin/bash
# Unattended finetune stage (label-efficiency experiment): start from the
# synth-trained checkpoint, finetune on the 6 real drums of real_split.json,
# evaluate every epoch on the 15 HELD-OUT drums. Safe to re-run: synth-shard
# generation is skipped if present, training resumes from $RUN/last.pt.
#
# Laptop : nohup methods/barrelnet/run_finetune.sh > methods/barrelnet/runs/finetune.log 2>&1 &
#          (override INIT=methods/barrelnet/runs/a100/best.pt)
# A100   : PY=/media/students/bharath/miniforge3/envs/barrelnet/bin/python \
#          nohup methods/barrelnet/run_finetune.sh > methods/barrelnet/runs/finetune.log 2>&1 &
#          (default INIT=runs/run1/best.pt = the server's synth-only run)
set -e
cd "$(dirname "$0")/../.."
PY=${PY:-.venv/bin/python}
OUT=data/synth_patches/train
RUN=${RUN:-methods/barrelnet/runs/finetune6}
INIT=${INIT:-methods/barrelnet/runs/run1/best.pt}
mkdir -p "$RUN"

for seed in 0 1 2 3; do
  if [ ! -f "$OUT/patches_s$seed.npz" ]; then
    echo "=== generating shard seed=$seed (3000 patches) ==="
    $PY methods/barrelnet/gen_synth_patches.py --out "$OUT" --n 3000 --seed $seed
  fi
done

echo "=== finetuning from $INIT (resumes if interrupted; max 6 h) ==="
$PY methods/barrelnet/train.py --data "$OUT" --run "$RUN" \
    --finetune-real --init "$INIT" --epochs 60 --max-hours 6

echo "=== scoring best.pt on the 15 held-out drums (TTA-32) ==="
$PY methods/barrelnet/predict_station.py --ckpt "$RUN/best.pt" --tta 32 \
    --split methods/barrelnet/real_split.json --subset eval
