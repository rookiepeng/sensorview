"""SensorView Settings and Shared Resources

What every other module reads: the constants, the cache configuration, the
dropdown output groups the views wire themselves to -- and the ``dash.Dash``
instance itself, which lives here rather than in :mod:`dash_app` so that a callback
module can take the app without importing the thing that registers it.

Nothing here starts a server or touches a dataset, which is what makes it safe
for a spawned background-callback worker to import.

Usage:
    from settings import app
    from settings import APP_TITLE, DATA_PATH, CACHE_KEYS

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

import os

import dash
from dash import DiskcacheManager
from dash.dependencies import Output, State

import multiprocess
import psutil

# import redis
from diskcache import FanoutCache

# Background callbacks run in a worker process that Dash's DiskcacheManager
# creates through `multiprocess`. On POSIX that defaults to fork, which copies
# only the calling thread -- and this server is threaded, so a worker inherits
# every lock and thread pool of a live, busy process without the threads that
# would release them.
#
# Polars is the one that bites: its rayon pool has no workers on the far side of
# a fork, so the first `collect()` in the worker blocks forever on threads that
# do not exist. A dataset load is nothing but `collect()`, so it hangs -- but
# only once something has already used Polars in the server process, which is
# why reading frames the buffer had not reached yet (a high slider position) was
# what made the next load hang.
#
# Spawn starts the worker from a clean interpreter instead. It is what Windows
# has always used here, so this makes the platforms behave alike rather than
# introducing anything new; the cost is the worker importing what it needs.
if multiprocess.get_start_method(allow_none=True) is None:
    multiprocess.set_start_method("spawn")


class SafeDiskcacheManager(DiskcacheManager):
    """DiskcacheManager that silently ignores already-terminated processes on cancel.

    It also drops whatever sits at a job's result key before that job starts.
    Dash keys a background callback's result by the hash of its argument values,
    and a result is meant to be read once: the browser polls for it and the read
    deletes it. A job whose poll chain stops early never performs that read --
    the renderer supersedes a running job as soon as one of its inputs changes
    again, and the superseded job can still finish and write its result before
    the kill reaches it -- so the entry is left behind under that key.

    Nothing ages those leftovers out, and the next invocation whose arguments
    hash to the same key is served one instead of running: Dash finds a result
    already sitting at the key, returns it and terminates the job it just
    started. Picking x/y/c back and forth on a 2D scatter is exactly that case,
    since every other argument stays put, so the key repeats as soon as a
    combination is revisited. When the leftover is a real figure the plot merely
    shows a recomputation of the same inputs; when it is the `no_update` that a
    PreventUpdate stored (the frame was not buffered yet when that job ran), the
    figure silently does not update at all.
    """

    def terminate_job(self, job):
        try:
            super().terminate_job(job)
        except psutil.NoSuchProcess:
            pass

    def call_job_fn(self, key, job_fn, args, context):
        self.clear_cache_entry(key)
        self.clear_cache_entry(self._make_progress_key(key))
        self.clear_cache_entry(self._make_set_props_key(key))
        return super().call_job_fn(key, job_fn, args, context)


APP_TITLE = "SensorView"
APP_VERSION = "v12.5"

DATA_PATH = "./data"
FRAME_CACHE_PATH = "./cache/frame"
DASH_CACHE_PATH = "./cache/dash"
# Transcoded copies of camera recordings a browser cannot play natively. Kept
# out of the case folder so the dataset directory stays read-only input.
VIDEO_CACHE_PATH = "./cache/video"
THEME = "dbc"

EXPIRATION = 172800  # 2 days in seconds
CACHE_KEYS = {
    "dataset": "DATASET",
    "frame_list": "FRAME_LIST",
    "frame_data": "FRAME_DATA",
    # Dataset manifest (info.json v2): declares the table/cloud/curve/image
    # stores every view resolves its per-frame data through.
    "manifest": "MANIFEST",
    # Current log: the stem its sidecars are keyed on, plus which log owns each
    # slider position once several are combined.
    "log_info": "LOG_INFO",
    # Per-(log, plot) threshold y range, estimated once so the axis stays
    # fixed while scrubbing instead of autoscaling every frame.
    "curve_range": "CURVE_RANGE",
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

dash_cache = FanoutCache(DASH_CACHE_PATH, timeout=120, shards=4, eviction_policy="none")
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

# The reference pickers map the columns of a log's `.reference.parquet` sidecar
# -- the only thing that places a reference -- so they list that file's columns,
# and the panel hides them for a log that has none.
DROPDOWN_OPTIONS_3D_XYZ_REF = [
    Output("frame-ref-picker-3d", "options"),
    Output("x-ref-picker-3d", "options"),
    Output("y-ref-picker-3d", "options"),
    Output("z-ref-picker-3d", "options"),
    Output("yaw-ref-picker-3d", "options"),
    Output("pitch-ref-picker-3d", "options"),
    Output("roll-ref-picker-3d", "options"),
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
    Output("frame-ref-picker-3d", "value"),
    Output("x-ref-picker-3d", "value"),
    Output("y-ref-picker-3d", "value"),
    Output("z-ref-picker-3d", "value"),
    Output("yaw-ref-picker-3d", "value"),
    Output("pitch-ref-picker-3d", "value"),
    Output("roll-ref-picker-3d", "value"),
]

# Sidecar fields the reference pickers map, in the order the panel shows them:
# the frame key that pairs the file with the table, then the pose it carries.
# Both lists above are indexed positionally against this, so the three orders
# have to be changed together.
REFERENCE_PICKER_ORDER = ("frame", "x", "y", "z", "yaw", "pitch", "roll")

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

# Radar point cloud format offered in the file picker. Sidecars (.h5/.mp4) sit
# beside their log rather than in subfolders, so they are excluded by extension
# rather than by folder.
RADAR_FILE_EXTENSIONS = (".parquet",)
