"""Point-Cloud Backdrop

The decimated cloud behind the detections, read one frame at a time and handed
straight to the renderer.

Cloud frames are deliberately *not* copied into the session cache: the chunked
HDF5 sidecar is already a frame-indexed cache, and duplicating decimated points
per frame onto disk would buy nothing over a few-millisecond chunk read.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Any, Dict, Optional

import numpy as np

from dataio.calibration import apply_transform
from dataio.dense_store import CloudStore
from dataio.manifest import Manifest

from viz.graph_data import get_cloud_scatter3d_data


def get_cloud_points(
    manifest: Manifest, stem: str, frame_id: Any, apply_calibration: bool = True
) -> Optional[np.ndarray]:
    """
    Read one frame of decimated cloud points, in the reference frame.

    Args:
        manifest: Dataset manifest.
        stem: Log stem.
        frame_id: Frame identifier.
        apply_calibration: Whether to apply the cloud extrinsics. Needed for the
            overlay to line up with the table; skip only for raw inspection.

    Returns:
        (N, 3+) point array, or None when the log has no cloud or that frame is
        missing.
    """
    if not manifest.has_cloud(stem):
        return None

    store = CloudStore(
        manifest.cloud_path(stem),
        manifest.cloud_dataset_pattern(),
        manifest.cloud_columns(),
    )
    points = store.read_frame(frame_id)
    if points is None or len(points) == 0:
        return None

    if apply_calibration:
        calibration = manifest.cloud_calibration()
        if not calibration.is_identity:
            transformed = apply_transform(points[:, :3], calibration)
            if points.shape[1] > 3:
                points = np.column_stack([transformed, points[:, 3:]])
            else:
                points = transformed

    return points


def get_cloud_trace(
    manifest: Optional[Manifest], stem: str, frame_id: Any
) -> Optional[Dict[str, Any]]:
    """
    Build the point-cloud backdrop trace for one frame.

    Args:
        manifest: Dataset manifest, or None.
        stem: Log stem.
        frame_id: Frame identifier.

    Returns:
        Scatter3d trace dictionary, or None when there is no cloud to draw.
    """
    if manifest is None or not stem:
        return None

    points = get_cloud_points(manifest, stem, frame_id)
    if points is None:
        return None

    return get_cloud_scatter3d_data(points, manifest.cloud_display())
