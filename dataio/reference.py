"""Reference Pose Sidecar (Parquet)

The reference overlay -- the host vehicle, usually -- can come from a sidecar of
its own, ``<stem>.reference.parquet``, instead of from columns embedded in the
table:

    frame | x | y | z | yaw | pitch | roll

One row per frame, positions in meters and angles in radians, keyed on the same
frame ids the table uses. A sidecar exists because a pose is per *frame*, not
per detection: carrying six more columns on every one of a log's 300k rows to
say where one vehicle was in 400 frames is a waste, and it cannot express
orientation at all -- the table path only ever reads a position, so a mesh
placed from it sits square to the axes however the vehicle is pointing.

Column names are the exporter's, not this app's, so the mapping from file column
to pose field is configured -- in the manifest's ``reference.columns`` block, or
in the 3D view's reference pickers, which write back to it. A file that already
names its columns ``x``/``yaw``/... needs no mapping at all.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Any, Dict, List, Optional, Tuple

import os

import numpy as np
import polars as pl

# Pose fields in the order the renderer wants them. Position in meters,
# orientation in radians (ZYX intrinsic: yaw about z, pitch about y, roll about
# x), matching the convention :mod:`dataio.calibration` uses for mountings.
POSE_FIELDS = ("x", "y", "z", "yaw", "pitch", "roll")
POSITION_FIELDS = ("x", "y", "z")

# Every field the manifest's `reference.columns` block can map. `frame` is not a
# pose field -- it is what pairs a sidecar row with a table frame -- but it is
# just as configurable, so anything keyed on "how is this file mapped" has to
# count it.
MAPPED_FIELDS = POSE_FIELDS + ("frame",)


def _fingerprint(path: str) -> Tuple[float, int]:
    """
    Identify one version of a file on disk.

    Args:
        path: File path.

    Returns:
        ``(mtime, size)``, or ``(0.0, -1)`` when the file cannot be stat'ed --
        distinct from any real file, so an unreadable path never returns a
        cached table belonging to a different one.
    """
    try:
        stat = os.stat(path)
    except OSError:
        return (0.0, -1)
    return (stat.st_mtime, stat.st_size)


def _frame_key(value: Any) -> Any:
    """
    Normalize a frame id to a stable dictionary key.

    The table's frame ids arrive as numpy scalars, Python ints, or floats
    depending on which path read them; ``33616142465`` must hit the same entry
    whichever it is.

    Args:
        value: Frame id in any numeric form.

    Returns:
        ``int`` for an integral value, ``float`` otherwise, and the value
        untouched when it is not numeric at all.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value

    if not np.isfinite(number):
        return value
    if number.is_integer():
        return int(number)
    return number


