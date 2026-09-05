"""SensorView Data IO Package

Read layer for the multi-sensor data architecture. Each data shape gets the
storage format that suits it:

- Table             -> Parquet (columnar, filtered/queried by the app)
- Cloud             -> HDF5, pre-decimated (display-only backdrop)
- Curves            -> HDF5, one (N, 2) pair per (frame, series) (display-only)
- Images            -> mp4, seeked client-side
- Reference pose    -> Parquet, one row per frame (display-only)

Datasets are authored externally; nothing here writes them.

All stores join on ``frame_id``, which is derived from the table Parquet rather
than declared anywhere. Logs share a case folder and are associated by basename
(``drive_01.parquet`` / ``drive_01.cloud.h5`` / ``drive_01.mp4``); the manifest
(``info.json`` v2) declares only the conventions, column metadata, and
calibration that cannot be inferred from the files themselves.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dataio.manifest import Manifest, ManifestError, log_stem
from dataio.calibration import Calibration, apply_transform
from dataio.frames import unique_frame_ids
from dataio.radar_store import load_radar, scan_radar
from dataio.dense_store import CloudStore, CurveStore
from dataio.reference import ReferenceStore

__all__ = [
    "Manifest",
    "ManifestError",
    "log_stem",
    "Calibration",
    "apply_transform",
    "unique_frame_ids",
    "load_radar",
    "scan_radar",
    "CloudStore",
    "CurveStore",
    "ReferenceStore",
]
