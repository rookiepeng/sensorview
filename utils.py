"""

    Copyright (C) 2019 - PRESENT  Zhengyu Peng
    E-mail: zpeng.me@gmail.com
    Website: https://zpeng.me

    `                      `
    -:.                  -#:
    -//:.              -###:
    -////:.          -#####:
    -/:.://:.      -###++##:
    ..   `://:-  -###+. :##:
           `:/+####+.   :##:
    .::::::::/+###.     :##:
    .////-----+##:    `:###:
     `-//:.   :##:  `:###/.
       `-//:. :##:`:###/.
         `-//:+######/.
           `-/+####/.
             `+##+.
              :##:
              :##:
              :##:
              :##:
              :##:
               .+:

"""

import os
import json

import base64

import pandas as pd

from app_config import EXPIRATION, KEY_TYPES
from app_config import frame_cache


def load_config(json_file):
    """
    Load a configuration file.

    Parameters:
    - json_file (str): The path to the JSON configuration file.

    Returns:
    - dict: The loaded configuration as a dictionary.
    """
    with open(json_file, "r", encoding="utf-8") as read_file:
        return json.load(read_file)


def save_config(json_dict, json_file):
    """
    Save configuration file.

    Parameters:
    - json_dict (dict): Python dict
    - json_file (str): The path to the JSON configuration file.
    """
    with open(json_file, "w+", encoding="utf-8") as write_file:
        json.dump(json_dict, write_file, indent=4)


def load_data(file_list, file=None):
    """
    Load data from file(s).

    Parameters:
    - file (str): The selected file.
    - file_list (list): The list of selected files.

    Returns:
    - pd.DataFrame: The loaded data.
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

        data_list.append(new_data)

    data = pd.concat(data_list)
    return data.reset_index(drop=True)


def load_image(img_path):
    """
    Load an image from a file.

    Parameters:
    - img_path (str): The path to the image file.

    Returns:
    - str: The base64-encoded image data.
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
    config,
    frame_list,
    c_key,
    num_keys,
    num_values,
    slider_arg=0,
):
    """
    Prepare keyword arguments for creating a 3D scatter plot figure.

    Parameters:
    - config (dict): The configuration dictionary.
    - frame_list (np.ndarray): The list of frame values.
    - c_key (str): The selected color key.
    - num_keys (list): The list of numerical keys.
    - num_values (list): The list of numerical values.
    - slider_arg (int, optional): The index of the slider argument. Defaults to 0.

    Returns:
    - dict: The figure keyword arguments.
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


def cache_set(data, id_str, key_major, key_minor=None):
    """
    Set data in the cache.

    Parameters:
    - data (any): The data to be cached.
    - id_str (str): A unique identifier string.
    - key_major (str): The major cache key.
    - key_minor (str, optional): The minor cache key. Defaults to None.
    """
    if key_minor is None:
        key_str = key_major + id_str
    else:
        key_str = key_major + id_str + key_minor

    frame_cache.set(key_str, data, expire=EXPIRATION)


def cache_expire():
    """
    Expire all items in the cache.
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


def cache_get(id_str, key_major, key_minor=None):
    """
    Get data from the cache.

    Parameters:
    - id_str (str): A unique identifier string.
    - key_major (str): The major cache key.
    - key_minor (str, optional): The minor cache key. Defaults to None.

    Returns:
    - any: The cached data, or None if not found.
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
    data,
    num_list,
    num_values,
    cat_list,
    cat_values,
    visible_table=None,
    visible_list=None,
):
    """
    Filter data based on numerical and categorical conditions.

    Parameters:
    - data (pd.DataFrame): The data to be filtered.
    - num_list (list): The list of numerical columns to filter on.
    - num_values (list): The list of numerical filter values.
    - cat_list (list): The list of categorical columns to filter on.
    - cat_values (list): The list of categorical filter values.
    - visible_table (pd.DataFrame, optional): The visible table. Defaults to None.
    - visible_list (list, optional): The list of visible values. Defaults to None.

    Returns:
    - pd.DataFrame: The filtered data.
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
