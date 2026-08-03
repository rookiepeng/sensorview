"""Dense Frame-Indexed Stores (HDF5)

Lidar point clouds and radar threshold maps are both display-only, frame-indexed
dense arrays -- nobody queries them by column -- so Parquet's columnar machinery
would be wasted overhead. A chunked HDF5 dataset per frame is a contiguous
binary blob: smaller on disk and faster to pull one frame from. HDF5 also has
first-class MATLAB support (``h5read``), same as the rest of the format choices.

File handles are opened per read rather than cached, because Dash background
callbacks run in separate processes and an inherited HDF5 handle is not safe to
share across them. Opening is sub-millisecond and happens once per frame change.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Any, Dict, List, Optional, Sequence

import os

import h5py
import numpy as np

# Chunked + compressed: one frame is one chunk, so reading a frame touches one
# contiguous compressed block instead of striding the whole dataset.
_COMPRESSION = "gzip"
_COMPRESSION_OPTS = 4

DEFAULT_LIDAR_PATTERN = "/frames/{frame_id}"
DEFAULT_THRESHOLD_PATTERN = "/frames/{frame_id}/{sensor_id}"


def _format_dataset(pattern: str, **kwargs: Any) -> str:
    """
    Fill a dataset-path pattern, tolerating unused placeholders.

    Args:
        pattern: Path pattern such as ``/frames/{frame_id}/{sensor_id}``.
        **kwargs: Placeholder values.

    Returns:
        Concrete HDF5 dataset path.
    """
    try:
        return pattern.format(**kwargs)
    except KeyError as exc:
        raise ValueError(
            f"Dataset pattern {pattern!r} references unknown placeholder {exc}"
        ) from exc


class LidarStore:
    """Read-only accessor for the decimated lidar point cloud sidecar."""

    def __init__(
        self, path: str, dataset_pattern: str = DEFAULT_LIDAR_PATTERN
    ) -> None:
        """
        Args:
            path: Path to the lidar HDF5 file.
            dataset_pattern: Dataset path pattern with a ``{frame_id}`` placeholder.
        """
        self.path = path
        self.dataset_pattern = dataset_pattern

    @property
    def exists(self) -> bool:
        """True when the backing file is present on disk."""
        return os.path.exists(self.path)

    def read_frame(self, frame_id: Any) -> Optional[np.ndarray]:
        """
        Read one frame of decimated lidar points.

        Args:
            frame_id: Frame identifier.

        Returns:
            (N, C) float array where the first three columns are xyz, or None
            when the file or that frame's dataset is absent.
        """
        if not self.exists:
            return None

        dataset_path = _format_dataset(self.dataset_pattern, frame_id=frame_id)
        try:
            with h5py.File(self.path, "r") as handle:
                node = handle.get(dataset_path)
                if node is None:
                    return None
                return np.asarray(node[()])
        except (OSError, KeyError):
            return None

    def columns(self) -> List[str]:
        """
        Column names for the stored point arrays.

        Returns:
            List of column names from the file's ``columns`` attribute, or the
            xyz default when unset.
        """
        if not self.exists:
            return ["x", "y", "z"]
        try:
            with h5py.File(self.path, "r") as handle:
                cols = handle.attrs.get("columns")
                if cols is None:
                    return ["x", "y", "z"]
                return [c.decode() if isinstance(c, bytes) else str(c) for c in cols]
        except OSError:
            return ["x", "y", "z"]

    def frame_ids(self) -> List[str]:
        """
        List frame ids present in the file.

        Returns:
            Frame id strings under the ``/frames`` group; empty on any error.
        """
        if not self.exists:
            return []
        try:
            with h5py.File(self.path, "r") as handle:
                group = handle.get("frames")
                return list(group.keys()) if group is not None else []
        except OSError:
            return []


class ThresholdStore:
    """Read-only accessor for per-(frame, sensor) threshold maps."""

    def __init__(
        self, path: str, dataset_pattern: str = DEFAULT_THRESHOLD_PATTERN
    ) -> None:
        """
        Args:
            path: Path to the threshold-map HDF5 file.
            dataset_pattern: Dataset path pattern with ``{frame_id}`` and
                ``{sensor_id}`` placeholders.
        """
        self.path = path
        self.dataset_pattern = dataset_pattern

    @property
    def exists(self) -> bool:
        """True when the backing file is present on disk."""
        return os.path.exists(self.path)

    def read_map(self, frame_id: Any, sensor_id: str) -> Optional[np.ndarray]:
        """
        Read one threshold map.

        Args:
            frame_id: Frame identifier.
            sensor_id: Sensor identifier.

        Returns:
            2D array of map values, or None when absent.
        """
        if not self.exists:
            return None

        dataset_path = _format_dataset(
            self.dataset_pattern, frame_id=frame_id, sensor_id=sensor_id
        )
        try:
            with h5py.File(self.path, "r") as handle:
                node = handle.get(dataset_path)
                if node is None:
                    return None
                return np.asarray(node[()])
        except (OSError, KeyError):
            return None

    def sensors(self) -> List[str]:
        """
        Discover which sensors have maps in this file.

        Sensors are read from the file rather than declared in the manifest, so
        a log that adds a sensor needs no manifest edit.

        Args:
            None

        Returns:
            Sorted sensor ids taken from the first frame group; empty on any
            error or when the file has no frames.
        """
        if not self.exists:
            return []
        try:
            with h5py.File(self.path, "r") as handle:
                frames = handle.get("frames")
                if frames is None:
                    return []
                for frame_name in frames:
                    group = frames[frame_name]
                    if isinstance(group, h5py.Group):
                        return sorted(group.keys())
                return []
        except (OSError, KeyError):
            return []

    def read_axis(self, dataset_path: str) -> Optional[np.ndarray]:
        """
        Read a stored axis vector (e.g. range bins, Doppler bins).

        Args:
            dataset_path: Absolute dataset path inside the file.

        Returns:
            1D array of axis values, or None when absent.
        """
        if not self.exists or not dataset_path:
            return None
        try:
            with h5py.File(self.path, "r") as handle:
                node = handle.get(dataset_path)
                if node is None:
                    return None
                return np.asarray(node[()])
        except (OSError, KeyError):
            return None


def write_lidar_frames(
    path: str,
    frames: Dict[Any, np.ndarray],
    columns: Sequence[str] = ("x", "y", "z"),
) -> str:
    """
    Write decimated lidar frames to an HDF5 sidecar.

    Args:
        path: Destination ``.h5`` path; parent directories are created.
        frames: Mapping of frame id to an (N, C) point array.
        columns: Column names describing the point arrays.

    Returns:
        The path written.
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    with h5py.File(path, "w") as handle:
        handle.attrs["columns"] = [str(c) for c in columns]
        group = handle.create_group("frames")
        for frame_id, points in frames.items():
            points = np.asarray(points, dtype=np.float32)
            group.create_dataset(
                str(frame_id),
                data=points,
                chunks=points.shape if points.size else None,
                compression=_COMPRESSION if points.size else None,
                compression_opts=_COMPRESSION_OPTS if points.size else None,
            )
    return path


