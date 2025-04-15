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

import json
import os
import shutil

# from waitress import serve
from multiprocessing import freeze_support

from flaskwebgui import FlaskUI

import dash
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from utils import load_config, save_config

from view_callbacks.test_case_view import get_test_case_view_callbacks
from view_callbacks.control_view import get_control_view_callbacks
from view_callbacks.scatter_3d_view import get_scatter_3d_view_callbacks
from view_callbacks.scatter_2d_left_view import get_scatter_2d_left_view_callbacks
from view_callbacks.scatter_2d_right_view import get_scatter_2d_right_view_callbacks
from view_callbacks.heatmap_view import get_heatmap_view_callbacks
from view_callbacks.histogram_view import get_histogram_view_callbacks
from view_callbacks.parcats_view import get_parcats_view_callbacks
from view_callbacks.violin_view import get_violin_view_callbacks

from app_config import APP_TITLE, DATA_PATH
from app_config import SPECIAL_FOLDERS

from app_layout import get_app_layout


app = dash.Dash(
    __name__,
    meta_tags=[{"name": "viewport", "content": "width=device-width,initial-scale=1"}],
)
app.scripts.config.serve_locally = True
app.css.config.serve_locally = True
app.title = APP_TITLE
app.layout = get_app_layout


@app.callback(
    output={
        "data_path": Output("data-path-modal", "value"),
    },
    inputs={"is_modal_open": Input("modal-centered", "is_open")},
)
def on_modal_open(is_modal_open):
    """
    Callback function to update the data path when the modal is opened.

    Parameters:
    - is_modal_open (bool): Whether the modal is open.

    Returns:
    - dict: A dictionary containing the data path.
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
def on_path_change(data_path, unused_refresh):
    """
    Callback function to update the case options and value when the data path changes.

    Parameters:
    - data_path (str): The path to the data directory.
    - unused_refresh (int): The number of times the refresh button has been clicked.

    Returns:
    - dict: A dictionary containing the case options and value.
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
def on_case_change(case_val, data_path):
    """
    Callback function to update the file options and value when the case changes.

    Parameters:
    - case_val (str): The name of the case.
    - data_path (str): The path to the data directory.

    Returns:
    - dict: A dictionary containing the file options and value.
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
    unused_ok_modal, data_path, case_val, file_value, file_options, current_file
):
    """
    Callback function to update the data path, test case, log file,
        and current file when the modal is closed.

    Parameters:
    - unused_ok_modal (int): The number of times the OK button has been clicked.
    - data_path (str): The path to the data directory.
    - case_val (str): The name of the case.
    - file_value (str): The value of the selected file.
    - file_options (list): The list of file options.
    - current_file (str): The current file.

    Returns:
    - dict: A dictionary containing the updated values.
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
def open_modal(unused_select_modal):
    """
    Callback function to open the modal.

    Parameters:
    - unused_select_modal (int): The number of times the select button has been clicked.

    Returns:
    - dict: A dictionary containing the updated value for the modal's is_open property.
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

get_test_case_view_callbacks(app)
get_control_view_callbacks(app)
get_scatter_3d_view_callbacks(app)
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
            app=app.server, server="flask", port=45678, profile_dir_prefix="sensorview"
        ).run()
