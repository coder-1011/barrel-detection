#!/usr/bin/env bash
# Run the RANSAC cylinder-fit detector on one scene and store results under
# methods/ransac_cylinder/results/<scene>/.
#
# Method contract (same as 3dtk_hough):
#   run_detection.sh <data-scene-dir> [opts] -> results/<scene>/predictions.json
#
# Stored per scene:
#   predictions.json   project-standard schema (meters; see common/eval_schema.py)
#   run.log            detector stdout
#   run_meta.json      provenance (fit mode, params, lib version, timestamp)
#
# Fit modes (see detect.py):
#   normals2step  axis from normal-covariance + 2D circle RANSAC  [default, robust]
#   pyransac      pyRANSAC-3D 3-point cylinder RANSAC (wobbles on partial arcs)
#
# Usage (from anywhere):
#   methods/ransac_cylinder/run_detection.sh data/synth/data_synth_half
#   methods/ransac_cylinder/run_detection.sh data/real/data3_crop --crop
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTERS="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [ $# -lt 1 ]; then
  echo "usage: $0 <data-scene-dir> [--crop] [--fit MODE] [--r-min M] [--r-max M] ..." >&2
  exit 2
fi
SCENE_DIR_ARG="$1"; shift
EXTRA_ARGS=("$@")   # forwarded verbatim to detect.py (--crop, --fit, --thresh, ...)

# Accept a path relative to cwd or to the repo root.
if [ -d "$SCENE_DIR_ARG" ]; then
  SCENE_DIR="$(cd "$SCENE_DIR_ARG" && pwd)"
elif [ -d "$MASTERS/$SCENE_DIR_ARG" ]; then
  SCENE_DIR="$(cd "$MASTERS/$SCENE_DIR_ARG" && pwd)"
else
  echo "scene dir not found: $SCENE_DIR_ARG" >&2; exit 1
fi
SCENE="$(basename "$SCENE_DIR")"

RESULTS="$MASTERS/methods/ransac_cylinder/results/$SCENE"
mkdir -p "$RESULTS"
LOG="$RESULTS/run.log"

python3 "$SCRIPT_DIR/detect.py" \
    --scene "$SCENE_DIR" \
    --out "$RESULTS/predictions.json" \
    "${EXTRA_ARGS[@]}" 2>&1 | tee "$LOG"

python3 - "$RESULTS/run_meta.json" "$SCENE" "$SCENE_DIR" "$LOG" "${EXTRA_ARGS[@]}" <<'PY'
import json, sys, time
try:
    import pyransac3d, importlib.metadata as md
    ver = md.version("pyransac3d")
except Exception:
    ver = None
out, scene, scene_dir, log, *extra = sys.argv[1:]
json.dump(dict(
    scene=scene, method="ransac_cylinder",
    timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
    scene_dir=scene_dir, run_log=log,
    detector="methods/ransac_cylinder/detect.py",
    extra_args=extra, pyransac3d_version=ver,
), open(out, "w"), indent=2)
print("wrote", out)
PY

echo
echo "done: $SCENE"
echo "  predictions : methods/ransac_cylinder/results/$SCENE/predictions.json"
echo "  log + meta  : run.log, run_meta.json"
