"""SensorView File Modal Callbacks

The dataset picker: the modal that chooses a data path, a case folder inside it,
and a log inside that. It is the only way a dataset enters a session, and the
last thing it does -- writing the chosen file to ``current-file`` -- is what
starts the load in :mod:`view_callbacks.test_case_view`.

The chosen path, case and file are mirrored into ``config.json`` on every step,
so the next launch reopens where the last one left off.

Usage:
    from view_callbacks.file_modal_view import get_file_modal_view_callbacks
    get_file_modal_view_callbacks(app)

Author: Zhengyu Peng
License: GPL-3.0
"""

from typing import Dict, List, Any, Optional, Union

import json
import os
import shutil

import dash
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

import desktop

from settings import DATA_PATH, RADAR_FILE_EXTENSIONS
from utils import load_config, save_config

from dataio.manifest import table_sidecar_suffixes


def get_file_modal_view_callbacks(app: dash.Dash) -> None:
    """
    Register callback functions for the dataset picker modal.

    Args:
        app: The Dash application instance.

    Returns:
        None
    """

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
            "data_path": Output("data-path-modal", "value", allow_duplicate=True),
        },
        inputs={"unused_browse": Input("browse-button-modal", "n_clicks")},
        state={"data_path": State("data-path-modal", "value")},
        prevent_initial_call=True,
    )
    def on_browse(unused_browse: Optional[int], data_path: str) -> Dict[str, str]:
        """
        Fill the data path from the OS folder chooser.

        Only the desktop shell can raise a native dialog, so the button that gets
        here is rendered disabled without one and this stays unreachable.

        Args:
            unused_browse: Number of browse button clicks (unused but required for callback).
            data_path: Current contents of the path field, used to open the dialog
                somewhere useful.

        Returns:
            Dictionary containing the chosen data path, which the path Input then
            rescans for test cases.

        Raises:
            PreventUpdate: If the dialog was cancelled or is unavailable, so a
                typed path survives a stray click.
        """
        chosen = desktop.pick_folder(data_path)
        if chosen is None:
            raise PreventUpdate

        return {"data_path": chosen}

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
        # Sidecars that are Parquet in their own right are not logs, however much
        # they look like one to a listing that goes by extension.
        sidecar_suffixes = tuple(table_sidecar_suffixes(case_dir))
        data_files = []
        for dirpath, _, files in os.walk(case_dir):
            for name in files:
                lowered = name.lower()
                if lowered.endswith(RADAR_FILE_EXTENSIONS) and not lowered.endswith(
                    sidecar_suffixes
                ):
                    data_files.append(
                        {
                            "label": os.path.join(dirpath[len(case_dir) :], name),
                            "value": json.dumps(
                                {
                                    "path": dirpath,
                                    "name": name,
                                    "label": os.path.join(
                                        dirpath[len(case_dir) :], name
                                    ),
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
