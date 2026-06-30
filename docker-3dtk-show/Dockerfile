# 3DTK `show` viewer inside ROS 2 Humble (Ubuntu 22.04), displayed via a
# self-contained X server + VNC/noVNC. This isolates mouse input completely
# from the host's XWayland, which is what makes orbit/zoom/pan actually work.
#
# Build:  sudo docker build -t 3dtk-humble -f Dockerfile .
FROM osrf/ros:humble-desktop

ENV DEBIAN_FRONTEND=noninteractive

# 3DTK build deps (from 3DTK/doc/equivs/control.ubuntu.jammy) + an internal
# X/VNC/noVNC stack + xdotool (used to script/verify mouse input).
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential cmake cmake-curses-gui ninja-build \
      freeglut3-dev imagemagick \
      libann-dev libboost-all-dev libcgal-dev libcgal-qt5-dev \
      libconfig-dev libeigen3-dev libftgl-dev \
      libgl1-mesa-dev libgl1-mesa-dri libglfw3-dev \
      libnewmat10-dev libopencv-calib3d-dev libopencv-dev libpng-dev \
      libqt5opengl5-dev libsuitesparse-dev libwxgtk3.0-gtk3-dev \
      libxi-dev libxml2-dev libxmlrpc-c++8-dev libxmu-dev libzip-dev \
      python3-dev qtbase5-dev xauth xvfb zlib1g-dev \
      x11vnc fluxbox xdotool wmctrl x11-utils x11-apps mesa-utils \
      novnc websockify python3-numpy \
      rsync net-tools libosmesa6 \
    && rm -rf /var/lib/apt/lists/*

EXPOSE 5901 6080
CMD ["sleep", "infinity"]
