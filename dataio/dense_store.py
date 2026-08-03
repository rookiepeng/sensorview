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
    """Read-only accessor for 1D threshold series.

    One file holds many named series per frame -- a detection threshold, the
    signal it is applied to, a noise floor, and so on. Which series are drawn
    together, and how, is declared in ``info.json`` rather than inferred here.
    """

    def __init__(self, path: str) -> None:
        """
        Args:
            path: Path to the threshold HDF5 file.
        """
        self.path = path

    @property
    def exists(self) -> bool:
        """True when the backing file is present on disk."""
        return os.path.exists(self.path)

    def read_series(
        self, dataset_pattern: str, frame_id: Any = None
    ) -> Optional[np.ndarray]:
        """
        Read one 1D series.

        Args:
            dataset_pattern: Dataset path, optionally containing a
                ``{frame_id}`` placeholder for per-frame series. Patterns
                without the placeholder read a frame-independent dataset, which
                is how shared x-axes are stored.
            frame_id: Frame identifier substituted into the pattern.

        Returns:
            1D array of values, or None when absent. Multi-dimensional datasets
            are flattened, so a stored (1, N) row still plots.
        """
        if not self.exists or not dataset_pattern:
            return None

        dataset_path = _format_dataset(dataset_pattern, frame_id=frame_id)
        try:
            with h5py.File(self.path, "r") as handle:
                node = handle.get(dataset_path)
                if node is None:
                    return None
                values = np.asarray(node[()])
                return values.reshape(-1) if values.ndim > 1 else values
        except (OSError, KeyError):
            return None

    def read_axis(self, dataset_path: str) -> Optional[np.ndarray]:
        """
        Read a stored axis vector (e.g. range bins, Doppler bins).

        Args:
            dataset_path: Dataset path inside the file.

        Returns:
            1D array of axis values, or None when absent.
        """
        return self.read_series(dataset_path)

    def signals(self, frame_id: Any = None) -> List[str]:
        """
        List the series names stored for a frame.

        Useful when writing the ``info.json`` plot config against an existing
        file, and for validating that config at load time.

        Args:
            frame_id: Frame to inspect; defaults to the first frame present.

        Returns:
            Sorted series names; empty on any error or when the file has no
            frames.
        """
        if not self.exists:
            return []
        try:
            with h5py.File(self.path, "r") as handle:
                frames = handle.get("frames")
                if frames is None:
                    return []
                if frame_id is not None:
                    group = frames.get(str(frame_id))
                    return sorted(group.keys()) if group is not None else []
                for frame_name in frames:
                    group = frames[frame_name]
                    if isinstance(group, h5py.Group):
                        return sorted(group.keys())
                return []
        except (OSError, KeyError):
            return []


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
    Write per-frame 1D threshold series to an HDF5 sidecar.

    Args:
        path: Destination ``.h5`` path; parent directories are created.
        frames: Mapping of frame id to ``{series_name: 1D array}``.
        axes: Optional mapping of axis name to a 1D vector of bin values,
            stored under ``/axes/<name>``. Axes live outside the frame groups
            because they are usually shared by every frame.

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
