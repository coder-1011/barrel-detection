# 3DTK `show` in a ROS 2 Humble Docker container (interactive viewer)

Runs 3DTK's `show` point-cloud viewer **inside a container** and displays it via
an internal X server + VNC/noVNC. The mouse (orbit/zoom/pan) works because the
container runs its **own** X server (`Xvfb :99`) — input never goes through the
host's XWayland, which was the original broken path.

There are two ways to view it. **Direct display is the nicer one** (native window,
no browser) and was verified to work; VNC/noVNC is the fallback that fully isolates
input from the host XWayland.

- **GPU:** software OpenGL (Mesa **llvmpipe**) — pure CPU, uses no GPU at all.
  Reliable for the ~1.2M-pt cloud; on a many-core box it's actually fast.
- Verified: cloud renders and the mouse orbits/zooms/pans the camera
  (both directly on XWayland `:1` and over VNC).

### Mouse controls (verified against the source, `callbacks_glut.cpp`)

In **perspective** view (default / after clicking *Rotate view*):
- **Left-drag**   = orbit / rotate
- **Middle-drag up/down** = **zoom** (dolly in/out)  ← the wheel is NOT bound
- **Right-drag**  = pan

In **top / parallel** view (`--viewmode 1`, the dense overview — it's orthographic):
- middle-drag does not change apparent size; **zoom via the "Parallel Zoom" field**
  in the Controls window (smaller number = zoomed in), or click **"Rotate view"** to
  switch to perspective and use middle-drag.

No middle button (trackpad)? Some browsers send middle-click as left — easiest is to
use a real 3-button mouse, or switch to perspective and use the keyboard
(`Page Up`/`Page Down` move the camera forward/back).

### Seeing the cloud as DENSE (not scattered dots)

This is a **single-station** scan: the default camera starts *at the scanner
origin looking outward*, so you see only a thin slice and it looks sparse — the
1.2M points are all there, just spread across the full 360°. To view it dense:

- Launch with **`--viewmode 1`** (camera starts above the cloud) plus
  **`--pointsize 2`** and **`--no-fog`**:
  ```
  ./bin/show -s 1 -e 1 -o 0 -f xyz --viewmode 1 --pointsize 2 --no-fog <dir>
  ```
- In the **Controls** window: **"Top view"** = dense overhead overview;
  **"Rotate view"** = orbit in perspective.
- **Right-drag downward to zoom out** until the whole cloud fits the window.
- `show` only thins points *while you drag*; when you stop, it redraws **all**
  points (the default `pointmode 0`). For permanent all-points, tick
  **"Always all Points"** in the Controls window.

---

## Option 1 — Direct display (native window, recommended)

Renders `show` as a real window on your screen through the host's XWayland.
Two non-obvious requirements: `xhost` access, and **`--ipc=host`** (without it
`show` crashes with an MIT-SHM `X_ShmPutImage` error because the container's
shared memory isn't visible to XWayland).

```bash
sudo systemctl start docker

DISPLAY=:1 xhost +local:                 # allow local clients (undo: xhost -local:)

sudo docker rm -f 3dtk-direct 2>/dev/null
sudo docker run -d --name 3dtk-direct \
  --net=host --ipc=host \
  -e DISPLAY=:1 -e LIBGL_ALWAYS_SOFTWARE=1 -e GALLIUM_DRIVER=llvmpipe \
  -v /tmp/.X11-unix:/tmp/.X11-unix --device /dev/dri \
  3dtk-show:latest sleep infinity

sudo docker exec -d 3dtk-direct bash -c \
 'cd /root/masters/3DTK && DISPLAY=:1 LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe \
  ./bin/show -s 1 -e 1 -o 0 -f xyz /root/masters/data/real/station1_deployment1_scan8/'
```

Or just run `./run-direct.sh` (does all of the above).

**RViz2 (optional bonus)** in the same container:
```bash
sudo docker exec -it 3dtk-direct bash -lc 'source /opt/ros/humble/setup.bash && rviz2'
```

Cleanup: `DISPLAY=:1 xhost -local: ; sudo docker rm -f 3dtk-direct`

---

## Option 2 — VNC / noVNC (browser, fully input-isolated fallback)

Use this if direct display ever misbehaves (e.g. XWayland input regressions).
It runs its own `Xvfb :99` inside the container, so input never touches the host
compositor at all. Display path: `Xvfb :99` → `x11vnc` (:5901) → `noVNC` (:6080).

### Quick start (image already built on this machine)

A ready image `3dtk-show:latest` was committed with masters copied in and 3DTK
already built. To launch:

```bash
sudo systemctl start docker            # daemon is not enabled at boot here

sudo docker rm -f 3dtk 2>/dev/null
sudo docker run -d --name 3dtk --shm-size=2g \
  -p 5901:5901 -p 6080:6080 \
  --device /dev/dri \
  3dtk-show:latest sleep infinity

# start Xvfb + fluxbox + x11vnc + noVNC + launch show on the cloud:
sudo docker exec 3dtk bash /root/start_all.sh
```

Then open the viewer in a **browser** (no client install needed) — type this in
the Claude prompt with the `!` prefix, or run it yourself:

```
! xdg-open 'http://localhost:6080/vnc.html?autoconnect=1&resize=remote'
```

Click **Connect** if it doesn't auto-connect. Drag in the black 3D window:
left = orbit, right = zoom, middle = pan.

(Or use any native VNC client against `localhost:5901`, no password.)

---

## From scratch (full rebuild — reproducible)

```bash
sudo systemctl start docker

# 1. Build the image (apt deps + VNC/noVNC stack)
cd ~/Projects/masters/docker-3dtk-show
sudo docker build -t 3dtk-humble -f Dockerfile .

# 2. Run a container; bind-mount the host masters read-only; publish ports
sudo docker rm -f 3dtk 2>/dev/null
sudo docker run -d --name 3dtk --shm-size=2g \
  -p 5901:5901 -p 6080:6080 \
  --device /dev/dri \
  -v ~/Projects/masters:/host-masters:ro \
  3dtk-humble sleep infinity

# 3. Copy masters into the container (skip .venv + Arch build artifacts)
sudo docker exec 3dtk rsync -a \
  --exclude='.venv' --exclude='3DTK/.build' --exclude='3DTK/bin' \
  --exclude='3DTK/lib' --exclude='3DTK/obj' \
  /host-masters/ /root/masters/

# 4. Build 3DTK `show` (+ scan_io_* runtime plugins) inside the container
sudo docker cp build_3dtk.sh 3dtk:/root/build_3dtk.sh
sudo docker cp start_all.sh  3dtk:/root/start_all.sh
sudo docker exec 3dtk bash -c 'chmod +x /root/*.sh && bash /root/build_3dtk.sh'

# 5. Launch the stack + viewer
sudo docker exec 3dtk bash /root/start_all.sh

# 6. View in a browser
xdg-open 'http://localhost:6080/vnc.html?autoconnect=1&resize=remote'
```

Optionally snapshot the ready container so step 1–4 don't repeat:
```bash
sudo docker commit 3dtk 3dtk-show:latest
```

---

## Run on a remote server (headless, e.g. an A100 box)

The image is published at **`bharath147/3dtk-show:latest`** (private). On the server:

```bash
docker login -u bharath147                     # private repo needs auth on the server
docker pull bharath147/3dtk-show:latest

docker run -d --name 3dtk --shm-size=2g -p 5901:5901 -p 6080:6080 \
  bharath147/3dtk-show:latest sleep infinity
docker exec 3dtk bash /root/start_all.sh       # Xvfb + x11vnc + noVNC + show
```

From your laptop, open `http://<server-ip>:6080/vnc.html` (SSH-tunnel it if the
port isn't public: `ssh -L 6080:localhost:6080 user@server`, then use localhost).

### About GPU / A100

`show` renders with **llvmpipe (CPU)** — it never touches a GPU. So:

- **No file changes are needed**; the headless noVNC path above just works, and a
  many-core server usually renders the 1.2M points *smoother than a laptop*.
- The A100 will **not** accelerate `show` out of the box: it's a headless compute
  GPU, and `show` uses **freeglut + GLX**, which needs an X server bound to the GPU
  (or VirtualGL). That's a fiddly setup and rarely worth it for this viewer.
- If you still want HW GL: install `nvidia-container-toolkit` on the server, run
  with `--gpus all -e NVIDIA_DRIVER_CAPABILITIES=all`, and replace the `Xvfb` line
  in `start_all.sh` with a VirtualGL + virtual-X setup. Expectation: marginal gain
  for this app.

---

## The exact `show` invocation

`start_all.sh` runs (from `/root/masters/3DTK`):

```bash
DISPLAY=:99 LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe \
  ./bin/show -s 1 -e 1 -o 0 -f xyz \
  /root/masters/data/real/station1_deployment1_scan8/
```

`ERROR: No .frames could be found` and `3D Mouse not connected` are harmless.

To re-run just the viewer (stack already up):
```bash
sudo docker exec -d 3dtk bash -c \
 'cd /root/masters/3DTK && DISPLAY=:99 LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe \
  ./bin/show -s 1 -e 1 -o 0 -f xyz /root/masters/data/real/station1_deployment1_scan8/'
```

---

## Notes / troubleshooting

- **Black window / no points:** give it ~10–15 s — software rendering of 1.2M
  points is slow to first frame. `Always reduce Points` (on by default) thins
  points while moving; the full cloud redraws when you stop.
- **GL errors:** the stack forces `LIBGL_ALWAYS_SOFTWARE=1` (llvmpipe). The
  `--device /dev/dri` flag is optional and only used if you switch to HW GL.
- **Stop everything:** `sudo docker rm -f 3dtk`
- Approach A (forwarding the host's `DISPLAY=:1` XWayland into the container)
  was intentionally **not** used — it reuses the same XWayland whose mouse input
  was dead natively. This VNC approach (Approach B) sidesteps it entirely.
```
