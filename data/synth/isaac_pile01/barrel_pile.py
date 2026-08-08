"""
Build a synthetic tumbled pile of 200 L barrels in Isaac Sim 5.1.0 and emit
per-barrel ground truth in the masters/ project schema (meters, one entry each).

Standalone, windowed on DISPLAY=:1 so `import -window root` can grab the viewport.

Pipeline:
  1. Measure the referenced barrel USD's local bbox -> long (cylinder) axis + length.
  2. New stage (meters, Z-up), static ground box, PhysX scene (gravity -Z).
  3. N barrels as references, each RigidBody + convex-hull collider, dropped from
     staggered heights inside a small footprint with uniform-random 3D orientation.
  4. Play physics until they settle into a natural tumbled, occluding heap.
  5. Read each settled world transform -> cylinder GT (center, unit axis, radius, length).
  6. Save pile.usd, gt.json, and perspective + top-down screenshots.

Env knobs: N_BARRELS (default 25), SEED (default 7), FOOTPRINT (default 2.4),
SETTLE_FRAMES (default 450), OUT_DIR (default /root/barrel).
"""
import os
import sys
import json
import math
import random

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": False, "width": 1280, "height": 720})

import carb
import numpy as np
import omni.usd
import omni.kit.app
import omni.timeline
import omni.kit.commands
from pxr import Usd, UsdGeom, UsdPhysics, UsdLux, Gf, Sdf, PhysxSchema

# force PhysX to write settled transforms back to USD so we can read them
_s = carb.settings.get_settings()
_s.set_bool("/physics/updateToUsd", True)
_s.set_bool("/physics/updateVelocitiesToUsd", True)
_s.set_bool("/app/asyncRendering", False)

N = int(os.environ.get("N_BARRELS", "25"))
SEED = int(os.environ.get("SEED", "7"))
FOOTPRINT = float(os.environ.get("FOOTPRINT", "1.4"))
SETTLE_FRAMES = int(os.environ.get("SETTLE_FRAMES", "520"))
OUT_DIR = os.environ.get("OUT_DIR", "/root/barrel")
BARREL_USD = "/root/barrel/barrel.usd"
RADIUS_M = 0.286   # 200 L drum body radius, matches real station1 GT

rng = random.Random(SEED)
np.random.seed(SEED)


def pump(n):
    for _ in range(n):
        simulation_app.update()


def log(m):
    print(f"[PILE] {m}", flush=True)


def rand_quat():
    """Uniform random unit quaternion (Shoemake). Returns Gf.Quatf (w,(x,y,z))."""
    u1, u2, u3 = rng.random(), rng.random(), rng.random()
    s1, s2 = math.sqrt(1 - u1), math.sqrt(u1)
    w = s1 * math.sin(2 * math.pi * u2)
    x = s1 * math.cos(2 * math.pi * u2)
    y = s2 * math.sin(2 * math.pi * u3)
    z = s2 * math.cos(2 * math.pi * u3)
    return Gf.Quatf(w, Gf.Vec3f(x, y, z))


log("app booting")
pump(90)

ctx = omni.usd.get_context()
ctx.new_stage()
pump(20)
stage = ctx.get_stage()
UsdGeom.SetStageMetersPerUnit(stage, 1.0)
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
UsdGeom.Xform.Define(stage, "/World")

# ---- physics scene ----
scene = UsdPhysics.Scene.Define(stage, "/World/PhysicsScene")
scene.CreateGravityDirectionAttr(Gf.Vec3f(0, 0, -1))
scene.CreateGravityMagnitudeAttr(9.81)

# ---- static ground box: 20x20x1, top face at z=0 ----
ground = UsdGeom.Cube.Define(stage, "/World/Ground")
ground.CreateSizeAttr(1.0)
gx = UsdGeom.Xformable(ground)
gx.AddTranslateOp().Set(Gf.Vec3d(0, 0, -0.5))
gx.AddScaleOp().Set(Gf.Vec3f(20, 20, 1))
UsdPhysics.CollisionAPI.Apply(ground.GetPrim())
ground.CreateDisplayColorAttr([Gf.Vec3f(0.35, 0.35, 0.38)])

# ---- friction / low-restitution physics material (keeps the heap together) ----
from pxr import UsdShade
physmat = UsdShade.Material.Define(stage, "/World/PhysMat")
pm = UsdPhysics.MaterialAPI.Apply(physmat.GetPrim())
pm.CreateStaticFrictionAttr(0.9)
pm.CreateDynamicFrictionAttr(0.8)
pm.CreateRestitutionAttr(0.0)


def bind_physmat(prim):
    b = UsdShade.MaterialBindingAPI.Apply(prim)
    b.Bind(physmat, bindingStrength=UsdShade.Tokens.weakerThanDescendants,
           materialPurpose="physics")


bind_physmat(ground.GetPrim())

