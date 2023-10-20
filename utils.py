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

import redis
import os
import json
import pickle
import base64
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

frame_cache = Cache("./cache/frame", eviction_policy="none")

dash_cache = Cache("./cache/dash", eviction_policy="none")
background_callback_manager = DiskcacheManager(dash_cache)


def load_config(json_file):
    """
    Load config json file

    :param str json_file
        json file path

    :return: configuration struct
    :rtype: dict
    """
    with open(json_file, "r") as read_file:
        return json.load(read_file)


def load_data(file, file_list, case):
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
    try:
        encoding = base64.b64encode(open(img_path, "rb").read())
        img = "data:image/jpeg;base64,{}".format(encoding.decode())
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
    keys_dict = config["keys"]
    # prepare figure key word arguments
    fig_kwargs = dict()
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


def cache_set(data, id, key_major, key_minor=None):
    """
    Set data to Redis

    :param dict/str/pandas.Dataframe data
        data to be stored in Redis
    :param str id
        unique id (session id)
    :param str key_major
        major key name
    :param str key_minor=None
        minor key name
    """
    if key_minor is None:
        key_str = key_major + id
    else:
        key_str = key_major + id + key_minor

    frame_cache.set(key_str, data, expire=EXPIRATION)


def redis_set(data, id, key_major, key_minor=None):
    """
    Set data to Redis

    :param dict/str/pandas.Dataframe data
        data to be stored in Redis
    :param str id
        unique id (session id)
    :param str key_major
        major key name
    :param str key_minor=None
        minor key name
    """
    if key_minor is None:
        key_str = key_major + id
    else:
        key_str = key_major + id + key_minor

    redis_instance.set(key_str, pickle.dumps(data), ex=EXPIRATION)


def cache_get(id, key_major, key_minor=None):
    """
    Get data from Redis

    :param str id
        unique id (session id)
    :param str key_major
        major key name
    :param str key_minor=None
        minor key name

    :return: data in Redis
    :rtype: dict/str/pandas.Dataframe
    """
    if key_minor is None:
        key_str = key_major + id
    else:
        key_str = key_major + id + key_minor

    val = frame_cache.get(key_str, default=None, retry=True)
    return val


def redis_get(id, key_major, key_minor=None):
    """
    Get data from Redis

    :param str id
        unique id (session id)
    :param str key_major
        major key name
    :param str key_minor=None
        minor key name

    :return: data in Redis
    :rtype: dict/str/pandas.Dataframe
    """
    if key_minor is None:
        key_str = key_major + id
    else:
        key_str = key_major + id + key_minor

    val = redis_instance.get(key_str)

    if val is not None:
        return pickle.loads(val)
    else:
        return None
