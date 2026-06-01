#!/usr/bin/env bash
# Run the CGAL Efficient-RANSAC (Schnabel) cylinder detector on one scene and
# store results under methods/efficient_ransac/results/<scene>/.
#
# Self-contained detector: NO clustering proposer (unlike ransac/ls_cylinder) --
# it registers Plane+Cylinder factories and finds cylinders directly. Needs
# oriented normals (estimated by prep_input.py).
#
# Method contract (same as the other methods):
#   run_detection.sh <data-scene-dir> [opts] -> results/<scene>/predictions.json
#
# Stored per scene:
#   input_xyzn.txt     prepared input (x y z nx ny nz, meters)
#   cyl.txt            raw cgal_ransac CYL lines (meters)
#   predictions.json   project-standard schema (meters; see common/eval_schema.py)
#   run.log, run_meta.json
#
# Usage (from anywhere):
#   methods/efficient_ransac/run_detection.sh data/synth/data_synth_half
#   methods/efficient_ransac/run_detection.sh data/real/data3_crop --epsilon 0.004
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTERS="$(cd "$SCRIPT_DIR/../.." && pwd)"
BIN="$SCRIPT_DIR/bin/cgal_ransac"

# Efficient-RANSAC parameters (meters); tuned for the ~8.5 cm barrel.
EPSILON=0.006          # max point-to-cylinder distance (~noise scale; <0.006 misses noisy arcs)
CLUSTER_EPSILON=0.02   # connectivity radius
MIN_POINTS=1500        # min inliers to accept a shape
NORMAL_THRESHOLD=0.85  # min |cos(normal, shape)|
PROBABILITY=0.05       # search endurance (smaller = more thorough)
SEED=42
R_MIN=0.02
R_MAX=0.20

if [ $# -lt 1 ]; then
  echo "usage: $0 <data-scene-dir> [--epsilon E] [--cluster-epsilon E] [--min-points N]" \
       "[--normal-threshold T] [--probability P] [--seed S] [--r-min M] [--r-max M]" >&2
  exit 2
fi
SCENE_DIR_ARG="$1"; shift
while [ $# -gt 0 ]; do
  case "$1" in
    --epsilon)          EPSILON="$2";          shift 2 ;;
    --cluster-epsilon)  CLUSTER_EPSILON="$2";  shift 2 ;;
    --min-points)       MIN_POINTS="$2";       shift 2 ;;
    --normal-threshold) NORMAL_THRESHOLD="$2"; shift 2 ;;
    --probability)      PROBABILITY="$2";      shift 2 ;;
    --seed)             SEED="$2";             shift 2 ;;
    --r-min)            R_MIN="$2";            shift 2 ;;
    --r-max)            R_MAX="$2";            shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [ -d "$SCENE_DIR_ARG" ]; then
  SCENE_DIR="$(cd "$SCENE_DIR_ARG" && pwd)"
elif [ -d "$MASTERS/$SCENE_DIR_ARG" ]; then
  SCENE_DIR="$(cd "$MASTERS/$SCENE_DIR_ARG" && pwd)"
else
  echo "scene dir not found: $SCENE_DIR_ARG" >&2; exit 1
fi
SCENE="$(basename "$SCENE_DIR")"

[ -x "$BIN" ] || { echo "cgal_ransac not built; run methods/efficient_ransac/build.sh" >&2; exit 1; }

RESULTS="$MASTERS/methods/efficient_ransac/results/$SCENE"
mkdir -p "$RESULTS"
LOG="$RESULTS/run.log"
XYZN="$RESULTS/input_xyzn.txt"
CYL="$RESULTS/cyl.txt"

{
  python3 "$SCRIPT_DIR/prep_input.py" --scene "$SCENE_DIR" --out "$XYZN"
  echo ">> cgal_ransac eps=$EPSILON clusEps=$CLUSTER_EPSILON minPts=$MIN_POINTS" \
       "nThr=$NORMAL_THRESHOLD prob=$PROBABILITY seed=$SEED"
  START=$(date +%s.%N)
  "$BIN" "$XYZN" "$EPSILON" "$CLUSTER_EPSILON" "$MIN_POINTS" \
         "$NORMAL_THRESHOLD" "$PROBABILITY" "$SEED" > "$CYL"
  END=$(date +%s.%N)
  RUNTIME=$(echo "$END - $START" | bc)
  echo ">> detected $(grep -c '^CYL' "$CYL") cylinder(s) in ${RUNTIME}s"
  cat "$CYL"
} 2>&1 | tee "$LOG"

RUNTIME=$(awk '/detected/{for(i=1;i<=NF;i++) if($i ~ /s$/){gsub(/s/,"",$i); print $i}}' "$LOG" | tail -1)

python3 "$SCRIPT_DIR/cgal_to_predictions.py" \
    --in "$CYL" --scene "$SCENE" --out "$RESULTS/predictions.json" \
    --runtime-s "${RUNTIME:-0}" --r-min "$R_MIN" --r-max "$R_MAX"

python3 - "$RESULTS/run_meta.json" "$SCENE" "$SCENE_DIR" "$LOG" "$EPSILON" "$CLUSTER_EPSILON" \
         "$MIN_POINTS" "$NORMAL_THRESHOLD" "$PROBABILITY" "$SEED" <<'PY'
import json, sys, time
out, scene, sdir, log, eps, ceps, mpts, nthr, prob, seed = sys.argv[1:11]
json.dump(dict(
    scene=scene, method="efficient_ransac",
    timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
    scene_dir=sdir, run_log=log,
    detector="CGAL::Shape_detection::Efficient_RANSAC (Schnabel 2007), Plane+Cylinder",
    params=dict(epsilon=float(eps), cluster_epsilon=float(ceps),
                min_points=int(mpts), normal_threshold=float(nthr),
                probability=float(prob), seed=int(seed)),
), open(out, "w"), indent=2)
print("wrote", out)
PY

echo
echo "done: $SCENE"
echo "  predictions : methods/efficient_ransac/results/$SCENE/predictions.json"
echo "  log + meta  : run.log, run_meta.json"