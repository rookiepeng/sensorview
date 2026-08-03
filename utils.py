"""Utility Functions for SensorView

Common utility functions for data handling, caching, and visualization preparation
including configuration management, cache operations, data processing, and filtering.

Key functions: load_config(), save_config(), load_data(), cache_set(), cache_get(),
filter_all(), and prepare_figure_kwargs().

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Dict, List, Optional, Any, Tuple, Union

import json
import base64
import pandas as pd
import numpy as np

from app_config import EXPIRATION, KEY_TYPES
from app_config import frame_cache

from dataio.radar_store import load_radar


def load_config(json_file: str) -> Dict[str, Any]:
    """
    Load a configuration file from JSON format.

    Args:
        json_file: Path to the JSON configuration file.

    Returns:
        Dictionary containing the configuration data.
    """
    with open(json_file, "r", encoding="utf-8") as read_file:
        return json.load(read_file)


def save_config(json_dict: Dict[str, Any], json_file: str) -> None:
    """
    Save configuration data to a JSON file.

    Args:
        json_dict: Dictionary containing configuration data to save.
        json_file: Path where the JSON file will be saved.
    """
    with open(json_file, "w+", encoding="utf-8") as write_file:
        json.dump(json_dict, write_file, indent=4)


def load_data(file_list: List[str], file: Optional[str] = None) -> pd.DataFrame:
    """
    Load radar point cloud data from multiple files into a pandas DataFrame.

    Thin wrapper over :func:`dataio.radar_store.load_radar`, which owns format
    handling (Parquet, plus legacy CSV/pickle) and non-finite normalization.

    Args:
        file_list: List of file specifications in JSON string format.
        file: Optional single file specification to add to the file list. Defaults to None.

    Returns:
        Combined DataFrame containing data from all specified files.

    Raises:
        ValueError: If an unsupported file type is encountered.
    """
    return load_radar(file_list, file)


def load_image(img_path: str) -> Optional[str]:
    """
    Load and encode an image file to base64 format.

    Args:
        img_path: Path to the image file.

    Returns:
        Base64 encoded image string with data URI scheme prefix, or None if file cannot be loaded.

    Note:
        Returns None for FileNotFoundError, NotADirectoryError, or other IO errors.
    """
    try:
        with open(img_path, "rb") as img_file:
            encoding = base64.b64encode(img_file.read())
        img = "data:image/jpeg;base64," + encoding.decode()
    except FileNotFoundError:
        img = None
    except NotADirectoryError:
        img = None

    return img


def prepare_figure_kwargs(
    config: Dict[str, Any],
    # Data parameters
    num_keys: List[str],
    num_values: List[Tuple[float, float]],
    # Color and visualization parameters
    c_key: str,
    size_vary: bool,
    # Animation parameters
    frame_list: Union[List[float], "np.ndarray"],
    slider_arg: int = 0,
) -> Dict[str, Any]:
    """
    Prepare keyword arguments for creating a 3D scatter plot figure.

    Args:
        config: Configuration dictionary containing plot settings and key definitions.
        num_keys: List of numerical column names.
        num_values: List of (min, max) tuples for numerical value ranges.
        c_key: Column name for color mapping.
        size_vary: Whether to vary marker sizes based on groups.
        frame_list: List or array of frame values for animation.
        slider_arg: Current slider position index. Defaults to 0.

    Returns:
        Dictionary containing all necessary keyword arguments for plotting.
    """
    keys_dict = config["keys"]

    def normalize_ref_value(value: Optional[str]) -> Optional[str]:
        """Convert string 'None' to actual None value."""
        return None if value == "None" else value

    def get_axis_range(key: str, ref_key: Optional[str] = None) -> List[float]:
        """Calculate axis range considering reference key if provided."""
        key_idx = num_keys.index(key)
        base_range = [num_values[key_idx][0], num_values[key_idx][1]]

        if ref_key is not None:
            ref_idx = num_keys.index(ref_key)
            ref_range = [num_values[ref_idx][0], num_values[ref_idx][1]]
            return [min(base_range[0], ref_range[0]), max(base_range[1], ref_range[1])]
        return base_range

    # Initialize figure kwargs with basic settings
    fig_kwargs = {
        "image": None,
        "ref_name": "Host Vehicle",
        "size_vary": size_vary,
    }

    # Setup axis keys and labels
    x_key = config.get("x_3d", num_keys[0])
    y_key = config.get("y_3d", num_keys[1])
    z_key = config.get("z_3d", num_keys[2])

    fig_kwargs.update(
        {
            "x_key": x_key,
            "x_label": keys_dict[x_key].get("description", x_key),
            "y_key": y_key,
            "y_label": keys_dict[y_key].get("description", y_key),
            "z_key": z_key,
            "z_label": keys_dict[z_key].get("description", z_key),
        }
    )

    # Setup color mapping
    fig_kwargs.update(
        {
            "c_key": c_key,
            "c_label": keys_dict[c_key].get("description", c_key),
            "c_type": keys_dict[c_key].get("type", KEY_TYPES["NUM"]),
        }
    )

    # Setup reference points
    x_ref = normalize_ref_value(config.get("x_ref"))
    y_ref = normalize_ref_value(config.get("y_ref"))
    z_ref = normalize_ref_value(config.get("z_ref"))

    fig_kwargs.update(
        {
            "x_ref": x_ref,
            "y_ref": y_ref,
            "z_ref": z_ref,
        }
    )

    # Calculate axis ranges
    fig_kwargs.update(
        {
            "x_range": get_axis_range(x_key, x_ref if x_ref and y_ref else None),
            "y_range": get_axis_range(y_key, y_ref if x_ref and y_ref else None),
            "z_range": get_axis_range(z_key, z_ref),
        }
    )

    # Setup color range
    if fig_kwargs["c_type"] == KEY_TYPES["NUM"]:
        c_idx = num_keys.index(c_key)
        fig_kwargs["c_range"] = [num_values[c_idx][0], num_values[c_idx][1]]
    else:
        fig_kwargs["c_range"] = [0, 0]

    # Setup plot name/title
    slider_label = keys_dict[config["slider"]]["description"]
    fig_kwargs["name"] = (
        f"Index: {slider_arg} ({slider_label}: {frame_list[slider_arg]})"
    )

    return fig_kwargs


def cache_set(
    data: Any, id_str: str, key_major: str, key_minor: Optional[str] = None
) -> None:
    """
    Store data in the cache with expiration time.

    Args:
        data: Data to be cached (any type).
        id_str: Unique identifier string for the cache entry.
        key_major: Primary key component for cache entry.
        key_minor: Optional secondary key component for cache entry. Defaults to None.
    """
    if key_minor is None:
        key_str = key_major + id_str
    else:
        key_str = key_major + id_str + key_minor

    frame_cache.set(key_str, data, expire=EXPIRATION)


def cache_expire() -> None:
    """
    Expire all items in the cache immediately.
    """
    frame_cache.expire()


# def redis_set(data, id_str, key_major, key_minor=None):
#     """
#     Set data in Redis.

