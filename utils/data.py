"""Table Data Loading

The app's one entry point to the radar table. Kept as a wrapper rather than a
re-export so callers stay off :mod:`dataio` internals -- the Parquet read and
the non-finite normalization are that package's business, not theirs.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import List, Optional

import pandas as pd

from dataio.radar_store import load_radar


def load_data(file_list: List[str], file: Optional[str] = None) -> pd.DataFrame:
    """
    Load radar point cloud data from multiple files into a pandas DataFrame.

    Thin wrapper over :func:`dataio.radar_store.load_radar`, which owns the
    Parquet read and non-finite normalization.

    Args:
        file_list: List of file specifications in JSON string format.
        file: Optional single file specification to add to the file list. Defaults to None.

    Returns:
        Combined DataFrame containing data from all specified files.

    Raises:
        ValueError: If an unsupported file type is encountered.
    """
    return load_radar(file_list, file)
