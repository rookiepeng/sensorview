"""Per-Frame Data Sources

Bridges the session cache to the :mod:`dataio` stores, and defines which data
gets re-read on which trigger.

The split matters for performance. Radar is refiltered whenever a filter
changes; lidar, threshold maps, and camera are display-only and only ever
change when the frame changes. Dragging a filter slider therefore never touches
the lidar or threshold path.

Sidecars resolve from the *current log's stem*, cached per session alongside the
frame index derived from that log's Parquet. When several logs are overlaid, the
primary selected log owns the backdrop, maps, and video -- those are per-log
data with no meaningful way to merge.

Lidar frames are deliberately *not* copied into the session cache: the chunked
HDF5 sidecar is already a frame-indexed cache, and duplicating decimated points
per frame onto disk would buy nothing over a few-millisecond chunk read.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Any, Dict, List, Optional

import numpy as np

from app_config import CACHE_KEYS

from dataio.calibration import apply_transform
from dataio.dense_store import LidarStore, ThresholdStore
from dataio.manifest import Manifest

from utils import cache_get, cache_set

from viz.graph_data import get_lidar_scatter3d_data
from viz.viz import get_threshold_map


def cache_manifest(manifest: Manifest, session_id: str) -> None:
    """
    Store a manifest in the session cache.

    Only the raw dictionary and case directory are cached; the ``Manifest``
    wrapper is rebuilt on read so cached sessions survive code changes to it.

    Args:
        manifest: Manifest to cache.
        session_id: Session identifier.
    """
    cache_set(
        {
            "raw": manifest.raw,
            "case_dir": manifest.case_dir,
            "source_version": manifest.source_version,
        },
        session_id,
        CACHE_KEYS["manifest"],
    )


def get_manifest(session_id: str) -> Optional[Manifest]:
    """
    Retrieve the cached manifest for a session.

    Args:
        session_id: Session identifier.

    Returns:
        Manifest instance, or None when nothing is cached yet.
    """
    cached = cache_get(session_id, CACHE_KEYS["manifest"])
    if not cached:
        return None
    return Manifest(
        cached["raw"],
        cached["case_dir"],
        source_version=cached.get("source_version", 2),
    )


def cache_log_info(
    session_id: str, stem: str, timestamps: List[float], fps: float
) -> None:
    """
    Store the current log's identity and derived frame index.

    Args:
        session_id: Session identifier.
        stem: Log stem that sidecars are keyed on.
        timestamps: Per-frame timestamps derived from the Parquet data.
        fps: Capture rate derived from those timestamps.
    """
    cache_set(
        {"stem": stem, "timestamps": timestamps, "fps": fps},
        session_id,
        CACHE_KEYS["log_info"],
    )


def get_log_info(session_id: str) -> Dict[str, Any]:
    """
    Retrieve the current log's identity and derived frame index.

    Args:
        session_id: Session identifier.

    Returns:
        Dict with ``stem``, ``timestamps``, and ``fps``; empty values when
        nothing is cached yet.
    """
    cached = cache_get(session_id, CACHE_KEYS["log_info"])
    if not cached:
        return {"stem": "", "timestamps": [], "fps": 0.0}
    return cached


def get_log_stem(session_id: str) -> str:
    """
    Retrieve the current log's stem.

    Args:
        session_id: Session identifier.

    Returns:
        Log stem, or an empty string when nothing is cached yet.
    """
    return get_log_info(session_id).get("stem", "")


def get_lidar_points(
    manifest: Manifest, stem: str, frame_id: Any, apply_calibration: bool = True
) -> Optional[np.ndarray]:
    """
    Read one frame of decimated lidar points, in the reference frame.

    Args:
        manifest: Dataset manifest.
        stem: Log stem.
        frame_id: Frame identifier.
        apply_calibration: Whether to apply the lidar extrinsics. Needed for the
            overlay to line up with radar; skip only for raw inspection.

    Returns:
        (N, 3+) point array, or None when the log has no lidar or that frame is
        missing.
    """
    if not manifest.has_lidar(stem):
        return None

    store = LidarStore(manifest.lidar_path(stem), manifest.lidar_dataset_pattern())
    points = store.read_frame(frame_id)
    if points is None or len(points) == 0:
        return None

    if apply_calibration:
        calibration = manifest.lidar_calibration()
        if not calibration.is_identity:
            transformed = apply_transform(points[:, :3], calibration)
            if points.shape[1] > 3:
                points = np.column_stack([transformed, points[:, 3:]])
            else:
                points = transformed

    return points


def get_lidar_trace(
    manifest: Optional[Manifest], stem: str, frame_id: Any
) -> Optional[Dict[str, Any]]:
    """
    Build the lidar backdrop trace for one frame.

    Args:
        manifest: Dataset manifest, or None.
        stem: Log stem.
        frame_id: Frame identifier.

    Returns:
        Scatter3d trace dictionary, or None when there is no lidar to draw.
    """
    if manifest is None or not stem:
        return None

    points = get_lidar_points(manifest, stem, frame_id)
    if points is None:
        return None

    return get_lidar_scatter3d_data(points, manifest.lidar_display())


def get_threshold_sensors(manifest: Optional[Manifest], stem: str) -> List[Dict[str, str]]:
    """
    List the sensors with threshold maps in the current log.

    Args:
        manifest: Dataset manifest, or None.
        stem: Log stem.

    Returns:
        List of ``{"id", "label"}`` dicts; empty when the log has no maps.
    """
    if manifest is None or not manifest.has_threshold(stem):
        return []

    store = ThresholdStore(
        manifest.threshold_path(stem), manifest.threshold_dataset_pattern()
    )
    return [
        {"id": sensor, "label": sensor.replace("_", " ").title()}
        for sensor in store.sensors()
    ]


def get_threshold_value_range(
    manifest: Optional[Manifest],
    stem: str,
    sensor_id: str,
    session_id: str,
    frame_ids: Optional[Any] = None,
    max_frames: int = 50,
) -> Optional[list]:
    """
    Estimate a stable color range for a sensor's threshold maps.

    Re-normalizing per frame makes levels jump while scrubbing, so the range is
    estimated once per (log, sensor) and cached for the session. Estimation
    samples at most ``max_frames`` evenly spaced frames and uses the 2nd/98th
    percentiles, which keeps a single hot cell from flattening the rest.

    Args:
        manifest: Dataset manifest, or None.
        stem: Log stem.
        sensor_id: Sensor identifier.
        session_id: Session identifier, used as the cache scope.
        frame_ids: Frame ids to sample from, as derived from the Parquet data.
        max_frames: Maximum number of frames to sample.

    Returns:
        ``[vmin, vmax]``, or None when no maps could be read.
    """
    if manifest is None or not sensor_id or not manifest.has_threshold(stem):
        return None

    cache_key = f"{stem}/{sensor_id}"
    cached = cache_get(session_id, CACHE_KEYS["threshold_range"], cache_key)
    if cached is not None:
        return cached

    if frame_ids is None or len(frame_ids) == 0:
        return None

    frame_ids = np.asarray(frame_ids)
    if len(frame_ids) > max_frames:
        indices = np.linspace(0, len(frame_ids) - 1, max_frames).astype(int)
        sampled = frame_ids[indices]
    else:
        sampled = frame_ids

    store = ThresholdStore(
        manifest.threshold_path(stem), manifest.threshold_dataset_pattern()
    )

    lows, highs = [], []
    for frame_id in sampled:
        values = store.read_map(frame_id, sensor_id)
        if values is None or np.size(values) == 0:
            continue
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            continue
        lows.append(float(np.percentile(finite, 2)))
        highs.append(float(np.percentile(finite, 98)))

    if not lows:
        return None

    value_range = [min(lows), max(highs)]
    cache_set(value_range, session_id, CACHE_KEYS["threshold_range"], cache_key)
    return value_range


def get_threshold_figure(
    manifest: Optional[Manifest],
    stem: str,
    frame_id: Any,
    sensor_id: str,
    colormap: str = "Jet",
    value_range: Optional[list] = None,
) -> Dict[str, Any]:
    """
    Build the threshold-map figure for one (frame, sensor).

    Args:
        manifest: Dataset manifest, or None.
        stem: Log stem.
        frame_id: Frame identifier.
        sensor_id: Sensor identifier.
        colormap: Colorscale name.
        value_range: Optional [min, max] color clamp held constant across frames.

    Returns:
        Figure dictionary; an empty placeholder figure when no map exists.
    """
    if manifest is None or not sensor_id or not manifest.has_threshold(stem):
        return get_threshold_map(None)

    block = manifest.threshold or {}
    store = ThresholdStore(
        manifest.threshold_path(stem), manifest.threshold_dataset_pattern()
    )
    values = store.read_map(frame_id, sensor_id)

    axes = block.get("axes") or {}
    x_axis = axes.get("x") or {}
    y_axis = axes.get("y") or {}

    return get_threshold_map(
        values,
        x_values=store.read_axis(x_axis.get("values_dataset", "")),
        y_values=store.read_axis(y_axis.get("values_dataset", "")),
        x_label=x_axis.get("label", ""),
        y_label=y_axis.get("label", ""),
        value_label=block.get("value_label", ""),
        colormap=colormap,
        value_range=value_range,
    )
