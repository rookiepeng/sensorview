"""Dense Frame-Indexed Stores (HDF5)

Point clouds and 1D curves are both display-only, frame-indexed
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

from typing import Any, List, Optional, Tuple

import os
import posixpath

import h5py
import numpy as np

DEFAULT_CLOUD_PATTERN = "/frame_{frame_id}"
DEFAULT_CURVE_PATTERN = "/frame_{frame_id}/{name}"


def _format_dataset(pattern: str, **kwargs: Any) -> str:
    """
    Fill a dataset-path pattern, tolerating unused placeholders.

    Args:
        pattern: Path pattern such as ``/frame_{frame_id}/{name}``.
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


def _split_xy(values: np.ndarray) -> Tuple[Optional[np.ndarray], np.ndarray]:
    """
    Split an (N, 2) dataset into its x and y vectors.

    MATLAB writes column-major, so a 2xN array there reads back as (N, 2) here;
    both orientations are accepted so the same file works either way.

    Args:
        values: Raw dataset contents.

    Returns:
        Tuple of (x, y). x is None for a dataset that is not a coordinate pair,
        which is not a layout this reads but is worth plotting against the
        sample index rather than failing on.
    """
    if values.ndim == 2:
        if values.shape[1] == 2:
            return np.ascontiguousarray(values[:, 0]), np.ascontiguousarray(
                values[:, 1]
            )
        if values.shape[0] == 2:
            return np.ascontiguousarray(values[0]), np.ascontiguousarray(values[1])

    return None, values.reshape(-1)


def _frame_nodes(path: str, template: str) -> List[str]:
    """
    List the per-frame node names a pattern resolves to.

    Splitting the template at ``{frame_id}`` gives the parent to list and the
    prefix its frame members carry, which resolves ``/frame_<id>`` and the
    nested ``/frames/<id>`` alike. The prefix is also what keeps MATLAB's ``#refs#``
    bookkeeping out of the result.

    Args:
        path: HDF5 file path.
        template: Path template containing ``{frame_id}``.

    Returns:
        Sorted ``(parent, name)`` joined paths; empty on any error.
    """
    head, _, tail = template.partition("{frame_id}")
    parent = posixpath.dirname(head) or "/"
    prefix = posixpath.basename(head)

    try:
        with h5py.File(path, "r") as handle:
            group = handle.get(parent)
            if group is None:
                return []
            return sorted(
                posixpath.join(parent, name)
                for name in group
                if name.startswith(prefix) and name.endswith(tail)
            )
    except (OSError, KeyError):
        return []


class CloudStore:
    """Read-only accessor for the decimated point-cloud sidecar."""

    def __init__(
        self, path: str, dataset_pattern: str = DEFAULT_CLOUD_PATTERN
    ) -> None:
        """
        Args:
            path: Path to the cloud HDF5 file.
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
        Read one frame of decimated cloud points.

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

        Derived from this store's dataset pattern rather than assuming a layout,
        so ``/frames/<id>`` and ``/frame_<id>`` both resolve.

        Returns:
            Frame id strings; empty on any error.
        """
        if not self.exists or "{frame_id}" not in self.dataset_pattern:
            return []

        head, _, tail = self.dataset_pattern.partition("{frame_id}")
        prefix = posixpath.basename(head)
        paths = _frame_nodes(self.path, self.dataset_pattern)
        return [
            posixpath.basename(p)[len(prefix) : len(posixpath.basename(p)) - len(tail)]
            if tail
            else posixpath.basename(p)[len(prefix) :]
            for p in paths
        ]


