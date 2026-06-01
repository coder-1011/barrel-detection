#!/usr/bin/env python3
"""
Capture one PointCloud2 frame from the Asus Xtion Pro and write:
  data/scan000.pcd   - ASCII PCD in meters (for Open3D / pcl_viewer)
  data/scan000.3d    - 3DTK uos format in centimeters
  data/scan000.pose  - identity pose (origin at the camera optical frame)

Usage:
  source /opt/ros/humble/setup.bash
  source ~/masters/openni2_camera/install/setup.bash
  # camera launched separately in another terminal
  python3 capture_one_frame.py [outdir]            (default outdir: ./data)
  python3 capture_one_frame.py data /camera/depth/points
"""
import os
import sys
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import PointCloud2


def pc2_to_xyz(msg: PointCloud2) -> np.ndarray:
    """Decode a PointCloud2 into an (N,3) float32 array, dropping NaNs."""
    offsets = {f.name: f.offset for f in msg.fields if f.name in ("x", "y", "z")}
    if not all(k in offsets for k in ("x", "y", "z")):
        raise RuntimeError("PointCloud2 missing x/y/z fields")
    dt = np.dtype({
        "names":   ["x", "y", "z"],
        "formats": ["<f4", "<f4", "<f4"],
        "offsets": [offsets["x"], offsets["y"], offsets["z"]],
        "itemsize": msg.point_step,
    })
    arr = np.frombuffer(msg.data, dtype=dt, count=msg.width * msg.height)
    xyz = np.stack([arr["x"], arr["y"], arr["z"]], axis=1)
    return xyz[np.isfinite(xyz).all(axis=1)]


class CaptureOnce(Node):
    def __init__(self, outdir: str, topic: str):
        super().__init__("capture_once")
        self.outdir = outdir
        self.done = False
        self.create_subscription(PointCloud2, topic, self.cb, qos_profile_sensor_data)
        self.get_logger().info(f"Waiting for one frame on {topic} ...")

    def cb(self, msg: PointCloud2):
        if self.done:
            return
        xyz_m = pc2_to_xyz(msg)
        n = xyz_m.shape[0]
        if n == 0:
            self.get_logger().warn("Frame has 0 valid points; waiting for next.")
            return

        os.makedirs(self.outdir, exist_ok=True)
        pcd_path = os.path.join(self.outdir, "scan000.pcd")
        with open(pcd_path, "w") as f:
            f.write(
                "# .PCD v0.7 - Point Cloud Data\n"
                "VERSION 0.7\nFIELDS x y z\nSIZE 4 4 4\nTYPE F F F\nCOUNT 1 1 1\n"
                f"WIDTH {n}\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\n"
                f"POINTS {n}\nDATA ascii\n"
            )
            np.savetxt(f, xyz_m, fmt="%.6f")

        # 3DTK uos: cm, plain "x y z" per line, identity pose.
        threed = os.path.join(self.outdir, "scan000.3d")
        np.savetxt(threed, xyz_m * 100.0, fmt="%.4f")
        with open(os.path.join(self.outdir, "scan000.pose"), "w") as f:
            f.write("0 0 0\n0 0 0\n")

        self.get_logger().info(
            f"Captured {n} pts, frame_id='{msg.header.frame_id}'.\n"
            f"  -> {pcd_path}\n  -> {threed}\n  -> {os.path.join(self.outdir,'scan000.pose')}"
        )
        self.done = True
        rclpy.shutdown()


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else "data"
    topic  = sys.argv[2] if len(sys.argv) > 2 else "/camera/depth/points"
    rclpy.init()
    rclpy.spin(CaptureOnce(outdir, topic))


if __name__ == "__main__":
    main()
