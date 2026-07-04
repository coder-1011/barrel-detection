#!/usr/bin/env bash
# Run the BarrelNet detector on one scene and store results under
# methods/barrelnet/results/<scene>/.
#
# Method contract (same as the other methods):
#   run_detection.sh <data-scene-dir> [opts] -> results/<scene>/predictions.json
#
# Needs a trained checkpoint (default methods/barrelnet/runs/a100/best.pt —
# runs/ is gitignored, so pass --ckpt on machines without it).
#
# Usage (from anywhere):
#   methods/barrelnet/run_detection.sh data/real/station1_pit_barrels
#   methods/barrelnet/run_detection.sh <scene> --ckpt methods/barrelnet/runs/run1/best.pt
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTERS="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [ $# -lt 1 ]; then
  echo "usage: $0 <data-scene-dir> [--ckpt PT] [--radius M] [--tta N] ..." >&2
  exit 2
fi
SCENE_DIR_ARG="$1"; shift
EXTRA_ARGS=("$@")   # forwarded verbatim to detect.py

if [ -d "$SCENE_DIR_ARG" ]; then
  SCENE_DIR="$(cd "$SCENE_DIR_ARG" && pwd)"
elif [ -d "$MASTERS/$SCENE_DIR_ARG" ]; then
  SCENE_DIR="$(cd "$MASTERS/$SCENE_DIR_ARG" && pwd)"
else
  echo "scene dir not found: $SCENE_DIR_ARG" >&2; exit 1
fi
SCENE="$(basename "$SCENE_DIR")"

RESULTS="$MASTERS/methods/barrelnet/results/$SCENE"
mkdir -p "$RESULTS"
LOG="$RESULTS/run.log"

python3 "$SCRIPT_DIR/detect.py" \
    --scene "$SCENE_DIR" \
    --out "$RESULTS/predictions.json" \
    "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}" 2>&1 | tee "$LOG"

python3 - "$RESULTS/run_meta.json" "$SCENE" "$SCENE_DIR" "$LOG" "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}" <<'PY'
import json, sys, time
try:
    import torch
    ver = torch.__version__
except Exception:
    ver = None
out, scene, scene_dir, log, *extra = sys.argv[1:]
json.dump(dict(
    scene=scene, method="barrelnet",
    timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
    scene_dir=scene_dir, run_log=log,
    detector="methods/barrelnet/detect.py",
    extra_args=extra, torch_version=ver,
), open(out, "w"), indent=2)
print("wrote", out)
PY

echo
echo "done: $SCENE"
echo "  predictions : methods/barrelnet/results/$SCENE/predictions.json"
echo "  log + meta  : run.log, run_meta.json"