class CurveStore:
    """Read-only accessor for 1D curves.

    One file holds many named curves per frame -- a detection threshold, the
    signal it is applied to, a noise floor, and so on. Which series are drawn
    together, and how, is declared in ``info.json`` rather than inferred here.

    Every dataset is an (N, 2) pair carrying its own x column. A shared x vector
    would be smaller, but it cannot describe real data: range bins differ from
    one sensor to the next, and differ frame to frame as the look type
    alternates, so the axis belongs with the curve it measures.

    Where a frame's series live is not assumed either -- the dataset pattern
    says, which covers both ``/frame_{frame_id}/{name}`` -- what this package
    writes, and what a MATLAB struct array reads back as -- and the nested
    ``/frames/{frame_id}/{name}`` an older export may carry.
    """

    def __init__(self, path: str, sensor_id: Optional[str] = None) -> None:
        """
        Args:
            path: Path to the curve HDF5 file.
            sensor_id: Value for a ``{sensor_id}`` placeholder, for files that
                key their series by sensor internally rather than one file each.
        """
        self.path = path
        self.sensor_id = sensor_id

    @property
    def exists(self) -> bool:
        """True when the backing file is present on disk."""
        return os.path.exists(self.path)

    def _read_raw(
        self, dataset_pattern: str, frame_id: Any = None
    ) -> Optional[np.ndarray]:
        """
        Read one dataset verbatim, without reshaping it.

        Args:
            dataset_pattern: Dataset path, optionally containing ``{frame_id}``
                and ``{sensor_id}`` placeholders.
            frame_id: Frame identifier substituted into the pattern.

        Returns:
            The dataset contents, or None when absent.
        """
        if not self.exists or not dataset_pattern:
            return None

        dataset_path = _format_dataset(
            dataset_pattern, frame_id=frame_id, sensor_id=self.sensor_id
        )
        try:
            with h5py.File(self.path, "r") as handle:
                node = handle.get(dataset_path)
                if node is None:
                    return None
                return np.asarray(node[()])
        except (OSError, KeyError):
            return None

    def read_curve(
        self, dataset_pattern: str, frame_id: Any = None
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Read one curve as an (x, y) pair.

        Args:
            dataset_pattern: Dataset path; see :meth:`_read_raw`.
            frame_id: Frame identifier substituted into the pattern.

        Returns:
            Tuple of (x, y); see :func:`_split_xy`. Both are None when the
            dataset is absent.
        """
        values = self._read_raw(dataset_pattern, frame_id)
        if values is None:
            return None, None

        return _split_xy(values)

    def read_series(
        self, dataset_pattern: str, frame_id: Any = None
    ) -> Optional[np.ndarray]:
        """
        Read one 1D series, dropping any x column it carries.

        Args:
            dataset_pattern: Dataset path; see :meth:`_read_raw`.
            frame_id: Frame identifier substituted into the pattern.

        Returns:
            1D array of values, or None when absent.
        """
        return self.read_curve(dataset_pattern, frame_id)[1]

    def frame_groups(
        self, dataset_pattern: str = DEFAULT_CURVE_PATTERN
    ) -> List[str]:
        """
        List the per-frame group paths present in the file.

        The pattern up to ``{name}`` is the group holding one frame's series.
        Splitting *that* at ``{frame_id}`` gives the parent group to list and
        the prefix its frame members carry -- which resolves ``/frame_<id>``
        and the nested ``/frames/<id>`` alike, and skips MATLAB's ``#refs#``
        bookkeeping.

        Args:
            dataset_pattern: Dataset path pattern from the manifest.

        Returns:
            Sorted group paths; empty on any error.
        """
        if not self.exists or not dataset_pattern:
            return []

        template = dataset_pattern.split("{name}")[0].rstrip("/") or "/"
        if "{frame_id}" not in template:
            return [template]

        return _frame_nodes(self.path, template)

    def signals(
        self,
        dataset_pattern: str = DEFAULT_CURVE_PATTERN,
        frame_id: Any = None,
    ) -> List[str]:
        """
        List the series names stored for a frame.

        Useful when writing the ``info.json`` plot config against an existing
        file, and for validating that config at load time.

        Args:
            dataset_pattern: Dataset path pattern from the manifest.
            frame_id: Frame to inspect; defaults to the first frame present.

        Returns:
            Sorted series names; empty on any error or when the file has no
            frames.
        """
        if not self.exists:
            return []

        if frame_id is not None:
            template = dataset_pattern.split("{name}")[0].rstrip("/") or "/"
            paths = [
                _format_dataset(template, frame_id=frame_id, sensor_id=self.sensor_id)
            ]
        else:
            paths = self.frame_groups(dataset_pattern)[:1]

        if not paths:
            return []

        try:
            with h5py.File(self.path, "r") as handle:
                group = handle.get(paths[0])
                if not isinstance(group, h5py.Group):
                    return []
                return sorted(group.keys())
        except (OSError, KeyError):
            return []

