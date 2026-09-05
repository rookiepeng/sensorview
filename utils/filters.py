"""Frame and DataFrame Filtering

The two things every view does to a loaded table before drawing it: reduce it to
the rows the filter panel allows, and make sure the slider position it was handed
actually points at a frame.

Both are on the hot path -- :func:`filter_all` runs on every filter change, for
every open view -- so the numerical and categorical passes build one boolean mask
with numpy rather than chaining DataFrame slices.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import List, Optional, Tuple, Union

import pandas as pd
import numpy as np


def clamp_frame_index(
    frame_list: Union[List[float], "np.ndarray"], slider_arg: Optional[int]
) -> Optional[int]:
    """
    Bring a slider position inside the current frame list.

    Loading a dataset replaces the frame list and resets the slider, but those
    are two separate callbacks firing off the same trigger, so for one round the
    old position is read against the new list. A shorter dataset would index off
    the end; clamping shows its last frame until the reset lands.

    Args:
        frame_list: Frame ids of the loaded dataset, in slider order.
        slider_arg: Slider position, possibly stale or None.

    Returns:
        A position that is a valid index into ``frame_list``, or None when the
        dataset has no frames to point at.
    """
    if frame_list is None or len(frame_list) == 0:
        return None
    if slider_arg is None:
        return 0
    return min(max(int(slider_arg), 0), len(frame_list) - 1)


def filter_all(
    data: pd.DataFrame,
    num_list: List[str],
    num_values: List[Tuple[float, float]],
    cat_list: List[str],
    cat_values: List[List[str]],
    visible_table: Optional[pd.DataFrame] = None,
    visible_list: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Filter DataFrame based on numerical and categorical conditions.

    Args:
        data: Input DataFrame to filter.
        num_list: List of numerical column names to filter on.
        num_values: List of (min, max) tuples defining ranges for numerical filters.
        cat_list: List of categorical column names to filter on.
        cat_values: List of lists containing allowed values for each categorical column.
        visible_table: Optional DataFrame containing visibility information. Defaults to None.
        visible_list: Optional list of visibility values to filter by. Defaults to None.

    Returns:
        Filtered DataFrame containing only rows that meet all specified conditions.
    """
    # Initialize condition as True for all rows
    condition = np.ones(len(data), dtype=bool)

    # Apply numerical filters using numpy for speed
    for f_idx, f_name in enumerate(num_list):
        if f_name not in data.columns:
            continue

        col = data[f_name].values
        condition &= (col >= num_values[f_idx][0]) & (col <= num_values[f_idx][1])

    # Apply categorical filters using vectorized isin()
    for f_idx, f_name in enumerate(cat_list):
        if f_name not in data.columns:
            continue

        if not cat_values[f_idx]:
            condition[:] = False
            break

        condition &= data[f_name].isin(cat_values[f_idx]).values

    # Apply visibility filter using index alignment
    if visible_list is not None and visible_table is not None:
        if len(visible_list) == 1:
            condition &= (
                visible_table.loc[data.index, "_VIS_"].values == visible_list[0]
            )
        elif not visible_list:
            condition[:] = False

    return data.loc[condition]
