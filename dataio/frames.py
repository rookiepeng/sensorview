"""Frame Index Derivation

The frame index is a property of the radar data, not of the manifest, so it is
always derived from the Parquet table rather than declared in ``info.json``.
That removes a whole class of drift: a manifest cannot go stale against the data
it describes, and re-exporting a log needs no manifest edit.

Only the frame ids are derived. Wall-clock timestamps and a capture rate used to
be built here as well, for a camera seek that worked in seconds; that seek now
maps frame counts, so nothing reads either one.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

import numpy as np
import pandas as pd


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
