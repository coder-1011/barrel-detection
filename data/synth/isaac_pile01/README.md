# isaac_pile01 — synthetic tumbled 200 L drum pile (Isaac Sim 5.1.0)

A PhysX drop-and-settle synthetic scene that mimics the character of the real
`data/real/station1_pit_barrels/` pit: 25 × 200 L drums dropped into a pit and
settled into a **tumbled, mutually-occluding heap at arbitrary orientations**,
with **exact per-barrel ground truth** (Isaac's whole value here — full GT even
for occluded/buried drums).

Generated 2026-08-09 on a Vast.ai RTX 4090 running Isaac Sim 5.1.0 (headless
windowed on Xvfb :1). Deterministic: `SEED=7`.

## Files
- `gt.json` — **the payload**. Per-barrel cylinder GT in the project schema
  (`common/eval_schema.py`), meters. 25 barrels: `radius_m` 0.286 (matches real
  station1), `height_m` 0.900, unit `axis`, `center` (point on axis = drum
  centroid), `occlusion_frac` null (geometric GT; fill from a sensor pass later).
  - **Frame: `isaac_world` (x, y, z-up), meters.** NOT camera_optical — this is a
    world-frame geometric scene. A future sensor/point-cloud pass (Phase 2) must
    emit its cloud in this same frame (or transform both consistently) before the
    methods/evaluator compare predictions to this gt.json.
- `pile_persp.png` — perspective viewport render: the dense occluding heap.
- `pile_top.png` — top-down overview: central heap + strewn drums.
- `pile_gui_xgrab.png` — full Isaac GUI X-root grab (proof the live scene graph
  loaded: PhysicsScene, Ground, PhysMat, 4 invisible pit Walls, 25 Barrels).
- `pile.usd` — the scene stage. **NOT standalone-portable**: it references the
  barrel asset by absolute path `/root/barrel/barrel.usd` on the render box
  (which itself references the OBJ + texture). Kept as a reproducibility record,
  not for loading on the laptop. Regenerate with `barrel_pile.py` instead.
- `barrel_pile.py` — the generator (standalone Isaac script). Reproduces the
  scene + GT + screenshots. Knobs via env: `N_BARRELS` (25), `SEED` (7),
  `FOOTPRINT` (1.4), `SETTLE_FRAMES` (520).

## Scene character (from gt.json)
- Orientation variety: tilt-from-vertical spans 0.5°–89.3° (mean ~69°) — some
  drums upright, some leaning, most tumbled onto their sides; full 360° yaw spread.
- Vertical stacking: barrel-center Z spans 0.29 m (on the ground) to 2.49 m
  (stacked several high) → genuine 3D occlusion, not a single flat layer.
- A central dense heap of ~10–12 drums plus ~10 drums strewn around it (some
  squeezed out of the pit while settling) — realistic for a dumped-drum pit.

## Method
Convex-hull colliders on each drum (from `rollreifenfass200l.obj` → USD via
`omni.kit.asset_converter`), rigid bodies + damping, a friction/zero-restitution
physics material, dropped from a layered 2×2 lattice into 4 invisible static pit
walls (interior ~1.8 m), settled ~9.5 s of sim time, then each settled world
transform → cylinder GT (local long axis = +Z, length 0.900; radius locked to
0.286 to match the real drums).

## Not yet done (Phase 2, gated on user approval)
No point cloud yet. To let `methods/*/run_detection.sh` run against this perfect
gt.json, simulate an RTX-Lidar/depth sensor from one viewpoint and export an
occluded `scan000.pcd` (meters, same frame) into this dir.
