#!/bin/bash
# Rebuild 3DTK `show` from source inside the Ubuntu container.
# (Host build under 3DTK/bin is Arch-compiled and won't run here.)
set -e
cd /root/masters/3DTK

# Drop any host-built artifacts that came along in the copy.
rm -rf .build bin lib obj
mkdir -p .build && cd .build

# Build the freeglut/wx `show` viewer; Qt off to keep the build lean.
cmake -DWITH_QT=OFF -DWITH_WXWIDGETS=ON ..

# The `show` CMake target is a *library*; the executable target is `showbin`
# (OUTPUT_NAME=show). `show` also dlopen()s scan-format plugins at runtime
# from lib/, so build all scan_io_* shared libs too.
make -j"$(nproc)" showbin
SCANIO=$(make help | grep -oE 'scan_io_[a-z0-9_]+' | sort -u | tr '\n' ' ')
make -j"$(nproc)" $SCANIO

echo "=== build done ==="
ls -la /root/masters/3DTK/bin/show
ls /root/masters/3DTK/lib/ | grep scan_io_xyz
