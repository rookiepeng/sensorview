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

from dash import DiskcacheManager
from dash.dependencies import Output, State

import redis
from diskcache import Cache


APP_TITLE = "SensorView"

DATA_PATH = "./data"
FRAME_CACHE_PATH = "./cache/frame"
DASH_CACHE_PATH = "./cache/dash"

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

frame_cache = Cache(FRAME_CACHE_PATH, timeout=120, eviction_policy="none")

dash_cache = Cache(DASH_CACHE_PATH, timeout=120, eviction_policy="none")
background_callback_manager = DiskcacheManager(dash_cache)

# options for dropdown components with all the keys
DROPDOWN_OPTIONS_ALL = [
    Output("c-picker-3d", "options"),
    Output("x-picker-2d-left", "options"),
    Output("y-picker-2d-left", "options"),
    Output("c-picker-2d-left", "options"),
    Output("x-picker-2d-right", "options"),
    Output("y-picker-2d-right", "options"),
    Output("c-picker-2d-right", "options"),
    Output("x-picker-histogram", "options"),
    Output("x-picker-heatmap", "options"),
    Output("y-picker-heatmap", "options"),
    Output("y-picker-violin", "options"),
]

# values for dropdown components with all the keys
DROPDOWN_VALUES_ALL = [
    Output("c-picker-3d", "value"),
    Output("x-picker-2d-left", "value"),
    Output("y-picker-2d-left", "value"),
    Output("c-picker-2d-left", "value"),
    Output("x-picker-2d-right", "value"),
    Output("y-picker-2d-right", "value"),
    Output("c-picker-2d-right", "value"),
    Output("x-picker-histogram", "value"),
    Output("x-picker-heatmap", "value"),
    Output("y-picker-heatmap", "value"),
    Output("y-picker-violin", "value"),
]

DROPDOWN_VALUES_ALL_STATE = [
    State("c-picker-3d", "value"),
    State("x-picker-2d-left", "value"),
    State("y-picker-2d-left", "value"),
    State("c-picker-2d-left", "value"),
    State("x-picker-2d-right", "value"),
    State("y-picker-2d-right", "value"),
    State("c-picker-2d-right", "value"),
    State("x-picker-histogram", "value"),
    State("x-picker-heatmap", "value"),
    State("y-picker-heatmap", "value"),
    State("y-picker-violin", "value"),
]

# options for dropdown components with categorical keys
DROPDOWN_OPTIONS_CAT = [
    Output("x-picker-violin", "options"),
]

# values for dropdown components with categorical keys
DROPDOWN_VALUES_CAT = [
    Output("x-picker-violin", "value"),
]

# options for dropdown components with categorical keys and `None`
# for color dropdown components
DROPDOWN_OPTIONS_CAT_COLOR = [
    Output("c-picker-histogram", "options"),
    Output("c-picker-violin", "options"),
    Output("c-picker-parallel", "options"),
]

# values for dropdown components with categorical keys and `None`
# for color dropdown components
DROPDOWN_VALUES_CAT_COLOR = [
    Output("c-picker-histogram", "value"),
    Output("c-picker-violin", "value"),
    Output("c-picker-parallel", "value"),
]

""" Global Variables """
REDIS_HASH_NAME = os.environ.get("DASH_APP_NAME", APP_TITLE)
SPECIAL_FOLDERS = ["images"]
