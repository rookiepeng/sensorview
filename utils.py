"""Utility Functions for SensorView

This module provides common utility functions used throughout the SensorView
application for data handling, caching, and visualization preparation.

Core Functionalities:
-------------------
1. Configuration Management:
   - JSON configuration loading/saving
   - Data file handling
   - Image processing

2. Cache Operations:
   - Data caching implementation
   - Cache key management
   - Expiration handling

3. Data Processing:
   - DataFrame filtering
   - Numerical/categorical data handling
   - Figure parameter preparation

Key Components:
-------------
- Configuration file operations
- Data loading and preprocessing
- Cache management
- Image encoding
- Data filtering
- Figure parameter preparation

Usage:
------
Imported by other modules for:
- Data management
- Cache operations
- Configuration handling
- Visualization preparation

Dependencies:
------------
- pandas
- numpy
- json
- base64
- custom configuration (app_config)

Author: Zhengyu Peng
Email: zpeng.me@gmail.com
Website: https://zpeng.me
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

import os
from typing import Dict, List, Optional, Any, Tuple

import json
import base64
import pandas as pd

from app_config import EXPIRATION, KEY_TYPES
from app_config import frame_cache


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
    Load data from multiple files into a pandas DataFrame.

    Args:
        file_list: List of file specifications in JSON string format.
        file: Optional single file to add to the file list.

    Returns:
        Combined DataFrame containing data from all specified files.
    """
    if file is not None and file not in file_list:
        file_list.append(file)

    data_list = []
    for _, f_dict in enumerate(file_list):
        file = json.loads(f_dict)

        if file["name"].endswith(".pkl"):
            new_data = pd.read_pickle(os.path.join(file["path"], file["name"]))
            # new_data = new_data.reset_index(drop=True)

        elif file["name"].endswith(".csv"):
            new_data = pd.read_csv(
                os.path.join(file["path"], file["name"]), engine="pyarrow"
            )
        else:
            raise ValueError(f"Unsupported file type: {file['name']}")

        data_list.append(new_data)

    data = pd.concat(data_list)
    return data.reset_index(drop=True)