#     Parameters:
#     - data (any): The data to be stored in Redis.
#     - id_str (str): A unique identifier string.
#     - key_major (str): The major Redis key.
#     - key_minor (str, optional): The minor Redis key. Defaults to None.
#     """
#     if key_minor is None:
#         key_str = key_major + id_str
#     else:
#         key_str = key_major + id_str + key_minor

#     redis_instance.set(key_str, pickle.dumps(data), ex=EXPIRATION)


def cache_get(
    id_str: str, key_major: str, key_minor: Optional[str] = None
) -> Optional[Any]:
    """
    Retrieve data from the cache.

    Args:
        id_str: Unique identifier string for the cache entry.
        key_major: Primary key component for cache entry.
        key_minor: Optional secondary key component for cache entry. Defaults to None.

    Returns:
        Cached data if found, None otherwise.
    """
    if key_minor is None:
        key_str = key_major + id_str
    else:
        key_str = key_major + id_str + key_minor

    val = frame_cache.get(key_str, default=None, retry=True)
    return val


# def redis_get(id_str, key_major, key_minor=None):
#     """
#     Get data from Redis.

#     Parameters:
#     - id_str (str): A unique identifier string.
#     - key_major (str): The major Redis key.
#     - key_minor (str, optional): The minor Redis key. Defaults to None.

#     Returns:
#     - any: The retrieved data, or None if not found.
#     """
#     if key_minor is None:
#         key_str = key_major + id_str
#     else:
#         key_str = key_major + id_str + key_minor

#     val = redis_instance.get(key_str)

#     if val is not None:
#         return pickle.loads(val)

#     return None


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
