"""SensorView Configuration Module

Core configuration settings, constants, and shared resources for the SensorView
application including app settings, cache configuration, and UI component mappings.

Usage:
    from app_config import APP_TITLE, DATA_PATH, CACHE_KEYS

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

import os

import dash
from dash import DiskcacheManager
from dash.dependencies import Output, State

import psutil

# import redis
from diskcache import FanoutCache


class SafeDiskcacheManager(DiskcacheManager):
    """DiskcacheManager that silently ignores already-terminated processes on cancel."""

    def terminate_job(self, job):
        try:
            super().terminate_job(job)
        except psutil.NoSuchProcess:
            pass


APP_TITLE = "SensorView"
APP_VERSION = "v11.8"

DATA_PATH = "./data"
FRAME_CACHE_PATH = "./cache/frame"
DASH_CACHE_PATH = "./cache/dash"
THEME = "dbc"

EXPIRATION = 172800  # 2 days in seconds
CACHE_KEYS = {
    "dataset": "DATASET",
    "frame_list": "FRAME_LIST",
    "frame_data": "FRAME_DATA",
    # Dataset manifest (info.json v2): declares the radar/lidar/threshold/camera
    # stores and the frame_id <-> timestamp map every view synchronizes on.
    "manifest": "MANIFEST",
    # Current log: the stem its sidecars are keyed on, plus the frame timestamps
    # and capture rate derived from that log's Parquet data.
    "log_info": "LOG_INFO",
    # Per-(log, plot) threshold y range, estimated once so the axis stays
    # fixed while scrubbing instead of autoscaling every frame.
    "threshold_range": "THRESHOLD_RANGE",
    "visible_table": "VIS_TABLE",
    "config": "CONFIG",
    "figure_idx": "FIGURE_IDX",
    "figure_bundle": "FIGURE_BUNDLE",
    "filter_kwargs": "FILTGER_KWARGS",
    "selected_data_left": "SELECTED_DATA_LEFT",
    "selected_data_right": "SELECTED_DATA_RIGHT",
    # Used for cooperative cancellation: newest task stores its trigger_idx
    # here so older tasks can detect they've been superseded and abort.
    "active_task_id": "ACTIVE_TASK_ID",
}
KEY_TYPES = {"CAT": "categorical", "NUM": "numerical"}

# redis_ip = os.environ.get("REDIS_SERVER_SERVICE_HOST", "127.0.0.1")
# redis_url = "redis://" + redis_ip + ":6379"
# redis_instance = redis.StrictRedis.from_url(redis_url)

frame_cache = FanoutCache(
    FRAME_CACHE_PATH, timeout=120, shards=8, eviction_policy="none"
)

dash_cache = FanoutCache(
    DASH_CACHE_PATH, timeout=120, shards=4, eviction_policy="none"
)
background_callback_manager = SafeDiskcacheManager(dash_cache)


app = dash.Dash(
    __name__,
    meta_tags=[{"name": "viewport", "content": "width=device-width,initial-scale=1"}],
)

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

DROPDOWN_OPTIONS_3D_XYZ = [
    Output("slider-picker-3d", "options"),
    Output("x-picker-3d", "options"),
    Output("y-picker-3d", "options"),
    Output("z-picker-3d", "options"),
]

DROPDOWN_OPTIONS_3D_XYZ_REF = [
    Output("x-ref-picker-3d", "options"),
    Output("y-ref-picker-3d", "options"),
    Output("z-ref-picker-3d", "options"),
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

DROPDOWN_VALUES_3D_XYZ = [
    Output("slider-picker-3d", "value"),
    Output("x-picker-3d", "value"),
    Output("y-picker-3d", "value"),
    Output("z-picker-3d", "value"),
]

DROPDOWN_VALUES_3D_XYZ_REF = [
    Output("x-ref-picker-3d", "value"),
    Output("y-ref-picker-3d", "value"),
    Output("z-ref-picker-3d", "value"),
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

# Folders skipped when scanning a case directory for selectable radar tables.
# Sidecars (.h5/.mp4) sit beside their log rather than in subfolders, and are
# excluded by extension rather than by folder.
SPECIAL_FOLDERS = ["images"]

# Radar point cloud formats offered in the file picker. Parquet is the format
# the ingest pipeline produces; CSV and pickle stay supported so pre-existing
# datasets load without conversion.
RADAR_FILE_EXTENSIONS = (".parquet", ".csv", ".pkl")