def load_image(img_path: str) -> Optional[str]:
    """
    Load and encode an image file to base64 format.

    Args:
        img_path: Path to the image file.

    Returns:
        Base64 encoded image string with data URI scheme prefix, or None if file not found.
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
    frame_list: List[float],
    c_key: str,
    num_keys: List[str],
    num_values: List[Tuple[float, float]],
    slider_arg: int = 0,
) -> Dict[str, Any]:
    """
    Prepare keyword arguments for creating a 3D scatter plot figure.

    Args:
        config: Configuration dictionary containing plot settings.
        frame_list: List of frame values for animation.
        c_key: Key for color mapping.
        num_keys: List of numerical column names.
        num_values: List of (min, max) tuples for numerical values.
        slider_arg: Current slider position index.

    Returns:
        Dictionary containing all necessary arguments for plotting.
    """
    keys_dict = config["keys"]
    # prepare figure key word arguments
    fig_kwargs = {}
    fig_kwargs["image"] = None

    fig_kwargs["x_key"] = config.get("x_3d", num_keys[0])
    fig_kwargs["x_label"] = keys_dict[fig_kwargs["x_key"]].get(
        "description", fig_kwargs["x_key"]
    )
    fig_kwargs["y_key"] = config.get("y_3d", num_keys[1])
    fig_kwargs["y_label"] = keys_dict[fig_kwargs["y_key"]].get(
        "description", fig_kwargs["y_key"]
    )
    fig_kwargs["z_key"] = config.get("z_3d", num_keys[2])
    fig_kwargs["z_label"] = keys_dict[fig_kwargs["z_key"]].get(
        "description", fig_kwargs["z_key"]
    )
    fig_kwargs["c_key"] = c_key
    fig_kwargs["c_label"] = keys_dict[fig_kwargs["c_key"]].get(
        "description", fig_kwargs["c_key"]
    )
    fig_kwargs["x_ref"] = config.get("x_ref", None)
    fig_kwargs["y_ref"] = config.get("y_ref", None)

    # set graph's range the same for all the frames
    if (fig_kwargs["x_ref"] is not None) and (fig_kwargs["y_ref"] is not None):
        fig_kwargs["x_range"] = [
            min(
                [
                    num_values[num_keys.index(fig_kwargs["x_key"])][0],
                    num_values[num_keys.index(fig_kwargs["x_ref"])][0],
                ]
            ),
            max(
                [
                    num_values[num_keys.index(fig_kwargs["x_key"])][1],
                    num_values[num_keys.index(fig_kwargs["x_ref"])][1],
                ]
            ),
        ]
        fig_kwargs["y_range"] = [
            min(
                [
                    num_values[num_keys.index(fig_kwargs["y_key"])][0],
                    num_values[num_keys.index(fig_kwargs["y_ref"])][0],
                ]
            ),
            max(
                [
                    num_values[num_keys.index(fig_kwargs["y_key"])][1],
                    num_values[num_keys.index(fig_kwargs["y_ref"])][1],
                ]
            ),
        ]
    else:
        fig_kwargs["x_range"] = [
            num_values[num_keys.index(fig_kwargs["x_key"])][0],
            num_values[num_keys.index(fig_kwargs["x_key"])][1],
        ]
        fig_kwargs["y_range"] = [
            num_values[num_keys.index(fig_kwargs["y_key"])][0],
            num_values[num_keys.index(fig_kwargs["y_key"])][1],
        ]
    fig_kwargs["z_range"] = [
        num_values[num_keys.index(fig_kwargs["z_key"])][0],
        num_values[num_keys.index(fig_kwargs["z_key"])][1],
    ]

    if keys_dict[c_key].get("type", KEY_TYPES["NUM"]) == KEY_TYPES["NUM"]:
        fig_kwargs["c_range"] = [
            num_values[num_keys.index(c_key)][0],
            num_values[num_keys.index(c_key)][1],
        ]
    else:
        fig_kwargs["c_range"] = [0, 0]

    slider_label = keys_dict[config["slider"]]["description"]
    fig_kwargs["name"] = (
        "Index: "
        + str(slider_arg)
        + " ("
        + slider_label
        + ": "
        + str(frame_list[slider_arg])
        + ")"
    )

    fig_kwargs["c_type"] = keys_dict[c_key].get("type", KEY_TYPES["NUM"])
    fig_kwargs["ref_name"] = "Host Vehicle"

    return fig_kwargs


def cache_set(
    data: Any, id_str: str, key_major: str, key_minor: Optional[str] = None
) -> None:
    """
    Store data in the cache with expiration time.

    Args:
        data: Data to be cached.
        id_str: Unique identifier string.
        key_major: Primary key for cache entry.
        key_minor: Optional secondary key for cache entry.
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
        id_str: Unique identifier string.
        key_major: Primary key for cache entry.
        key_minor: Optional secondary key for cache entry.

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
        num_list: List of numerical column names.
        num_values: List of (min, max) ranges for numerical filters.
        cat_list: List of categorical column names.
        cat_values: List of lists containing allowed values for each categorical column.
        visible_table: Optional DataFrame containing visibility information.
        visible_list: Optional list of visibility values to filter by.

    Returns:
        Filtered DataFrame meeting all specified conditions.
    """
    for f_idx, f_name in enumerate(num_list):
        if f_name not in data.columns:
            continue

        if f_idx == 0:
            condition = (data[f_name] >= num_values[f_idx][0]) & (
                data[f_name] <= num_values[f_idx][1]
            )
        else:
            condition = (
                condition
                & (data[f_name] >= num_values[f_idx][0])
                & (data[f_name] <= num_values[f_idx][1])
            )

    for f_idx, f_name in enumerate(cat_list):
        if f_name not in data.columns:
            continue

        if not cat_values[f_idx]:
            condition = condition & False
            break

        for val_idx, val in enumerate(cat_values[f_idx]):
            if val_idx == 0:
                val_condition = data[f_name] == val
            else:
                val_condition = val_condition | (data[f_name] == val)

        condition = condition & val_condition

    if len(visible_list) == 1:
        condition = condition & (visible_table["_VIS_"] == visible_list[0])
    elif not visible_list:
        condition = condition & False

    return data.loc[condition]
