#!/bin/bash
cd /isaac-sim
export DISPLAY=:1
export OMNI_KIT_ALLOW_ROOT=1
exec ./python.sh /root/barrel/barrel_import.py
