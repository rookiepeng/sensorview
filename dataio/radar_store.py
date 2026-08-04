"""Radar Point Cloud Store (Parquet)

The radar point cloud is the only dataset the app filters and queries, so it
stays tabular and columnar. Parquet gives compressed columnar storage with
predicate/projection pushdown, and MATLAB reads it natively via
``parquetread``/``parquetwrite`` (unlike Feather/Arrow IPC).

Legacy ``.csv`` and ``.pkl`` inputs are still accepted so existing datasets load
without conversion; only Parquet gets the lazy pushdown path.

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

# Polars only recognizes "inf"/"-inf" as float tokens out of the box; a bare
# "nan" makes it infer the whole column as a string, so list it (and common
# variants) as null values to keep numeric columns numeric.
CSV_NULL_VALUES = ["nan", "NaN", "NAN", "null", "NULL"]

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


def _read_one(path: str) -> pl.DataFrame:
    """
    Eagerly read a single radar file of any supported format.

    Args:
        path: Path to a ``.parquet``, ``.csv``, or ``.pkl`` file.

    Returns:
        Polars DataFrame of the file contents.

    Raises:
        ValueError: If the file extension is not supported.
    """
    lowered = path.lower()
    if lowered.endswith(".parquet"):
        return pl.read_parquet(path)
    if lowered.endswith(".csv"):
        return pl.read_csv(path, null_values=CSV_NULL_VALUES)
    if lowered.endswith(".pkl"):
        return pl.from_pandas(pd.read_pickle(path))
    raise ValueError(f"Unsupported file type: {os.path.basename(path)}")


def scan_radar(paths: Sequence[str]) -> pl.LazyFrame:
    """
    Build a lazy scan over Parquet radar files.

    Args:
        paths: Parquet file paths. Must all be Parquet; use :func:`load_radar`
            for mixed or legacy formats.

    Returns:
        LazyFrame over the concatenated files, ready for pushdown filtering.

    Raises:
        ValueError: If ``paths`` is empty or contains a non-Parquet file.
    """
    if not paths:
        raise ValueError("scan_radar requires at least one path")
    if not all(p.lower().endswith(".parquet") for p in paths):
        raise ValueError("scan_radar only accepts .parquet files")

    if len(paths) == 1:
        return pl.scan_parquet(paths[0])

    try:
        return pl.scan_parquet(list(paths))
    except Exception:
        # Schemas differ across files (e.g. sensors with different columns);
        # diagonal concat keeps the union of columns and null-fills the rest.
        return pl.concat(
            [pl.scan_parquet(p) for p in paths], how="diagonal_relaxed"
        )


def load_radar(
    file_list: Optional[Iterable[FileSpec]] = None,
    file: Optional[FileSpec] = None,
    columns: Optional[Sequence[str]] = None,
    frame_key: Optional[str] = None,
    frame_ids: Optional[Sequence[Any]] = None,
) -> pd.DataFrame:
    """
    Load radar point cloud data into a pandas DataFrame.

    When every input is Parquet, projection (``columns``) and the frame
    predicate (``frame_key``/``frame_ids``) are pushed down into the scan so
    only the needed bytes leave disk.

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

    all_parquet = all(p.lower().endswith(".parquet") for p in paths)

    if all_parquet:
        frame = scan_radar(paths)
        if columns:
            frame = frame.select(list(columns))
        if frame_key and frame_ids is not None:
            frame = frame.filter(pl.col(frame_key).is_in(list(frame_ids)))
        data = _scalarize_list_columns(frame.collect()).to_pandas()
    else:
        parts = [_read_one(path) for path in paths]
        combined = (
            parts[0] if len(parts) == 1 else pl.concat(parts, how="diagonal_relaxed")
        )
        if columns:
            combined = combined.select([c for c in columns if c in combined.columns])
        if frame_key and frame_ids is not None and frame_key in combined.columns:
            combined = combined.filter(pl.col(frame_key).is_in(list(frame_ids)))
        data = _scalarize_list_columns(combined).to_pandas()

    data = data.reset_index(drop=True)
    return _normalize_non_finite(data)


def write_radar(data: pd.DataFrame, path: str, compression: str = "zstd") -> str:
    """
    Write a radar point cloud table to Parquet.

    Args:
        data: DataFrame to write.
        path: Destination ``.parquet`` path; parent directories are created.
        compression: Parquet codec. ``zstd`` gives the best size/speed tradeoff
            here and is readable by MATLAB's ``parquetread``.

    Returns:
        The path written.
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    pl.from_pandas(data).write_parquet(path, compression=compression)
    return path
