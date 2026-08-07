"""Radar Point Cloud Store (Parquet)

The radar point cloud is the only dataset the app filters and queries, so it
stays tabular and columnar. Parquet gives compressed columnar storage with
predicate/projection pushdown, and MATLAB reads it natively via
``parquetread``/``parquetwrite`` (unlike Feather/Arrow IPC).

Parquet is the only accepted table format, which is what lets every read go
through the lazy pushdown path.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

import json
import os

import numpy as np
import pandas as pd
import polars as pl

FileSpec = Union[str, Dict[str, str]]


def _resolve_path(spec: FileSpec) -> str:
    """
    Turn one file specification into an absolute-ish filesystem path.

    Args:
        spec: Either a plain path, a JSON string of ``{"path", "name"}`` as the
            file pickers emit, or that same dict directly.

    Returns:
        Filesystem path to the data file.
    """
    if isinstance(spec, dict):
        return os.path.join(spec["path"], spec["name"])

    if isinstance(spec, str):
        stripped = spec.strip()
        if stripped.startswith("{"):
            file_dict = json.loads(stripped)
            return os.path.join(file_dict["path"], file_dict["name"])
        return spec

    raise ValueError(f"Unsupported file specification: {spec!r}")


def resolve_paths(
    file_list: Optional[Iterable[FileSpec]], file: Optional[FileSpec] = None
) -> List[str]:
    """
    Normalize the app's file-picker values into a list of paths.

    Args:
        file_list: Additional selected files (may be None or empty).
        file: Primary selected file, appended when not already present.

    Returns:
        De-duplicated list of filesystem paths, order preserved.
    """
    specs: List[FileSpec] = list(file_list or [])
    if file is not None and file not in specs:
        specs.append(file)

    paths: List[str] = []
    for spec in specs:
        path = _resolve_path(spec)
        if path not in paths:
            paths.append(path)
    return paths


def frame_ids_by_file(
    file_list: Optional[Iterable[FileSpec]],
    file: Optional[FileSpec] = None,
    frame_key: str = "Frame",
) -> List[tuple]:
    """
    List each selected file's own frame ids, without loading the tables.

    Combining logs concatenates their rows, which loses track of which log a
    given frame came from -- and every sidecar (cloud, curves, video, pose) is
    keyed on its log's stem, so that has to be recoverable. Only the frame
    column is read, so this stays cheap even when several logs are in play.

    Args:
        file_list: Additional selected files (may be None or empty).
        file: Primary selected file, appended when not already present.
        frame_key: Frame column name.

    Returns:
        List of ``(path, frame_ids)`` in :func:`resolve_paths` order, so the
        primary log comes last. A file without the frame column contributes an
        empty list rather than raising -- it simply owns no frames.
    """
    owners: List[tuple] = []
    for path in resolve_paths(file_list, file):
        try:
            ids = (
                pl.scan_parquet(path)
                .select(pl.col(frame_key).unique())
                .collect()
                .to_series()
            )
        except (pl.exceptions.PolarsError, KeyError, ValueError, OSError):
            owners.append((path, []))
            continue
        owners.append((path, ids.to_list()))
    return owners


def _scalarize_list_columns(frame: pl.DataFrame) -> pl.DataFrame:
    """
    Collapse Parquet list columns down to plain scalar columns.

    Exporters routinely emit a column as a length-1 list -- a sensor id written
    as ``["sensor_1"]`` rather than ``"sensor_1"`` is the common case. Pandas
    turns those into columns of numpy arrays, which are unhashable, so the very
    first thing the app does with a categorical column (``.unique()`` to build
    its filter dropdown) raises ``TypeError``. Nothing downstream can plot or
    filter a list either way, so flatten at the door.

    Args:
        frame: Radar table as read from disk.

    Returns:
        The same table with every List/Array column replaced by a scalar one.
        Numeric-like elements keep their dtype and only the first element
        survives; anything else is joined into a string, which is lossless for
        the length-1 case and still readable for longer lists.
    """
    exprs = []
    for name, dtype in frame.schema.items():
        if not isinstance(dtype, (pl.List, pl.Array)):
            continue

        inner = dtype.inner
        if inner.is_numeric() or inner.is_temporal() or inner == pl.Boolean:
            exprs.append(pl.col(name).list.first().alias(name))
        else:
            exprs.append(
                pl.col(name).cast(pl.List(pl.String)).list.join(", ").alias(name)
            )

    return frame.with_columns(exprs) if exprs else frame


def _normalize_non_finite(data: pd.DataFrame) -> pd.DataFrame:
    """
    Replace +/-Inf with NaN across numeric columns.

    Keeps downstream min/max, filtering, and plotting code dealing with a single
    "missing" representation.

    Args:
        data: DataFrame to normalize in place.

    Returns:
        The same DataFrame, normalized.
    """
    numeric_cols = data.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) > 0:
        data[numeric_cols] = data[numeric_cols].replace([np.inf, -np.inf], np.nan)
    return data


def scan_radar(paths: Sequence[str]) -> pl.LazyFrame:
    """
    Build a lazy scan over Parquet radar files.

    Args:
        paths: Parquet file paths.

    Returns:
        LazyFrame over the concatenated files, ready for pushdown filtering.

    Raises:
        ValueError: If ``paths`` is empty or contains a non-Parquet file.
    """
    if not paths:
        raise ValueError("scan_radar requires at least one path")

    # Named rather than counted: this message is what the file picker surfaces
    # when someone selects a table the app cannot read.
    unsupported = next((p for p in paths if not p.lower().endswith(".parquet")), None)
    if unsupported is not None:
        raise ValueError(f"Unsupported file type: {os.path.basename(unsupported)}")

    if len(paths) == 1:
        return pl.scan_parquet(paths[0])

    try:
        return pl.scan_parquet(list(paths))
    except Exception:
        # Schemas differ across files (e.g. sensors with different columns);
        # diagonal concat keeps the union of columns and null-fills the rest.
        return pl.concat([pl.scan_parquet(p) for p in paths], how="diagonal_relaxed")


def load_radar(
    file_list: Optional[Iterable[FileSpec]] = None,
    file: Optional[FileSpec] = None,
    columns: Optional[Sequence[str]] = None,
    frame_key: Optional[str] = None,
    frame_ids: Optional[Sequence[Any]] = None,
) -> pd.DataFrame:
    """
    Load radar point cloud data into a pandas DataFrame.

    Projection (``columns``) and the frame predicate (``frame_key`` /
    ``frame_ids``) are pushed down into the scan so only the needed bytes leave
    disk.

    Args:
        file_list: Selected files (paths, dicts, or file-picker JSON strings).
        file: Primary selected file, merged into ``file_list``.
        columns: Optional column subset to project.
        frame_key: Frame column name, required to use ``frame_ids``.
        frame_ids: Optional frame ids to restrict the read to.

    Returns:
        Combined DataFrame with a fresh RangeIndex and non-finite values
        normalized to NaN.

    Raises:
        ValueError: If no files are given or a file type is unsupported.
    """
    paths = resolve_paths(file_list, file)
    if not paths:
        raise ValueError("No data files selected")

    frame = scan_radar(paths)
    if columns:
        frame = frame.select(list(columns))
    if frame_key and frame_ids is not None:
        frame = frame.filter(pl.col(frame_key).is_in(list(frame_ids)))

    data = _scalarize_list_columns(frame.collect()).to_pandas()
    data = data.reset_index(drop=True)
    return _normalize_non_finite(data)
