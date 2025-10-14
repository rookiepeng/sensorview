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

from flask import jsonify, Response

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

from app_config import app
from app_config import APP_TITLE, DATA_PATH, CACHE_KEYS
from app_config import SPECIAL_FOLDERS

from layouts.app_layout import get_app_layout


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

    if start_index > latest_server_buffer_index:
        return jsonify([{"index": -1}])

    if start_index == latest_server_buffer_index:
        return jsonify([])

    buffer = []
    for idx in range(start_index + 1, latest_server_buffer_index + 1):
        buffer.append(
            {
                "index": idx,
                "fig": cache_get(session, CACHE_KEYS["figure"], str(idx)),
                "hover_strings": cache_get(session, CACHE_KEYS["hover"], str(idx)),
                "ref_fig": cache_get(session, CACHE_KEYS["figure_ref"], str(idx)),
                "fig_layout": cache_get(session, CACHE_KEYS["figure_layout"], str(idx)),
            }
        )

    return jsonify(buffer)


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
    Input("stop-button", "n_clicks"),
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
            if name.lower().endswith(".csv"):
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
            elif name.lower().endswith(".pkl"):
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
    function(play_clicks, stop_clicks) {
        const triggered = dash_clientside.callback_context.triggered.map(
            t => t.prop_id
            );
        if (triggered.length > 0) {
            if (triggered[0].includes('play-button')) {
                if (play_clicks>0){
                    return false;
                }
                else {
                    return window.dash_clientside.no_update;
                }
            }
            if (triggered[0].includes('stop-button')) {
                if (stop_clicks>0){
                    return true;
                }
                else {
                    return window.dash_clientside.no_update;
                }
            }
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("interval-component", "disabled"),
    Input("play-button", "n_clicks"),
    Input("stop-button", "n_clicks"),
)

app.clientside_callback(
    """
    function(current_file, add_file) {
        
        return {
                    position: "fixed",
                    top: 0,
                    left: 0,
                    width: "100%",
                    height: "100%",
                    backgroundColor: "rgba(0, 0, 0, 0.9)",
                };
    }
    """,
    Output("loading-view", "style", allow_duplicate=True),
    Input("current-file", "data"),
    Input("file-add", "value"),
    prevent_initial_call=True,
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
