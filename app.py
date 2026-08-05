"""SensorView Application Server

Flask/Dash-based web application for real-time sensor data visualization and analysis
with multiple visualization modes, test case management, and WebWorker-based caching.

Features: 3D/2D scatter plots, heatmaps, histograms, interactive controls, frame
navigation, data filtering, and session-based data isolation.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Dict, List, Any, Optional, Union

import json
import os
import shutil

# from waitress import serve
from multiprocessing import freeze_support

from flaskwebgui import FlaskUI

import orjson
from flask import Response, abort, send_file

import dash
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from utils import load_config, save_config, cache_get

from view_callbacks.test_case_view import get_test_case_view_callbacks
from view_callbacks.control_view import get_control_view_callbacks
from view_callbacks.scatter_3d_view import get_scatter_3d_view_callbacks
from view_callbacks.scatter_3d_view_background import (
    get_scatter_3d_view_background_callbacks,
)
from view_callbacks.scatter_2d_left_view import get_scatter_2d_left_view_callbacks
from view_callbacks.scatter_2d_right_view import get_scatter_2d_right_view_callbacks
from view_callbacks.heatmap_view import get_heatmap_view_callbacks
from view_callbacks.histogram_view import get_histogram_view_callbacks
from view_callbacks.parcats_view import get_parcats_view_callbacks
from view_callbacks.violin_view import get_violin_view_callbacks
from view_callbacks.camera_view import get_camera_view_callbacks
from view_callbacks.threshold_view import get_threshold_view_callbacks

from frame_sources import (
    get_log_stem,
    get_manifest,
    get_cloud_trace,
    playable_image_file,
)

from app_config import app
from app_config import APP_TITLE, DATA_PATH, CACHE_KEYS
from app_config import SPECIAL_FOLDERS, RADAR_FILE_EXTENSIONS

from layouts.app_layout import get_app_layout
from layouts.analysis_dock_layout import DOCK_VIEWS, EMPTY_SLOT

app.scripts.config.serve_locally = True
app.css.config.serve_locally = True
app.title = APP_TITLE
app.layout = get_app_layout


@app.server.route("/api/data/<session>/<start_index_str>", methods=["GET"])
def get_data_by_index(session: str, start_index_str: str) -> Response:
    """
    Retrieve buffered figure data from cache for a specific session.

    Args:
        session: Unique session identifier for data isolation.
        start_index_str: Starting index from which to retrieve data (converted to int).

    Returns:
        JSON response containing:
            - If start_index_str > latest_server_buffer_index: [{"index": -1}]
            - If start_index_str == latest_server_buffer_index: []
            - Otherwise: List of dictionaries with figure data, hover strings,
              reference figures, and layouts for each index.
    """
    latest_server_buffer_index = cache_get(session, CACHE_KEYS["figure_idx"])
    start_index = int(start_index_str)

    if latest_server_buffer_index is None:
        latest_server_buffer_index = -1

    _orjson_opts = orjson.OPT_SERIALIZE_NUMPY

    if start_index > latest_server_buffer_index:
        return Response(
            orjson.dumps([{"index": -1}]),
            mimetype="application/json",
        )

    if start_index == latest_server_buffer_index:
        return Response(orjson.dumps([]), mimetype="application/json")

    # Cap the number of frames returned per request to prevent huge JSON responses
    # that cause browser memory spikes. storeBuffer polls on an interval and will
    # pick up remaining frames in subsequent requests.
    MAX_BATCH_SIZE = 40
    end_index = min(start_index + 1 + MAX_BATCH_SIZE, latest_server_buffer_index + 1)

    buffer = []
    for idx in range(start_index + 1, end_index):
        bundle = cache_get(session, CACHE_KEYS["figure_bundle"], str(idx))
        if bundle is not None:
            buffer.append(
                {
                    "index": idx,
                    "fig": bundle["fig"],
                    "hover_strings": bundle["hover_strings"],
                    "ref_fig": bundle["ref_fig"],
                    "fig_layout": bundle["fig_layout"],
                }
            )

    return Response(
        orjson.dumps(buffer, option=_orjson_opts), mimetype="application/json"
    )


@app.server.route("/api/cloud/<session>/<int:frame_idx>", methods=["GET"])
def get_cloud_frame(session: str, frame_idx: int) -> Response:
    """
    Serve the point-cloud backdrop trace for one frame.

    The cloud is deliberately kept off the IndexedDB figure-buffer path that the
    radar traces use. The buffer pre-fetches a window of frames ahead, and a
    decimated cloud frame is orders of magnitude larger than a table one --
    buffering it would balloon client storage for data that is pure backdrop.
    Instead the client fetches just the frame it is displaying, and caches it.

    Args:
        session: Session identifier used to look up the manifest and frame list.
        frame_idx: Slider position (an index into the frame list, not a frame id).

    Returns:
        JSON ``{"trace": <scatter3d trace>}``, or ``{"trace": null}`` when the
        dataset has no cloud or that frame is missing.
    """
    empty = Response(orjson.dumps({"trace": None}), mimetype="application/json")

    manifest = get_manifest(session)
    stem = get_log_stem(session)
    if manifest is None or not stem or not manifest.has_cloud(stem):
        return empty

    frame_list = cache_get(session, CACHE_KEYS["frame_list"])
    if frame_list is None or frame_idx < 0 or frame_idx >= len(frame_list):
        return empty

    trace = get_cloud_trace(manifest, stem, frame_list[frame_idx])
    if trace is None:
        return empty

    return Response(
        orjson.dumps({"trace": trace}, option=orjson.OPT_SERIALIZE_NUMPY),
        mimetype="application/json",
    )


@app.server.route("/api/camera/<session>/<stream_id>", methods=["GET"])
def get_camera_stream(session: str, stream_id: str):
    """
    Serve a camera mp4 for the browser's video element.

    The file path comes from the session's manifest, never from the URL, so a
    caller cannot walk outside the dataset directory by crafting ``stream_id``.

    Args:
        session: Session identifier used to look up the manifest.
        stream_id: Camera stream identifier declared in the manifest.

    Returns:
        The mp4 file response. ``conditional=True`` enables HTTP Range
        requests, which is what makes ``currentTime`` seeking work at all --
        without it the browser must download the whole clip before it can seek.

        A recording in a container browsers cannot play is transcoded on first
        request and served from the video cache, so this can block for a few
        seconds once per log.
    """
    manifest = get_manifest(session)
    stem = get_log_stem(session)
    if manifest is None or not stem:
        abort(404)

    stream = next(
        (s for s in manifest.image_streams(stem) if s["id"] == stream_id), None
    )
    if stream is None:
        abort(404)

    playable = playable_image_file(stream["file"])
    if playable is None:
        abort(404)

    return send_file(playable, mimetype="video/mp4", conditional=True)


# Initialize worker
app.clientside_callback(
    dash.ClientsideFunction(
        namespace="clientside_callback", function_name="initWorker"
    ),
    Output("worker-status", "data"),
    Input("refresh-button-modal", "n_clicks"),
)

# Store data in IndexedDB via worker
app.clientside_callback(
    dash.ClientsideFunction(
        namespace="clientside_callback", function_name="storeBuffer"
    ),
    [
        Output("buffer-local", "value"),
        Output("worker-status", "data", allow_duplicate=True),
        Output("local-buffer-index", "data", allow_duplicate=True),
    ],
    Input("interval-buffer", "n_intervals"),
    State("local-buffer-index", "data"),
    State("session-id", "data"),
    State("slider-frame", "max"),
    prevent_initial_call=True,
)

# Retrieve data from IndexedDB
app.clientside_callback(
    dash.ClientsideFunction(
        namespace="clientside_callback", function_name="retrieveBuffer"
    ),
    [
        Output("scatter3d", "figure", allow_duplicate=True),
        Output("trigger-remote-figure", "data"),
    ],
    Input("slider-frame", "value"),
    Input("play-stop-button", "n_clicks"),
    Input("decay-slider", "value"),
    State("size-vary-switch", "value"),
    State("session-id", "data"),
    State("interval-component", "disabled"),
    State("colormap-3d", "value"),
    State("c-picker-3d", "value"),
    State("darkmode-switch", "value"),
    State("key-dict", "data"),
    State("dark-template", "data"),
    State("light-template", "data"),
    State("local-buffer-index", "data"),
    State("trigger-remote-figure", "data"),
    prevent_initial_call=True,
)


@app.callback(
    output={
        "data_path": Output("data-path-modal", "value"),
    },
    inputs={"is_modal_open": Input("modal-centered", "is_open")},
)
def on_modal_open(is_modal_open: bool) -> Dict[str, str]:
    """
    Initialize data path when configuration modal is opened.

    Args:
        is_modal_open: Boolean indicating if the modal is currently open.

    Returns:
        Dictionary containing the data path configuration.

    Raises:
        PreventUpdate: If modal is not open to prevent unnecessary updates.
    """
    if not is_modal_open:
        raise PreventUpdate

    if os.path.isfile("./config.json"):
        config = load_config("./config.json")
    else:
        config = {"DATA_PATH": DATA_PATH}
        save_config(config, "./config.json")
    data_path = config.get("DATA_PATH", DATA_PATH)

    if os.path.exists("./temp"):
        shutil.rmtree("./temp")
    os.makedirs("./temp")

    return {
        "data_path": data_path,
    }


@app.callback(
    output={
        "case_options": Output("case-picker-modal", "options"),
        "case_value": Output("case-picker-modal", "value"),
    },
    inputs={
        "data_path": Input("data-path-modal", "value"),
        "unused_refresh": Input("refresh-button-modal", "n_clicks"),
    },
)
def on_path_change(
    data_path: str, unused_refresh: Optional[int]
) -> Dict[str, Union[str, List[Dict[str, str]]]]:
    """
    Update available test cases when data path changes.

    Args:
        data_path: Path to the data directory containing test cases.
        unused_refresh: Number of refresh button clicks (unused but required for callback).

    Returns:
        Dictionary containing:
            - case_options: List of available test case options
            - case_value: Currently selected test case value
    """
    config = load_config("./config.json")

    stored_case = config.get("CASE", "")

    options = []
    try:
        obj = os.scandir(data_path)
    except OSError:
        return {
            "case_options": "",
            "case_value": "",
        }

    for entry in obj:
        if entry.is_dir():
            # only add the folder with 'info.json'
            if os.path.exists(os.path.join(data_path, entry.name, "info.json")):
                options.append({"label": entry.name, "value": entry.name})

    case_val = options[0]["value"]

    # check previously loaded case in the browser's cache
    if stored_case:
        for _, case in enumerate(options):
            if stored_case == case["value"]:
                case_val = stored_case
                break

    return {
        "case_options": options,
        "case_value": case_val,
    }


@app.callback(
    output={
        "file_value": Output("file-picker-modal", "value"),
        "file_options": Output("file-picker-modal", "options"),
    },
    inputs={
        "case_val": Input("case-picker-modal", "value"),
    },
    state={
        "data_path": State("data-path-modal", "value"),
    },
)
def on_case_change(
    case_val: str, data_path: str
) -> Dict[str, Union[str, List[Dict[str, str]]]]:
    """
    Update available data files when test case selection changes.

    Args:
        case_val: Selected test case name.
        data_path: Path to the data directory.

    Returns:
        Dictionary containing:
            - file_value: Currently selected file value (JSON string)
            - file_options: List of available data file options
    """
    config = load_config("./config.json")

    stored_file = config.get("FILE", "")

    if not case_val:
        return {
            "file_value": "",
            "file_options": "",
        }

    case_dir = os.path.join(data_path, case_val)
    data_files = []
    for dirpath, dirnames, files in os.walk(case_dir):
        dirnames[:] = [d for d in dirnames if d not in SPECIAL_FOLDERS]
        for name in files:
            if name.lower().endswith(RADAR_FILE_EXTENSIONS):
                data_files.append(
                    {
                        "label": os.path.join(dirpath[len(case_dir) :], name),
                        "value": json.dumps(
                            {
                                "path": dirpath,
                                "name": name,
                                "label": os.path.join(dirpath[len(case_dir) :], name),
                            }
                        ),
                    }
                )

    if not data_files:
        return {
            "file_value": "",
            "file_options": "",
        }

    file_value = data_files[0]["value"]
    if stored_file:
        for _, file in enumerate(data_files):
            if stored_file == file["value"]:
                file_value = stored_file
                break

    config["DATA_PATH"] = data_path
    config["CASE"] = case_val
    config["FILE"] = file_value
    save_config(config, "./config.json")

    return {
        "file_value": file_value,
        "file_options": data_files,
    }


@app.callback(
    output={
        "modal_is_open": Output("modal-centered", "is_open", allow_duplicate=True),
        "data_path_str": Output("data-path", "value"),
        "test_case_str": Output("test-case", "value"),
        "log_file_str": Output("log-file", "value"),
        "current_file_update": Output("current-file", "data"),
        "add_file_value": Output("file-add", "value"),
        "add_file_options": Output("file-add", "options"),
    },
    inputs={
        "unused_ok_modal": Input("ok-modal", "n_clicks"),
    },
    state={
        "data_path": State("data-path-modal", "value"),
        "case_val": State("case-picker-modal", "value"),
        "file_value": State("file-picker-modal", "value"),
        "file_options": State("file-picker-modal", "options"),
        "current_file": State("current-file", "data"),
    },
    prevent_initial_call=True,
)
def on_modal_close(
    unused_ok_modal: Optional[int],
    data_path: str,
    case_val: str,
    file_value: str,
    file_options: List[Dict[str, str]],
    current_file: Optional[str],
) -> Dict[str, Any]:
    """
    Apply configuration changes when modal is closed via OK button.

    Args:
        unused_ok_modal: Number of OK button clicks (unused but required for callback).
        data_path: Selected data directory path.
        case_val: Selected test case name.
        file_value: Selected file value (JSON string).
        file_options: List of available file options.
        current_file: Currently loaded file value.

    Returns:
        Dictionary containing updated UI state values including modal visibility,
        display strings, and file configurations.

    Raises:
        PreventUpdate: If no file is selected.
    """
    if not file_value:
        raise PreventUpdate

    config = load_config("./config.json")

    file_dict = json.loads(file_value)

    config["DATA_PATH"] = data_path
    config["CASE"] = case_val
    config["FILE"] = file_value
    save_config(config, "./config.json")

    if current_file == file_value:
        return {
            "modal_is_open": False,
            "data_path_str": data_path,
            "test_case_str": case_val,
            "log_file_str": file_dict["label"],
            "current_file_update": dash.no_update,
            "add_file_value": dash.no_update,
            "add_file_options": dash.no_update,
        }

    return {
        "modal_is_open": False,
        "data_path_str": data_path,
        "test_case_str": case_val,
        "log_file_str": file_dict["label"],
        "current_file_update": file_value,
        "add_file_value": [],
        "add_file_options": file_options,
    }


@app.callback(
    output={
        "modal_is_open": Output("modal-centered", "is_open", allow_duplicate=True),
    },
    inputs={
        "unused_select_modal": Input("select-button", "n_clicks"),
    },
    prevent_initial_call=True,
)
def open_modal(unused_select_modal: Optional[int]) -> Dict[str, bool]:
    """
    Open the configuration modal when select button is clicked.

    Args:
        unused_select_modal: Number of select button clicks (unused but required for callback).

    Returns:
        Dictionary containing modal open state.
    """
    return {"modal_is_open": True}


# This clientside callback function disables the interval component based on
# the number of clicks on the play button and stop button. If the play button
# is clicked and the number of play clicks is greater than 0, the interval
# component is disabled. If the stop button is clicked and the number of stop
# clicks is greater than 0, the interval component is enabled. If neither button
# is clicked, the interval component remains unchanged.
app.clientside_callback(
    """
    function(n_clicks, ispaused) {
        const triggered = dash_clientside.callback_context.triggered.map(
            t => t.prop_id
            );
        if (triggered.length > 0 && triggered[0].includes('play-stop-button')) {
            if (n_clicks > 0) {
                return ispaused ? false : true;
            }
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("interval-component", "disabled"),
    Input("play-stop-button", "n_clicks"),
    State("interval-component", "disabled"),
)

app.clientside_callback(
    """
    function(current_file, add_file) {
        return {display: "flex"};
    }
    """,
    Output("loading-view", "style", allow_duplicate=True),
    Input("current-file", "data"),
    Input("file-add", "value"),
    prevent_initial_call=True,
)

# The picker panel is the only place the combined logs are named, and it closes
# on demand, so the button that opens it carries the fact that some are in play.
app.clientside_callback(
    """
    function(add_file) {
        var combining = Array.isArray(add_file) && add_file.length > 0;
        return "sv-icon-btn" + (combining ? " active" : "");
    }
    """,
    Output("button-add", "className"),
    Input("file-add", "value"),
)

# Slot assignment is the enable switch for a view, and the slot layout.
#
# These six figures are expensive, so only the two on screen are live: a view
# placed in a slot gets its switch turned on and a class that orders it left or
# right, everything else goes off and stays hidden, and a collapsed dock turns
# all of them off. Re-firing on `file-loaded-trigger` means a newly loaded log
# refreshes the visible charts rather than blanking them.
app.clientside_callback(
    f"""
    function(slot_a, slot_b, dock_state, unused_file_loaded) {{
        const keys = {[key for key, _, _ in DOCK_VIEWS]};
        const live = (dock_state || {{}}).open === true;
        const a = live ? slot_a : null;
        const b = live ? slot_b : null;
        // The divider between the slots only exists when both are filled.
        const paired = keys.indexOf(a) >= 0 && keys.indexOf(b) >= 0;
        const classes = keys.map(function (key) {{
            if (key === a) return "sv-dock-pane sv-slot-a";
            if (key === b) {{
                return "sv-dock-pane sv-slot-b" + (paired ? " sv-slot-paired" : "");
            }}
            return "sv-dock-pane";
        }});
        const switches = keys.map(function (key) {{
            return key === a || key === b ? [true] : [];
        }});
        return classes.concat(switches);
    }}
    """,
    [Output(f"dock-pane-{key}", "className") for key, _, _ in DOCK_VIEWS]
    + [Output(switch_id, "value") for _, switch_id, _ in DOCK_VIEWS],
    Input("dock-slot-a", "value"),
    Input("dock-slot-b", "value"),
    Input("dock-state", "data"),
    Input("file-loaded-trigger", "data"),
)

# A view can only be in one slot -- its component ids exist once. Picking a view
# the other slot already holds therefore swaps the two rather than failing: the
# store remembers the last accepted pair, which is how this knows which of the
# two selects the user just changed.
app.clientside_callback(
    f"""
    function(slot_a, slot_b, previous) {{
        const empty = "{EMPTY_SLOT}";
        const prev = previous || {{}};
        if (slot_a && slot_a === slot_b && slot_a !== empty) {{
            if (slot_a !== prev.a) {{
                slot_b = prev.a || empty;
            }} else {{
                slot_a = prev.b || empty;
            }}
        }}
        return [slot_a, slot_b, {{a: slot_a, b: slot_b}}];
    }}
    """,
    Output("dock-slot-a", "value"),
    Output("dock-slot-b", "value"),
    Output("dock-slots", "data"),
    Input("dock-slot-a", "value"),
    Input("dock-slot-b", "value"),
    State("dock-slots", "data"),
)

app.clientside_callback(
    """
    function(n_clicks, slot_a, slot_b) {
        if (!n_clicks) {
            return [window.dash_clientside.no_update,
                    window.dash_clientside.no_update];
        }
        return [slot_b, slot_a];
    }
    """,
    Output("dock-slot-a", "value", allow_duplicate=True),
    Output("dock-slot-b", "value", allow_duplicate=True),
    Input("dock-swap", "n_clicks"),
    State("dock-slot-a", "value"),
    State("dock-slot-b", "value"),
    prevent_initial_call=True,
)

# The dock's open state has to reach the server-side gate above, and the collapse
# itself is clientside, so the toggle button updates a store that both read.
app.clientside_callback(
    """
    function(n_clicks, state) {
        if (!n_clicks) {
            return window.dash_clientside.no_update;
        }
        return {open: !((state || {}).open === true)};
    }
    """,
    Output("dock-state", "data"),
    Input("dock-toggle", "n_clicks"),
    State("dock-state", "data"),
)

# Mirror the hidden path/case/file fields into the top bar breadcrumb.
app.clientside_callback(
    """
    function(case_name, log_file) {
        const empty = "sv-crumb sv-crumb-file sv-crumb-empty";
        const named = "sv-crumb sv-crumb-file";
        return [
            case_name || "No test case",
            log_file || "select a log …",
            log_file ? named : empty,
        ];
    }
    """,
    Output("crumb-case", "children"),
    Output("crumb-file", "children"),
    Output("crumb-file", "className"),
    Input("test-case", "value"),
    Input("log-file", "value"),
)

# Frame counter beside the transport slider.
app.clientside_callback(
    """
    function(value, max_value) {
        return [String(value || 0), " / " + String(max_value || 0)];
    }
    """,
    Output("frame-current", "children"),
    Output("frame-total", "children"),
    Input("slider-frame", "value"),
    Input("slider-frame", "max"),
)

get_test_case_view_callbacks(app)
get_control_view_callbacks(app)
get_scatter_3d_view_callbacks(app)
get_scatter_3d_view_background_callbacks(app)
get_scatter_2d_left_view_callbacks(app)
get_scatter_2d_right_view_callbacks(app)
get_heatmap_view_callbacks(app)
get_histogram_view_callbacks(app)
get_parcats_view_callbacks(app)
get_violin_view_callbacks(app)
get_camera_view_callbacks(app)
get_threshold_view_callbacks(app)


if __name__ == "__main__":
    DEBUG = False
    if DEBUG:
        app.run(debug=True, threaded=True, processes=1, host="0.0.0.0")

    else:
        # serve(app.server, listen="*:8000")
        freeze_support()

        FlaskUI(
            app=app.server, server="flask", port=8521, profile_dir_prefix="sensorview"
        ).run()