# ---- invisible pit walls (interior ~1.8 m) so barrels pile instead of scatter,
#      mirroring the real station1_pit_barrels pit ----
PIT = 0.95   # wall centerline; interior ~1.8 m
WALL_H = 2.5
_walls = [
    ("WallXn", Gf.Vec3d(-PIT, 0, WALL_H / 2), Gf.Vec3f(0.1, 2.2, WALL_H)),
    ("WallXp", Gf.Vec3d(PIT, 0, WALL_H / 2), Gf.Vec3f(0.1, 2.2, WALL_H)),
    ("WallYn", Gf.Vec3d(0, -PIT, WALL_H / 2), Gf.Vec3f(2.2, 0.1, WALL_H)),
    ("WallYp", Gf.Vec3d(0, PIT, WALL_H / 2), Gf.Vec3f(2.2, 0.1, WALL_H)),
]
for name, tr, sc in _walls:
    w = UsdGeom.Cube.Define(stage, f"/World/{name}")
    w.CreateSizeAttr(1.0)
    wx = UsdGeom.Xformable(w)
    wx.AddTranslateOp().Set(tr)
    wx.AddScaleOp().Set(sc)
    UsdPhysics.CollisionAPI.Apply(w.GetPrim())
    bind_physmat(w.GetPrim())
    UsdGeom.Imageable(w.GetPrim()).MakeInvisible()   # collides but not rendered

# ---- measure the barrel's local bbox (long axis + length) using a probe prim ----
probe = stage.DefinePrim("/World/_probe", "Xform")
probe.GetReferences().AddReference(BARREL_USD)
pump(5)
bbc = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])
lb = bbc.ComputeLocalBound(probe)
rng_box = lb.ComputeAlignedRange()
bmin, bmax = rng_box.GetMin(), rng_box.GetMax()
ext = [bmax[i] - bmin[i] for i in range(3)]
cen_local = [(bmax[i] + bmin[i]) * 0.5 for i in range(3)]
long_i = int(np.argmax(ext))
LOCAL_AXIS = Gf.Vec3d(0, 0, 0)
LOCAL_AXIS[long_i] = 1.0
LENGTH_M = float(ext[long_i])
short_r = 0.5 * float(sorted(ext)[1])   # measured hull radius (incl. rolling hoops)
log(f"barrel local extent={['%.3f'%e for e in ext]} long_axis_idx={long_i} "
    f"length={LENGTH_M:.3f} hull_r={short_r:.3f} center_local={['%.3f'%c for c in cen_local]}")
stage.RemovePrim("/World/_probe")
pump(3)

# ---- instance N barrels ----
UsdGeom.Xform.Define(stage, "/World/Barrels")
barrel_paths = []
for i in range(N):
    path = f"/World/Barrels/Barrel_{i:02d}"
    # clean parent Xform (we own its ops) + reference as a child so the
    # referenced prim's own xformOpOrder doesn't collide with ours
    parent = UsdGeom.Xform.Define(stage, path)
    geo = stage.DefinePrim(path + "/geo", "Xform")
    geo.GetReferences().AddReference(BARREL_USD)
    xf = UsdGeom.Xformable(parent.GetPrim())
    # layered 2x2 lattice inside the pit: avoids spawn overlap and keeps drop
    # heights modest (<~4.5 m) so barrels heap instead of exploding apart.
    layer = i // 4
    node = i % 4
    gx_off = (-1 if node in (0, 2) else 1) * (FOOTPRINT / 2)
    gy_off = (-1 if node in (0, 1) else 1) * (FOOTPRINT / 2)
    px = gx_off + rng.uniform(-0.12, 0.12)
    py = gy_off + rng.uniform(-0.12, 0.12)
    pz = 0.7 + 0.6 * layer + rng.uniform(0.0, 0.1)
    xf.AddTranslateOp().Set(Gf.Vec3d(px, py, pz))
    xf.AddOrientOp().Set(rand_quat())
    # rigid body + mass + damping on the clean parent (root of the body)
    UsdPhysics.RigidBodyAPI.Apply(parent.GetPrim())
    m = UsdPhysics.MassAPI.Apply(parent.GetPrim())
    m.CreateMassAttr(20.0)
    rbx = PhysxSchema.PhysxRigidBodyAPI.Apply(parent.GetPrim())
    rbx.CreateLinearDampingAttr(0.2)
    rbx.CreateAngularDampingAttr(0.2)
    # convex-hull collider + physics material on every mesh in the subtree
    for d in Usd.PrimRange(parent.GetPrim()):
        if d.IsA(UsdGeom.Mesh):
            UsdPhysics.CollisionAPI.Apply(d)
            mca = UsdPhysics.MeshCollisionAPI.Apply(d)
            mca.CreateApproximationAttr().Set("convexHull")
            bind_physmat(d)
    barrel_paths.append(path)
log(f"instanced {len(barrel_paths)} barrels; footprint {FOOTPRINT} m")

