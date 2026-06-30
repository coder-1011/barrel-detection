#!/bin/bash
# Annotation stack: same Xvfb :99 -> fluxbox -> x11vnc (:5901) -> noVNC (:6080) as
# start_all.sh, but launches **CloudCompare** (apt jammy/universe package) instead of
# 3DTK `show`, for manually segmenting barrels out of the pile.
#
# Run the container with the LIVE host masters bind-mounted read-write at /work so the
# cloud comes from the repo and exported segments land back on the host, e.g.:
#   sudo docker run -d --name 3dtk-annot --shm-size=2g -p 5901:5901 -p 6080:6080 \
#     --device /dev/dri -v ~/Projects/masters:/work 3dtk-show:latest sleep infinity
#   sudo docker exec 3dtk-annot bash /work/docker-3dtk-show/start_annotate.sh
# then open http://localhost:6080/vnc.html in a browser.
export DISPLAY=:99
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
export QT_X11_NO_MITSHM=1          # avoid Qt MIT-SHM issues under Xvfb

CLOUD="${1:-/work/data/real/station1_pit_barrels/scan000.pcd}"

# Install CloudCompare once (jammy universe). No-op if already present.
if ! command -v CloudCompare >/dev/null 2>&1 && ! command -v cloudcompare >/dev/null 2>&1; then
    echo "Installing cloudcompare (apt jammy/universe)..."
    apt-get update -qq && apt-get install -y -qq cloudcompare || {
        echo "apt install failed — enable 'universe' (add-apt-repository universe) or check network." >&2
    }
fi
CC=CloudCompare; command -v CloudCompare >/dev/null 2>&1 || CC=cloudcompare

pkill -f "Xvfb :99" 2>/dev/null || true
pkill -f x11vnc      2>/dev/null || true
pkill -f fluxbox     2>/dev/null || true
pkill -f websockify  2>/dev/null || true
pkill -f "$CC"       2>/dev/null || true
sleep 1

Xvfb :99 -screen 0 1600x1000x24 +extension GLX +render -noreset >/var/log/xvfb.log 2>&1 &
sleep 2
fluxbox >/var/log/fluxbox.log 2>&1 &
sleep 1
x11vnc -display :99 -forever -shared -nopw -rfbport 5901 -bg -o /var/log/x11vnc.log
websockify --web=/usr/share/novnc 6080 localhost:5901 >/var/log/novnc.log 2>&1 &
sleep 1

# Launch CloudCompare GUI. (Plain GUI: open the cloud via File > Open if it doesn't
# auto-load — '-O' would force CC's headless command mode, which we do NOT want here.)
echo "Launching $CC on $CLOUD"
"$CC" "$CLOUD" >/var/log/cloudcompare.log 2>&1 &
sleep 1
echo "Stack up: VNC :5901, noVNC http :6080, CloudCompare launched."
echo "If the cloud didn't open, in CloudCompare: File > Open -> $CLOUD"
