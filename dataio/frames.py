"""Frame Index Derivation

The frame index is a property of the radar data, not of the manifest, so it is
always derived from the Parquet table rather than declared in ``info.json``.
That removes a whole class of drift: a manifest cannot go stale against the data
it describes, and re-exporting a log needs no manifest edit.

The capture rate is derived here too, from the same timestamps, so seeking a
camera stream uses a rate computed from the data rather than a declared one.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Any, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

# Column treated as wall-clock time when present. Timestamps fall back to
# index/fps when it is absent.
DEFAULT_TIME_KEY = "Time"
DEFAULT_FPS = 10.0


def find_time_key(
    data: pd.DataFrame, time_key: str = DEFAULT_TIME_KEY
) -> Optional[str]:
    """
    Locate the wall-clock time column, if the data has one.

    Args:
        data: Radar table.
        time_key: Column name to look for.

    Returns:
        The column name when present, else None.
    """
    return time_key if time_key in data.columns else None


def unique_frame_ids(data: pd.DataFrame, frame_key: str) -> np.ndarray:
    """
    Extract the sorted unique frame ids from the radar table.

    Args:
        data: Radar table.
        frame_key: Frame/slider column name.

    Returns:
        Sorted array of unique frame ids.

    Raises:
        KeyError: If ``frame_key`` is not a column.
    """
    if frame_key not in data.columns:
        raise KeyError(
            f"Frame key {frame_key!r} is not a column in the data "
            f"(available: {list(data.columns)})"
        )
    return np.sort(data[frame_key].unique())


def compute_timestamps(
    data: pd.DataFrame,
    frame_ids: Sequence[Any],
    frame_key: str,
    time_key: Optional[str] = None,
    fps: float = DEFAULT_FPS,
    time_scale: float = 1.0,
) -> List[float]:
    """
    Build the per-frame timestamp vector.

    Args:
        data: Radar table.
        frame_ids: Sorted unique frame ids.
        frame_key: Frame/slider column name.
        time_key: Optional wall-clock time column. When present its per-frame
            minimum is used, rebased so the first frame sits at t=0.
        fps: Fallback rate used when no usable time column exists.
        time_scale: Seconds per unit of the time column, from the manifest's
            ``time_unit``. Applied after rebasing so a millisecond epoch does
            not lose precision to float subtraction.

    Returns:
        List of timestamps in seconds, aligned index-wise with ``frame_ids``.
    """
    if time_key and time_key in data.columns:
        per_frame = data.groupby(frame_key)[time_key].min()
        stamps = [float(per_frame.get(frame_id, np.nan)) for frame_id in frame_ids]
        if stamps and not any(np.isnan(stamps)):
            base = stamps[0]
            return [round((value - base) * time_scale, 6) for value in stamps]

    return [round(index / fps, 6) for index in range(len(frame_ids))]


def derive_fps(timestamps: Sequence[float], fallback: float = DEFAULT_FPS) -> float:
    """
    Infer the capture frame rate from per-frame timestamps.

    Uses the median inter-frame delta so an occasional dropped frame does not
    skew the result.

    Args:
        timestamps: Per-frame timestamps in seconds.
        fallback: Rate to use when the timestamps are unusable.

    Returns:
        Frame rate in Hz, rounded to 3 decimals.
    """
    if len(timestamps) < 2:
        return fallback

    deltas = np.diff(np.asarray(timestamps, dtype=float))
    deltas = deltas[np.isfinite(deltas) & (deltas > 0)]
    if deltas.size == 0:
        return fallback

    median_delta = float(np.median(deltas))
    if median_delta <= 0:
        return fallback

    return round(1.0 / median_delta, 3)


def build_frame_index(
    data: pd.DataFrame,
    frame_key: str,
    time_key: Optional[str] = DEFAULT_TIME_KEY,
    fps: Optional[float] = None,
    time_scale: float = 1.0,
) -> Tuple[np.ndarray, List[float], float]:
    """
    Derive the complete frame index from a radar table in one pass.

    Args:
        data: Radar table.
        frame_key: Frame/slider column name.
        time_key: Wall-clock time column to look for; None skips the lookup.
        fps: Explicit capture rate. When None it is inferred from the derived
            timestamps.
        time_scale: Seconds per unit of the time column; see
            :func:`compute_timestamps`.

    Returns:
        Tuple of (frame ids, timestamps, fps).
    """
    frame_ids = unique_frame_ids(data, frame_key)
    resolved_time_key = find_time_key(data, time_key) if time_key else None
    timestamps = compute_timestamps(
        data, frame_ids, frame_key, resolved_time_key, fps or DEFAULT_FPS, time_scale
    )
    effective_fps = fps if fps is not None else derive_fps(timestamps)
    return frame_ids, timestamps, effective_fps
