"""
Barrel import into Isaac Sim 5.1.0 (standalone, windowed on DISPLAY=:1).

- Renders a Kit window on the current X display (:1) so an external
  `import -window root` grab captures a real RTX viewport.
- Converts rollreifenfass200l.obj -> USD via omni.kit.asset_converter.
- References it under /World/Barrel (stage is meters, Z-up; OBJ already ~0.9m).
- Adds lights, frames a camera on the barrel, captures a PNG itself, then
  loops update() forever so the app window stays alive for the X grab.
"""
import sys
import time

from isaacsim import SimulationApp

# headless=False -> Kit opens a real window on $DISPLAY (:1). RTX renderer.
simulation_app = SimulationApp({"headless": False, "width": 1280, "height": 720})

import carb
import omni.usd
import omni.kit.app
import omni.kit.commands
import asyncio
from pxr import Usd, UsdGeom, UsdLux, Sdf, Gf

OBJ = "/root/barrel/rollreifenfass200l.obj"
USD_OUT = "/root/barrel/barrel.usd"
SELF_SHOT = "/root/barrel/barrel_selfcapture.png"


def pump(n):
    for _ in range(n):
        simulation_app.update()


def log(msg):
    print(f"[BARREL] {msg}", flush=True)


# ---- let the app fully come up ----
log("app booting; pumping updates")
pump(120)

# ---- convert OBJ -> USD ----
import omni.kit.asset_converter as ac

log(f"converting {OBJ} -> {USD_OUT}")
converter = ac.get_instance()
ctx_cfg = ac.AssetConverterContext()
task = converter.create_converter_task(OBJ, USD_OUT, None, ctx_cfg)

# drive the async task by pumping the app loop until it finishes
loop = asyncio.get_event_loop()
success = False
for i in range(600):
    if task.is_finished():
        success = task.get_status() == ac.AssetConverterStatus.SUCCESS
        break
    simulation_app.update()
    time.sleep(0.05)
else:
    log("converter task did not finish in time")

if not task.is_finished():
    # give it a hard await as a fallback
    try:
        success = loop.run_until_complete(task.wait_until_finished())
    except Exception as e:  # noqa
        log(f"wait_until_finished raised: {e}")

log(f"convert finished: success={success} status={task.get_status()} detail={task.get_error_message()}")
if not success:
    log("CONVERSION FAILED — aborting")
    simulation_app.close()
    sys.exit(2)

# ---- build the stage ----
ctx = omni.usd.get_context()
ctx.new_stage()
pump(20)
stage = ctx.get_stage()
UsdGeom.SetStageMetersPerUnit(stage, 1.0)
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)

UsdGeom.Xform.Define(stage, "/World")

# reference the converted barrel
barrel = stage.DefinePrim("/World/Barrel", "Xform")
barrel.GetReferences().AddReference(USD_OUT)
# OBJ already in meters (~0.9m tall) -> keep scale 1.0 at origin. The referenced
# prim already carries a scale xformOp; use XformCommonAPI (tolerant) if a change
# is ever needed. No scale op added here (1.0 is a no-op).
log("barrel referenced at /World/Barrel")

# ---- lights (otherwise RTX viewport is black) ----
dome = UsdLux.DomeLight.Define(stage, "/World/DomeLight")
dome.CreateIntensityAttr(1000.0)
distant = UsdLux.DistantLight.Define(stage, "/World/KeyLight")
distant.CreateIntensityAttr(3000.0)
UsdGeom.Xformable(distant).AddRotateXYZOp().Set(Gf.Vec3f(-45.0, 0.0, 45.0))

# ---- camera framing the barrel (barrel ~0.9m tall, centered near origin) ----
cam = UsdGeom.Camera.Define(stage, "/World/BarrelCam")
cam_xf = UsdGeom.Xformable(cam)
# place camera up and back, looking down at the barrel center (~z=0)
eye = Gf.Vec3d(1.6, -1.6, 0.9)
target = Gf.Vec3d(0.0, 0.0, 0.0)
up = Gf.Vec3d(0.0, 0.0, 1.0)
# build look-at matrix
mtx = Gf.Matrix4d().SetLookAt(eye, target, up).GetInverse()
cam_xf.AddTransformOp().Set(mtx)
cam.CreateFocalLengthAttr(24.0)
cam.CreateClippingRangeAttr(Gf.Vec2f(0.01, 10000.0))
pump(10)

# ---- set active viewport camera to our camera + frame ----
try:
    from omni.kit.viewport.utility import get_active_viewport
    vp = get_active_viewport()
    vp.camera_path = "/World/BarrelCam"
    log("active viewport camera set to /World/BarrelCam")
except Exception as e:  # noqa
    log(f"viewport camera set failed: {e}")

# select + frame as belt-and-suspenders
try:
    ctx.get_selection().set_selected_prim_paths(["/World/Barrel"], True)
    pump(5)
    omni.kit.commands.execute("FramePrimsCommand", prim_to_move=["/World/Barrel"])
except Exception as e:  # noqa
    log(f"frame command failed: {e}")

# ---- let RTX converge ----
log("rendering / converging")
pump(200)

# ---- self capture ----
try:
    from omni.kit.viewport.utility import capture_viewport_to_file, get_active_viewport
    capture_viewport_to_file(get_active_viewport(), SELF_SHOT)
    pump(60)
    log(f"self-capture requested -> {SELF_SHOT}")
except Exception as e:  # noqa
    log(f"self-capture failed: {e}")

log("SETUP COMPLETE — entering keepalive loop (Ctrl-C / kill to stop)")
# keepalive so the X window stays for external `import -window root`
while simulation_app.is_running():
    simulation_app.update()
