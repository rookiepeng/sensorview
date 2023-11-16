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
import pickle
import base64

import redis
from diskcache import Cache
from dash import DiskcacheManager

import pandas as pd


EXPIRATION = 172800  # 2 days in seconds
CACHE_KEYS = {
    "dataset": "DATASET",
    "frame_list": "FRAME_LIST",
    "frame_data": "FRAME_DATA",
    "visible_table": "VIS_TABLE",
    "config": "CONFIG",
    "figure_idx": "FIGURE_IDX",
    "figure": "FIGURE",
    "hover": "HOVER",
    "figure_ref": "FIGURE_REF",
    "figure_layout": "FIGURE_LAYOUT",
    "task_id": "TASK_ID",
    "filter_kwargs": "FILTGER_KWARGS",
    "selected_data": "SELECTED_DATA",
}
KEY_TYPES = {"CAT": "categorical", "NUM": "numerical"}

redis_ip = os.environ.get("REDIS_SERVER_SERVICE_HOST", "127.0.0.1")
redis_url = "redis://" + redis_ip + ":6379"
redis_instance = redis.StrictRedis.from_url(redis_url)

frame_cache = Cache("./cache/frame", timeout=120, eviction_policy="none")

dash_cache = Cache("./cache/dash", timeout=120, eviction_policy="none")
background_callback_manager = DiskcacheManager(dash_cache)


def load_config(json_file):
    """
    Load config json file

    :param str json_file
        json file path

    :return: configuration struct
    :rtype: dict
    """
    with open(json_file, "r", encoding="utf-8") as read_file:
        return json.load(read_file)


def load_data(file, file_list, case):
    """_summary_

    :param file: _description_
    :type file: _type_
    :param file_list: _description_
    :type file_list: _type_
    :param case: _description_
    :type case: _type_
    :return: _description_
    :rtype: _type_
    """
    if file not in file_list:
        file_list.append(file)

    data_list = []
    for _, f_dict in enumerate(file_list):
        file = json.loads(f_dict)
        data_list.append(
            pd.read_feather(
                "./data/" + case + file["path"] + "/" + file["feather_name"]
            )
        )

    data = pd.concat(data_list)
    return data.reset_index(drop=True)


def load_data_list(file_list, case):
    """_summary_

    :param file_list: _description_
    :type file_list: _type_
    :param case: _description_
    :type case: _type_
    :return: _description_
    :rtype: _type_
    """
    data_list = []
    for _, f_dict in enumerate(file_list):
        file = json.loads(f_dict)
        data_list.append(
            pd.read_feather(
                "./data/" + case + file["path"] + "/" + file["feather_name"]
            )
        )

    data = pd.concat(data_list)
    return data.reset_index(drop=True)


def load_image(img_path):
    """_summary_

    :param img_path: _description_
    :type img_path: _type_
    :return: _description_
    :rtype: _type_
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
    """_summary_

    :param config: _description_
    :type config: _type_
    :param frame_list: _description_
    :type frame_list: _type_
    :param c_key: _description_
    :type c_key: _type_
    :param num_keys: _description_
    :type num_keys: _type_
    :param num_values: _description_
    :type num_values: _type_
    :param slider_arg: _description_, defaults to 0
    :type slider_arg: int, optional
    :return: _description_
    :rtype: _type_
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
    Set data to Redis

    :param dict/str/pandas.Dataframe data
        data to be stored in Redis
    :param str id_str
        unique id (session id)
    :param str key_major
        major key name
    :param str key_minor=None
        minor key name
    """
    if key_minor is None:
        key_str = key_major + id_str
    else:
        key_str = key_major + id_str + key_minor

    frame_cache.set(key_str, data, expire=EXPIRATION)


def cache_expire():
    """_summary_"""
    frame_cache.expire()


def redis_set(data, id_str, key_major, key_minor=None):
    """
    Set data to Redis

    :param dict/str/pandas.Dataframe data
        data to be stored in Redis
    :param str id_str
        unique id (session id)
    :param str key_major
        major key name
    :param str key_minor=None
        minor key name
    """
    if key_minor is None:
        key_str = key_major + id_str
    else:
        key_str = key_major + id_str + key_minor

    redis_instance.set(key_str, pickle.dumps(data), ex=EXPIRATION)


def cache_get(id_str, key_major, key_minor=None):
    """
    Get data from Redis

    :param str id_str
        unique id (session id)
    :param str key_major
        major key name
    :param str key_minor=None
        minor key name

    :return: data in Redis
    :rtype: dict/str/pandas.Dataframe
    """
    if key_minor is None:
        key_str = key_major + id_str
    else:
        key_str = key_major + id_str + key_minor

    val = frame_cache.get(key_str, default=None, retry=True)
    return val


def redis_get(id_str, key_major, key_minor=None):
    """
    Get data from Redis

    :param str id_str
        unique id (session id)
    :param str key_major
        major key name
    :param str key_minor=None
        minor key name

    :return: data in Redis
    :rtype: dict/str/pandas.Dataframe
    """
    if key_minor is None:
        key_str = key_major + id_str
    else:
        key_str = key_major + id_str + key_minor

    val = redis_instance.get(key_str)

    if val is not None:
        return pickle.loads(val)
    else:
        return None


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
    Filter the DataFrame

    :param pandas.DataFrame data
        initial data table
    :param [str] num_list
        list of numerical keys
    :param [list] num_values
        numberical value ranges
    :param [str] cat_list
        list of categorical keys
    :param [list] cat_values
        categorical item lists
    :param pandas.DataFrame visible_table=None
        visibility table
    :param [str] visible_list=None
        visibility list

    :return: filtered data table
    :rtype: pandas.DataFrame
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
        else:
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
