#!/bin/bash
# Start the full stack: Xvfb :99 -> fluxbox -> x11vnc (:5901) -> noVNC web (:6080),
# then launch 3DTK `show` on the cloud. Self-contained; isolates mouse input from host.
export DISPLAY=:99
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe

pkill -f "Xvfb :99" 2>/dev/null || true
pkill -f x11vnc      2>/dev/null || true
pkill -f fluxbox     2>/dev/null || true
pkill -f websockify  2>/dev/null || true
pkill -f bin/show    2>/dev/null || true
sleep 1

Xvfb :99 -screen 0 1600x1000x24 +extension GLX +render -noreset >/var/log/xvfb.log 2>&1 &
sleep 2
fluxbox >/var/log/fluxbox.log 2>&1 &
sleep 1
x11vnc -display :99 -forever -shared -nopw -rfbport 5901 -bg -o /var/log/x11vnc.log
# noVNC: serve a browser client on :6080, proxying to the VNC server on :5901
websockify --web=/usr/share/novnc 6080 localhost:5901 >/var/log/novnc.log 2>&1 &
sleep 1

# Launch the viewer (1,234,883-pt cloud; mouse: left=orbit, right=zoom, middle=pan).
# --viewmode 1 / --pointsize 2 / --no-fog -> dense overview (the default view sits at the
# scanner origin looking out and looks deceptively sparse).
cd /root/masters/3DTK
./bin/show -s 1 -e 1 -o 0 -f xyz --viewmode 1 --pointsize 2 --no-fog \
    /root/masters/data/real/station1_deployment1_scan8/ \
    >/var/log/show.log 2>&1 &
sleep 1
echo "Stack up: VNC :5901, noVNC http :6080, show launched."
