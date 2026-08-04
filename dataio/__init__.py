"""SensorView Data IO Package

Storage layer for the multi-sensor data architecture. Each data shape gets the
storage format that suits it:

- Radar point cloud -> Parquet (columnar, filtered/queried by the app)
- Lidar point cloud -> HDF5, decimated at ingest time (display-only backdrop)
- Threshold maps    -> HDF5, chunked per (frame, sensor) (display-only)
- Camera            -> mp4, seeked client-side

All stores join on ``frame_id``, which is derived from the radar Parquet rather
than declared anywhere. Logs share a case folder and are associated by basename
(``drive_01.parquet`` / ``drive_01.lidar.h5`` / ``drive_01.mp4``); the manifest
(``info.json`` v2) declares only the conventions, column metadata, and
calibration that cannot be inferred from the files themselves.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dataio.manifest import Manifest, ManifestError, log_stem
from dataio.calibration import Calibration, apply_transform
from dataio.frames import build_frame_index, derive_fps, unique_frame_ids
from dataio.radar_store import load_radar, scan_radar, write_radar
from dataio.dense_store import LidarStore, ThresholdStore

__all__ = [
    "Manifest",
    "ManifestError",
    "log_stem",
    "Calibration",
    "apply_transform",
    "build_frame_index",
    "derive_fps",
    "unique_frame_ids",
    "load_radar",
    "scan_radar",
    "write_radar",
    "LidarStore",
    "ThresholdStore",
]