class ReferenceStore:
    """One log's per-frame reference pose, read from its Parquet sidecar."""

    # The whole sidecar is one row per frame -- a few hundred rows against the
    # table's hundreds of thousands -- so it is read once and kept, rather than
    # re-read on the per-frame path the way the chunked HDF5 stores are.
    _cache: Dict[Tuple[str, float, int], "ReferenceStore"] = {}

    def __init__(
        self,
        path: str,
        columns: Optional[Dict[str, Optional[str]]] = None,
        frame_key: Optional[str] = None,
    ) -> None:
        """
        Args:
            path: Path to the sidecar Parquet.
            columns: Mapping of pose field -> column name, as configured. Fields
                the mapping omits fall back to a column named after the field
                itself, so a self-describing file needs no configuration.
            frame_key: The table's frame column name, used when the mapping does
                not name one.
        """
        self.path = path
        self.columns = dict(columns or {})
        self.frame_key = frame_key

        self._table: Optional[pl.DataFrame] = None
        self._poses: Dict[Any, Dict[str, float]] = {}
        self._bounds: Optional[Dict[str, Tuple[float, float]]] = None
        self._resolved: Dict[str, Optional[str]] = {}

        self._load()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def open(
        cls,
        path: str,
        columns: Optional[Dict[str, Optional[str]]] = None,
        frame_key: Optional[str] = None,
    ) -> Optional["ReferenceStore"]:
        """
        Open a sidecar, reusing the parsed table when nothing changed on disk.

        Args:
            path: Path to the sidecar Parquet.
            columns: Pose field -> column name mapping.
            frame_key: The table's frame column name.

        Returns:
            Store instance, or None when the file does not exist.
        """
        if not path or not os.path.exists(path):
            return None

        mtime, size = _fingerprint(path)
        # The mapping is part of the key: repointing a picker has to re-derive
        # the poses, and a mapping change leaves the file itself untouched. That
        # includes `frame` -- pointing it at another column re-keys every pose in
        # the file, which is the largest change a picker can make, not one to
        # answer out of the cache.
        signature = f"{path}|{frame_key}|" + "|".join(
            f"{field}={(columns or {}).get(field)}" for field in MAPPED_FIELDS
        )
        key = (signature, mtime, size)

        cached = cls._cache.get(key)
        if cached is not None:
            return cached

        store = cls(path, columns, frame_key)
        # One log at a time is the norm; a handful covers flipping between logs
        # without letting an all-day session accumulate every case ever opened.
        if len(cls._cache) > 8:
            cls._cache.clear()
        cls._cache[key] = store
        return store

    def _resolve(self, available: List[str]) -> None:
        """
        Decide which file column feeds each pose field.

        Args:
            available: Column names present in the file.
        """
        lowered = {name.lower(): name for name in available}

        def pick(field: str) -> Optional[str]:
            configured = self.columns.get(field)
            if configured and configured in available:
                return configured
            # Unmapped, or mapped to a column this file does not have: a column
            # named after the field is the obvious intent either way.
            return lowered.get(field)

        self._resolved = {field: pick(field) for field in POSE_FIELDS}

        frame_column = self.columns.get("frame")
        if not frame_column or frame_column not in available:
            frame_column = None
            for candidate in (self.frame_key, "frame", "frame_id", "frame_idx"):
                if candidate and candidate in available:
                    frame_column = candidate
                    break
                if candidate and candidate.lower() in lowered:
                    frame_column = lowered[candidate.lower()]
                    break
        self._resolved["frame"] = frame_column

    def _load(self) -> None:
        """Read the sidecar and index its poses by frame id."""
        try:
            table = pl.read_parquet(self.path)
        except Exception:
            return

        self._table = table
        available = list(table.columns)
        self._resolve(available)

        frame_column = self._resolved.get("frame")
        if frame_column is None or not self.is_usable:
            return

        frames = table[frame_column].to_numpy()
        values = {}
        for field in POSE_FIELDS:
            column = self._resolved.get(field)
            if column is None:
                values[field] = np.zeros(len(frames), dtype=float)
            else:
                # Angles or positions written as ints read back as ints; the
                # renderer wants floats either way.
                column_values = table[column].cast(pl.Float64, strict=False).to_numpy()
                values[field] = np.nan_to_num(column_values, nan=0.0)

        for row, frame_id in enumerate(frames):
            self._poses[_frame_key(frame_id)] = {
                field: float(values[field][row]) for field in POSE_FIELDS
            }

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def is_usable(self) -> bool:
        """
        Whether the sidecar carries enough to place a reference.

        A pose with no x or y column places nothing; z and the three angles all
        default to zero, which is a flat, unrotated reference rather than a
        missing one.
        """
        return bool(self._resolved.get("x") and self._resolved.get("y"))

    @property
    def available_columns(self) -> List[str]:
        """Column names in the sidecar, in file order."""
        return list(self._table.columns) if self._table is not None else []

    @property
    def resolved_columns(self) -> Dict[str, Optional[str]]:
        """The column actually feeding each pose field, plus ``frame``."""
        return dict(self._resolved)

    def pose(self, frame_id: Any) -> Optional[Dict[str, float]]:
        """
        Read the reference pose for one frame.

        Args:
            frame_id: Frame id as used by the table.

        Returns:
            Dict with every field in :data:`POSE_FIELDS`, or None when the
            sidecar has no row for that frame -- a gap draws nothing rather than
            stranding the reference at its last known pose.
        """
        if not self._poses:
            return None
        return self._poses.get(_frame_key(frame_id))

    def bounds(self) -> Optional[Dict[str, Tuple[float, float]]]:
        """
        Position extent across every frame in the sidecar.

        The 3D scene fixes its axis ranges from the table's filter ranges, and a
        reference that travels beyond them would simply be clipped away, so the
        ranges have to be widened by what this returns.

        Returns:
            ``{"x": (min, max), "y": ..., "z": ...}``, or None when the sidecar
            holds no usable rows.
        """
        if self._bounds is not None:
            return self._bounds
        if not self._poses:
            return None

        extent = {}
        for field in POSITION_FIELDS:
            values = [pose[field] for pose in self._poses.values()]
            extent[field] = (float(min(values)), float(max(values)))

        self._bounds = extent
        return extent