def write_threshold_frames(
    path: str,
    frames: Dict[Any, Dict[str, np.ndarray]],
    axes: Optional[Dict[str, np.ndarray]] = None,
) -> str:
    """
    Write per-(frame, sensor) threshold maps to an HDF5 sidecar.

    Args:
        path: Destination ``.h5`` path; parent directories are created.
        frames: Mapping of frame id to ``{sensor_id: 2D array}``.
        axes: Optional mapping of axis name to a 1D vector of bin values,
            stored under ``/axes/<name>``.

    Returns:
        The path written.
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    with h5py.File(path, "w") as handle:
        if axes:
            axis_group = handle.create_group("axes")
            for name, values in axes.items():
                axis_group.create_dataset(
                    str(name), data=np.asarray(values, dtype=np.float32)
                )

        group = handle.create_group("frames")
        for frame_id, sensors in frames.items():
            frame_group = group.create_group(str(frame_id))
            for sensor_id, values in sensors.items():
                values = np.asarray(values, dtype=np.float32)
                frame_group.create_dataset(
                    str(sensor_id),
                    data=values,
                    chunks=values.shape if values.size else None,
                    compression=_COMPRESSION if values.size else None,
                    compression_opts=_COMPRESSION_OPTS if values.size else None,
                )
    return path
