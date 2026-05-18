# barrel-detection

Single-frame barrel detection from an Asus Xtion Pro depth camera, using the
[3DTK](https://threedtk.de/) toolkit's `detectCylinder` (Randomized Hough Transform)
with Open3D for pre/post-processing and visualization.

Target: an 8.5 cm-diameter plastic barrel from a single depth frame at
0.5–1 m range. Pipeline is offline / single-frame.

## Layout

```
barrel_pipeline/
├── capture_one_frame.py    # ROS 2 subscriber on /camera/depth/points → scan000.{pcd,3d,pose}
├── crop_barrel.py          # voxel + RANSAC plane removal + DBSCAN + barrel priors
├── compute_normals_o3d.py  # Open3D estimate_normals with sensor-orientation
├── synth_cylinder.py       # synthetic half-shell point clouds for controlled tests
├── inspect_clusters.py     # diagnostic: print/visualize DBSCAN clusters
├── view_cloud.py           # Open3D viewer for PCD + optional cylinder overlay
└── data*/                  # captured + synthetic scans (see below)
```

## Local dependencies (not in this repo)

Both live as siblings of `barrel_pipeline/` in the working tree:

- **3DTK** — clone and build per upstream instructions. The pipeline runs
  `bin/detectCylinder` and expects the cfg at
  `include/detectCylinder/cylinderDetector.cfg`. The cfg path is resolved
  relative to cwd, so always `cd` into the 3DTK source root before running.
- **openni2_camera** — ROS 2 Humble driver for the Asus Xtion Pro. Use the
  `camera_with_cloud_norgb.launch.py` launch file (the standard one tries to
  open RGB, which the Xtion Pro doesn't have).

## Pipeline

1. **Launch camera** (ROS 2):
   ```bash
   ros2 launch openni2_camera camera_with_cloud_norgb.launch.py
   ```
2. **Capture** one frame:
   ```bash
   python3 capture_one_frame.py data3
   ```
3. **Crop** to barrel cluster(s) — multi-barrel scenes supported:
   ```bash
   python3 crop_barrel.py --pcd data3/scan000.pcd --out data3_crop
   ```
4. **Normals** (Open3D sensor-oriented; do not use 3DTK `calc_normals` —
   it produces ~39% flipped normals on small-radius surfaces):
   ```bash
   python3 compute_normals_o3d.py --in data3_crop --radius-cm 0.4 --max-nn 15
   ```
5. **Detect**:
   ```bash
   cd <3DTK source root>
   bin/detectCylinder -s 0 -e 0 -f uos_normal \
     <repo>/barrel_pipeline/data3_crop/normals_o3d/
   ```
6. **Visualize**:
   ```bash
   python3 view_cloud.py --pcd data3_crop/scan000.pcd \
     --cylinders data3_crop/normals_o3d/detectCylinder/cylinder.2d
   ```

## Units

- Open3D / `.pcd` files: **meters**
- 3DTK / `.3d` and `cylinder.2d`: **centimeters**

Conversion is handled inside each script; raw `cylinder.2d` reads are in cm.

## Notes

- `cylinder.2d` may contain phantom duplicates (low lateral-pt counts, short
  axis extent). Post-filter on `lateralPts >= 1000` and `extent >= 10 cm`
  before treating a detection as real.
- Barrel priors in `crop_barrel.py` are tuned for an 8.5 cm-diameter target
  (`--target-width 0.085 --width-tol 0.03`). For different sizes pass
  appropriate values.