# ---- lights ----
dome = UsdLux.DomeLight.Define(stage, "/World/DomeLight")
dome.CreateIntensityAttr(1200.0)
key = UsdLux.DistantLight.Define(stage, "/World/KeyLight")
key.CreateIntensityAttr(2500.0)
UsdGeom.Xformable(key).AddRotateXYZOp().Set(Gf.Vec3f(-50.0, 0.0, 40.0))

# ---- cameras: perspective + top-down ----
persp = UsdGeom.Camera.Define(stage, "/World/PerspCam")
eye = Gf.Vec3d(2.9, -2.9, 2.1)
mtx = Gf.Matrix4d().SetLookAt(eye, Gf.Vec3d(0, 0, 0.5), Gf.Vec3d(0, 0, 1)).GetInverse()
UsdGeom.Xformable(persp).AddTransformOp().Set(mtx)
persp.CreateFocalLengthAttr(24.0)
persp.CreateClippingRangeAttr(Gf.Vec2f(0.01, 10000.0))

top = UsdGeom.Camera.Define(stage, "/World/TopCam")
mtx_t = Gf.Matrix4d().SetLookAt(Gf.Vec3d(0.01, 0, 9.0), Gf.Vec3d(0, 0, 0.3), Gf.Vec3d(0, 1, 0)).GetInverse()
UsdGeom.Xformable(top).AddTransformOp().Set(mtx_t)
top.CreateFocalLengthAttr(24.0)
top.CreateClippingRangeAttr(Gf.Vec2f(0.01, 10000.0))
pump(10)

# ---- simulate ----
log("playing physics to settle the pile")
timeline = omni.timeline.get_timeline_interface()
timeline.play()
pump(SETTLE_FRAMES)
# a few extra quiet frames
pump(60)
timeline.pause()
pump(10)
log("physics settled")

# ---- read settled transforms -> GT ----
xfc = UsdGeom.XformCache(Usd.TimeCode.Default())
barrels_gt = []
positions = []
for i, path in enumerate(barrel_paths):
    # read the geo prim's world transform — same frame cen_local/LOCAL_AXIS were
    # measured in (the referenced model content frame), after physics settling
    prim = stage.GetPrimAtPath(path + "/geo")
    M = xfc.GetLocalToWorldTransform(prim)   # Gf.Matrix4d
    R = M.ExtractRotationMatrix()            # 3x3
    T = M.ExtractTranslation()
    # world center = transform of local bbox center
    cl = Gf.Vec3d(cen_local[0], cen_local[1], cen_local[2])
    center_world = M.Transform(cl)
    # world axis = rotation applied to local long axis, normalized
    a = R * LOCAL_AXIS
    a = Gf.Vec3d(a[0], a[1], a[2])
    an = a.GetLength()
    axis_world = (a / an) if an > 1e-9 else Gf.Vec3d(0, 0, 1)
    positions.append([T[0], T[1], T[2]])
    barrels_gt.append({
        "id": i,
        "radius_m": RADIUS_M,
        "axis": [round(axis_world[0], 6), round(axis_world[1], 6), round(axis_world[2], 6)],
        "center": [round(center_world[0], 6), round(center_world[1], 6), round(center_world[2], 6)],
        "height_m": round(LENGTH_M, 6),
        "occlusion_frac": None,
    })

# tilt stats (angle of each axis from vertical) to confirm variety
tilts = [math.degrees(math.acos(min(1.0, abs(b["axis"][2])))) for b in barrels_gt]
log(f"GT built for {len(barrels_gt)} barrels; tilt-from-vertical "
    f"min={min(tilts):.1f} max={max(tilts):.1f} mean={np.mean(tilts):.1f} deg")

gt = {
    "scene": "isaac_pile01",
    "source": "isaac_sim",
    "sensor": "none_geometry_gt",
    "units": "m",
    "frame": "isaac_world (x, y, z up)",
    "barrels": barrels_gt,
}
os.makedirs(OUT_DIR, exist_ok=True)
with open(os.path.join(OUT_DIR, "gt.json"), "w") as f:
    json.dump(gt, f, indent=2)
log(f"wrote {os.path.join(OUT_DIR, 'gt.json')}")

# ---- save scene USD ----
pile_usd = os.path.join(OUT_DIR, "pile.usd")
stage.Export(pile_usd)
log(f"exported {pile_usd}")

# ---- screenshots: perspective then top-down ----
from omni.kit.viewport.utility import get_active_viewport, capture_viewport_to_file
vp = get_active_viewport()

vp.camera_path = "/World/PerspCam"
pump(120)
capture_viewport_to_file(vp, os.path.join(OUT_DIR, "pile_persp.png"))
pump(60)
log("captured pile_persp.png")

vp.camera_path = "/World/TopCam"
pump(120)
capture_viewport_to_file(vp, os.path.join(OUT_DIR, "pile_top.png"))
pump(60)
log("captured pile_top.png")

# leave on perspective for the external X grab
vp.camera_path = "/World/PerspCam"
pump(60)

log("SETUP COMPLETE — entering keepalive loop")
while simulation_app.is_running():
    simulation_app.update()
