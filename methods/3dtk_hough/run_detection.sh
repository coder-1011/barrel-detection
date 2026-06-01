#!/usr/bin/env bash
# Run the 3DTK randomized-Hough cylinder detector on one scene and store the
# results under methods/3dtk_hough/results/<scene>/.
#
# Input handling is automatic, based on the column count of scan000.3d:
#   6 cols (x y z nx ny nz) -> used as-is (already uos_normal)
#   3 cols (x y z)          -> normals estimated with compute_normals_o3d.py
#
# Stored per scene:
#   <work>/detectCylinder/cylinder.2d   raw detector output (cm)
#   run.log                              detector stdout
#   run_meta.json                        provenance (params, cfg hash, time)
#   predictions.json                     project-standard schema (see common/eval_schema.py)
#
# detectCylinder reads its cfg relative to the cwd, so we cd into 3DTK to run it.
#
# Usage (from anywhere):
#   methods/3dtk_hough/run_detection.sh data/real/data3_crop
#   methods/3dtk_hough/run_detection.sh data/synth/data_synth_half --radius-cm 0.4 --max-nn 15
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTERS="$(cd "$SCRIPT_DIR/../.." && pwd)"
TDTK="$MASTERS/3DTK"
DETECT="$TDTK/bin/detectCylinder"
CFG="$TDTK/include/detectCylinder/cylinderDetector.cfg"

RADIUS_CM=0.4
MAX_NN=15
MIN_EXTENT_CM=10

if [ $# -lt 1 ]; then
  echo "usage: $0 <data-scene-dir> [--radius-cm R] [--max-nn N] [--min-extent-cm E]" >&2
  exit 2
fi
SCENE_DIR_ARG="$1"; shift
while [ $# -gt 0 ]; do
  case "$1" in
    --radius-cm)     RADIUS_CM="$2";     shift 2 ;;
    --max-nn)        MAX_NN="$2";        shift 2 ;;
    --min-extent-cm) MIN_EXTENT_CM="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# Accept a path relative to cwd or to the repo root.
if [ -d "$SCENE_DIR_ARG" ]; then
  SCENE_DIR="$(cd "$SCENE_DIR_ARG" && pwd)"
elif [ -d "$MASTERS/$SCENE_DIR_ARG" ]; then
  SCENE_DIR="$(cd "$MASTERS/$SCENE_DIR_ARG" && pwd)"
else
  echo "scene dir not found: $SCENE_DIR_ARG" >&2; exit 1
fi
SCENE="$(basename "$SCENE_DIR")"
SCAN="$SCENE_DIR/scan000.3d"
[ -f "$SCAN" ]    || { echo "missing $SCAN" >&2; exit 1; }
[ -x "$DETECT" ] || { echo "detectCylinder not executable at $DETECT" >&2; exit 1; }

RESULTS="$MASTERS/methods/3dtk_hough/results/$SCENE"
mkdir -p "$RESULTS"

NCOLS=$(awk '!/^#/ && NF>0 {print NF; exit}' "$SCAN")
if [ "${NCOLS:-0}" -ge 6 ]; then
  # already has normals: copy the scan into the results dir and detect there
  WORK="$RESULTS"
  cp "$SCAN" "$WORK/scan000.3d"
  if [ -f "$SCENE_DIR/scan000.pose" ]; then
    cp "$SCENE_DIR/scan000.pose" "$WORK/scan000.pose"
  else
    printf '0 0 0\n0 0 0\n' > "$WORK/scan000.pose"
  fi
  NORMALS_SRC="input scan already uos_normal (${NCOLS} cols)"
else
  WORK="$RESULTS/normals_o3d"
  python3 "$SCRIPT_DIR/compute_normals_o3d.py" \
      --in "$SCENE_DIR" --out "$WORK" \
      --radius-cm "$RADIUS_CM" --max-nn "$MAX_NN"
  NORMALS_SRC="compute_normals_o3d.py --radius-cm $RADIUS_CM --max-nn $MAX_NN"
fi

LOG="$RESULTS/run.log"
echo ">> detectCylinder on $WORK"
( cd "$TDTK" && "$DETECT" -s 0 -e 0 -f uos_normal "$WORK/" ) | tee "$LOG"

CYL="$WORK/detectCylinder/cylinder.2d"
[ -f "$CYL" ] || { echo "detectCylinder produced no cylinder.2d" >&2; exit 1; }

python3 "$SCRIPT_DIR/cylinder2d_to_predictions.py" \
    --in "$CYL" --scene "$SCENE" --log "$LOG" \
    --out "$RESULTS/predictions.json" --min-extent-cm "$MIN_EXTENT_CM"

python3 - "$RESULTS/run_meta.json" "$SCENE" "$SCAN" "$WORK" "$NORMALS_SRC" "$CFG" "$MIN_EXTENT_CM" <<'PY'
import hashlib, json, os, sys, time
out, scene, scan, work, normals_src, cfg, min_ext = sys.argv[1:8]

def sha(p):
    try:
        with open(p, "rb") as f:
            return hashlib.sha1(f.read()).hexdigest()[:12]
    except OSError:
        return None

json.dump(dict(
    scene=scene, method="3dtk_hough",
    timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
    input_scan=scan, work_dir=work, normals=normals_src,
    detector="3DTK bin/detectCylinder -s 0 -e 0 -f uos_normal",
    cfg=cfg, cfg_sha1=sha(cfg),
    phantom_min_extent_cm=float(min_ext),
), open(out, "w"), indent=2)
print("wrote", out)
PY

echo
echo "done: $SCENE"
echo "  cylinder.2d : ${CYL#"$MASTERS"/}"
echo "  predictions : methods/3dtk_hough/results/$SCENE/predictions.json"
echo "  log + meta  : run.log, run_meta.json"
