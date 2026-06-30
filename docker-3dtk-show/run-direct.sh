#!/bin/bash
# Direct-display launch: show 3DTK `show` (and/or RViz2) as a NATIVE window on the
# host's screen, via the host's XWayland (DISPLAY=:1). No VNC, no browser.
#
# Requires two things that tripped up the naive attempt:
#   1. xhost access for local clients
#   2. --ipc=host  (otherwise show dies with an MIT-SHM X_ShmPutImage BadValue error,
#      because the container's shared-memory segments aren't visible to XWayland)
set -e

# 1. Allow the container to talk to the host X server (undo later with: xhost -local:)
DISPLAY=:1 xhost +local: >/dev/null

# 2. (Re)create the container sharing the host's net + IPC + X socket
sudo docker rm -f 3dtk-direct 2>/dev/null || true
sudo docker run -d --name 3dtk-direct \
  --net=host --ipc=host \
  -e DISPLAY=:1 \
  -e LIBGL_ALWAYS_SOFTWARE=1 -e GALLIUM_DRIVER=llvmpipe \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  --device /dev/dri \
  3dtk-show:latest sleep infinity >/dev/null

# 3. Launch the viewer straight onto the host screen.
#    --viewmode 1 : start camera ABOVE the cloud (dense overview; default view sits
#                   AT the scanner origin looking out, which looks deceptively sparse)
#    --pointsize 2 / --no-fog : make the full 1.2M-pt cloud read as dense.
sudo docker exec -d 3dtk-direct bash -c \
  'cd /root/masters/3DTK && DISPLAY=:1 LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe \
   ./bin/show -s 1 -e 1 -o 0 -f xyz --viewmode 1 --pointsize 2 --no-fog \
   /root/masters/data/real/station1_deployment1_scan8/'

echo "show launched on DISPLAY=:1 (native window). left-drag=orbit, right-drag=zoom, middle-drag=pan."
echo "Dense overview = 'Top view' button; 'Rotate view' to orbit in perspective; right-drag down to zoom out."
echo "RViz2 bonus:  sudo docker exec -it 3dtk-direct bash -lc 'source /opt/ros/humble/setup.bash && rviz2'"
echo "When done:    DISPLAY=:1 xhost -local:   &&   sudo docker rm -f 3dtk-direct"
