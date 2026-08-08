# Isaac Sim synthetic barrel-scene generation

Tooling to generate synthetic drum/barrel scenes in **NVIDIA Isaac Sim 5.1.0** on a
cloud GPU, with **exact per-barrel ground truth**, mirroring the real
`data/real/station1_pit_barrels/` scene (tumbled, occluded 200 L drums,
radius 0.286 m, arbitrary orientations). Output scenes land in `data/synth/`.

## Scripts
- `barrel_import.py` — imports a single barrel OBJ, converts OBJ→USD
  (`omni.kit.asset_converter`), references it under `/World/Barrel`, lights + camera.
- `barrel_pile.py` — the pile generator. Instances N barrels (default 25) as rigid
  bodies at random positions + **uniform-random orientations**, drops them inside
  static "pit" walls, steps PhysX until they settle into a tumbled, mutually-occluding
  heap, then writes `pile.usd` and a `gt.json` (project schema, meters, one cylinder
  per barrel: center, unit axis, radius 0.286, length). Deterministic via `SEED`.
- `flatten.py` — flattens `pile.usd` (inlines geometry) so the scene USD is
  self-contained and opens anywhere without the source barrel asset.
- `run_barrel.sh` / `run_pile.sh` — launch the two generators with Isaac's
  `python.sh` (set `DISPLAY=:1`, `OMNI_KIT_ALLOW_ROOT=1`).
- `onstart.sh` — Vast create-time hook that injects the SSH **public** key into the
  container's `authorized_keys` (Vast does not auto-provision it — see below).

Paths in these scripts (`/root/barrel`, `/isaac-sim`) reflect the Vast Isaac Sim
container they were run in.

## How to run (cloud GPU)
1. Rent an RTX 4090 (driver ≥ 580.65.06) and launch the
   `nvcr.io/nvidia/isaac-sim:5.1.0` image with `--ssh --direct`, passing `onstart.sh`
   as the create-time hook (mandatory — Vast does NOT auto-inject the account SSH key,
   so without it direct SSH is refused). NGC login: user `$oauthtoken`, password =
   your NGC key, server `nvcr.io`.
2. Over SSH: start `Xvfb :1`, then place the barrel model at `/root/barrel/`
   (`rollreifenfass200l.obj` + `.mtl` + `Rollreifenfass.png` from your `Barrels.zip`).
3. `./run_pile.sh` → produces `pile.usd`, `gt.json`, and screenshots. `flatten.py`
   makes the USD self-contained. Copy the outputs into `data/synth/<scene>/`.

## Notes
- The raw barrel model (`*.obj/.mtl/.png`, `*.blend`, `Barrels.zip`) is **not** in the
  repo (kept out via `.gitignore`) — supply your own copy. The generated `pile.usd`
  already has the geometry flattened in, so committed scenes are self-contained.
- Ground-truth format follows `common/eval_schema.py` / `data/GT_TEMPLATE.json`, so the
  detection methods in `methods/*/run_detection.sh` can score against it directly.
- Example output scene: `data/synth/isaac_pile01/` (25 barrels, SEED=7).
