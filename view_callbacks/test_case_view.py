"""SensorView Test Case View Callbacks

This module provides callback functions for managing test case selection and configuration
in the SensorView application.

Core Features:
-------------
1. Test Case Management:
   - Test case loading and validation
   - Configuration persistence
   - Path management
   - File selection

2. UI Controls:
   - Case picker updates
   - File picker updates
   - Modal dialog management
   - Error handling

3. Data Validation:
   - Path existence checking
   - File format validation
   - Configuration verification
   - Error reporting

Dependencies:
------------
- dash & dash-bootstrap-components
- app_config settings
- Standard Python libraries

Usage:
------
Register callbacks with app instance:
    from view_callbacks.test_case_view import get_test_case_view_callbacks
    get_test_case_view_callbacks(app)

Author: Zhengyu Peng
Email: zpeng.me@gmail.com
Website: https://zpeng.me
License: GPL-3.0
"""

import os

import pandas as pd
import numpy as np

import dash
from dash import dcc
from dash import html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from app_config import (
    DROPDOWN_OPTIONS_ALL,
    DROPDOWN_VALUES_ALL,
    DROPDOWN_VALUES_ALL_STATE,
)
from app_config import DROPDOWN_OPTIONS_CAT, DROPDOWN_VALUES_CAT
from app_config import DROPDOWN_OPTIONS_CAT_COLOR, DROPDOWN_VALUES_CAT_COLOR
from app_config import DROPDOWN_OPTIONS_3D_XYZ, DROPDOWN_OPTIONS_3D_XYZ_REF
from app_config import DROPDOWN_VALUES_3D_XYZ, DROPDOWN_VALUES_3D_XYZ_REF
from app_config import background_callback_manager
from app_config import CACHE_KEYS, KEY_TYPES, THEME

from utils import load_config, cache_set, cache_get
from utils import load_data


def get_test_case_view_callbacks(app: dash.Dash) -> None:
    """
    Register the callback functions for the test case selection view.

    Args:
        app (dash.Dash): The Dash application instance

    Returns:
        None
    """

    @app.callback(
        background=True,
        output={
            "key_dict": Output("key-dict", "data"),
            "file_load_trigger": Output("file-loaded-trigger", "data"),
            "stored_file": Output("local-file-selection", "data"),
            "frame_min": Output("slider-frame", "min"),
            "frame_max": Output("slider-frame", "max"),
            "dropdown_container": Output("dropdown-container", "children"),
            "slider_container": Output("slider-container", "children"),
            "dim_picker_opt": Output("dim-picker-parallel", "options"),
            "dim_picker_val": Output("dim-picker-parallel", "value"),
            "dp_opts_all": DROPDOWN_OPTIONS_ALL,
            "dp_vals_all": DROPDOWN_VALUES_ALL,
            "dp_opts_cat_color": DROPDOWN_OPTIONS_CAT_COLOR,
            "dp_vals_cat_color": DROPDOWN_VALUES_CAT_COLOR,
            "dp_opts_cat": DROPDOWN_OPTIONS_CAT,
            "dp_vals_cat": DROPDOWN_VALUES_CAT,
            "dp_opts_num": DROPDOWN_OPTIONS_3D_XYZ,
            "dp_vals_num": DROPDOWN_VALUES_3D_XYZ,
            "dp_opts_num_with_none": DROPDOWN_OPTIONS_3D_XYZ_REF,
            "dp_vals_num_with_none": DROPDOWN_VALUES_3D_XYZ_REF,
        },
        inputs={
            "file": Input("current-file", "data"),
            "add_file_value": Input("file-add", "value"),
        },
        state={
            "data_path": State("data-path", "value"),
            "case": State("test-case", "value"),
            "file_loaded": State("file-loaded-trigger", "data"),
            "session_id": State("session-id", "data"),
            "all_state": DROPDOWN_VALUES_ALL_STATE,
        },
        progress=[
            Output("loading-view", "style"),
        ],
        manager=background_callback_manager,
    )
    def file_select_changed(
        set_progress: callable,
        file: str,
        add_file_value: list,
        data_path: str,
        case: str,
        file_loaded: int,
        session_id: str,
        all_state: list,
    ) -> dict:
        """
        Callback when a file selection is changed.

        Args:
            set_progress (callable): Function to set the progress visual indicators
            file (str): Selected file value
            add_file_value (list): List containing additional file values
            data_path (str): Path to data directory
            case (str): Test case value
            file_loaded (int): Number of times the file has been loaded
            session_id (str): Session identifier
            all_state (list): State of all dropdown components

        Returns:
            dict: Configuration data containing:
                - key_dict (dict): Dictionary of keys and their configurations
                - file_load_trigger (int): File load trigger count
                - stored_file (str): Stored file value
                - frame_min (int): Minimum frame index
                - frame_max (int): Maximum frame index
                - dropdown_container (list): Dropdown components for categorical values
                - slider_container (list): Slider components for numerical values
                - dim_picker_opt (list): Dimension picker options
                - dim_picker_val (list): Dimension picker values
                - dp_opts_all (list): Dropdown options for all keys
                - dp_vals_all (list): Dropdown values for all keys
                - dp_opts_cat_color (list): Dropdown options for categorical color keys
                - dp_vals_cat_color (list): Dropdown values for categorical color keys
                - dp_opts_cat (list): Dropdown options for categorical keys
                - dp_vals_cat (list): Dropdown values for categorical keys

        Raises:
            PreventUpdate: If no file is selected
        """
        if not file:
            raise PreventUpdate

        # set_progress(
        #     [
        #         {
        #             "position": "fixed",
        #             "top": 0,
        #             "left": 0,
        #             "width": "100%",
        #             "height": "100%",
        #             "backgroundColor": "rgba(0, 0, 0, 0.9)",
        #         },
        #     ]
        # )
        cache_set(-1, session_id, CACHE_KEYS["task_id"])
        cache_set(-1, session_id, CACHE_KEYS["figure_idx"])

        if os.path.exists(os.path.join(data_path, case, "info.json")):
            config = load_config(os.path.join(data_path, case, "info.json"))
            cache_set(config, session_id, CACHE_KEYS["config"])
        else:
            raise PreventUpdate

        # extract keys and save to Cache
        num_keys = []
        cat_keys = []
        for _, item in enumerate(config["keys"]):
            if config["keys"][item].get("type", KEY_TYPES["NUM"]) == KEY_TYPES["NUM"]:
                num_keys.append(item)
            else:
                cat_keys.append(item)
        filter_kwargs = {"num_keys": num_keys, "cat_keys": cat_keys}
        cache_set(filter_kwargs, session_id, CACHE_KEYS["filter_kwargs"])

        # options for `DROPDOWN_OPTIONS_ALL`
        options_all = [
            [
                {"label": config["keys"][item].get("description", item), "value": item}
                for _, item in enumerate(config["keys"])
            ]
        ] * len(DROPDOWN_OPTIONS_ALL)

        # values for `DROPDOWN_VALUES_ALL`
        all_keys = num_keys + cat_keys
        if len(all_keys) == 0:
            values_all = [None] * len(DROPDOWN_VALUES_ALL)
        else:
            values_all = [
                all_keys[x % len(all_keys)] for x in range(0, len(DROPDOWN_VALUES_ALL))
            ]

        for idx, item in enumerate(all_state):
            if item in all_keys:
                values_all[idx] = item

        # options for `DROPDOWN_OPTIONS_CAT_COLOR`
        options_cat_color = [
            [{"label": "None", "value": "None"}]
            + [
                {"label": config["keys"][item].get("description", item), "value": item}
                for _, item in enumerate(cat_keys)
            ]
        ] * len(DROPDOWN_OPTIONS_CAT_COLOR)

        # values for `DROPDOWN_VALUES_CAT_COLOR`
        values_cat_color = ["None"] * len(DROPDOWN_VALUES_CAT_COLOR)

        # options for `DROPDOWN_OPTIONS_CAT`
        options_cat = [
            [
                {"label": config["keys"][item].get("description", item), "value": item}
                for _, item in enumerate(cat_keys)
            ]
        ] * len(DROPDOWN_OPTIONS_CAT)

        options_num = [
            [
                {"label": config["keys"][item].get("description", item), "value": item}
                for _, item in enumerate(num_keys)
            ]
        ] * len(DROPDOWN_OPTIONS_3D_XYZ)

        options_num_with_none = [
            [{"label": "None", "value": "None"}]
            + [
                {"label": config["keys"][item].get("description", item), "value": item}
                for _, item in enumerate(num_keys)
            ]
        ] * len(DROPDOWN_OPTIONS_3D_XYZ_REF)

        if len(num_keys) == 0:
            xyz_all = [None] * len(DROPDOWN_VALUES_3D_XYZ)
        else:
            xyz_all = [
                num_keys[x % len(num_keys)]
                for x in range(0, len(DROPDOWN_VALUES_3D_XYZ))
            ]

        xyz_all[0] = config.get("slider", xyz_all[0])
        xyz_all[1] = config.get("x_3d", xyz_all[1])
        xyz_all[2] = config.get("y_3d", xyz_all[2])
        xyz_all[3] = config.get("z_3d", xyz_all[3])

        if len(num_keys) == 0:
            xyz_ref_all = [None] * len(DROPDOWN_VALUES_3D_XYZ_REF)
        else:
            xyz_ref_all = [
                num_keys[x % len(num_keys)]
                for x in range(0, len(DROPDOWN_VALUES_3D_XYZ_REF))
            ]

        xyz_ref_all[0] = config.get("x_ref", "None")
        xyz_ref_all[1] = config.get("y_ref", "None")
        xyz_ref_all[2] = config.get("z_ref", "None")

        # values for `DROPDOWN_VALUES_CAT`
        if len(cat_keys) == 0:
            values_cat = [None] * len(DROPDOWN_VALUES_CAT)
        else:
            values_cat = [cat_keys[0]] * len(DROPDOWN_VALUES_CAT)

        keys_dict = config["keys"]

        new_data = load_data(add_file_value, file)
        # get the list of frames and save to Cache
        frame_list = np.sort(new_data[config["slider"]].unique())
        cache_set(frame_list, session_id, CACHE_KEYS["frame_list"])

        # create the visibility table and save to Cache
        #   the visibility table is used to indicate if the data point is
        #   `visible` or `hidden`
        visible_table = pd.DataFrame()
        visible_table["_IDS_"] = new_data.index
        visible_table["_VIS_"] = "visible"
        cache_set(visible_table, session_id, CACHE_KEYS["visible_table"])

        # group the DataFrame by frame and save the grouped data one by one
        # into Cache
        frame_group = new_data.groupby(config["slider"])
        for frame_idx, frame_data in frame_group:
            cache_set(frame_data, session_id, CACHE_KEYS["frame_data"], str(frame_idx))

        # create dropdown layouts
        # obtain categorical values
        cat_values = []
        new_dropdown = []
        for idx, d_item in enumerate(cat_keys):
            if d_item in new_data.columns:
                var_list = new_data[d_item].unique().tolist()
                value_list = var_list
            else:
                var_list = []
                value_list = []

            new_dropdown.append(dbc.Label(keys_dict[d_item]["description"]))
            new_dropdown.append(
                html.Div(
                    dcc.Dropdown(
                        id={"type": "filter-dropdown", "index": idx},
                        options=[{"label": i, "value": i} for i in var_list],
                        value=value_list,
                        multi=True,
                    ),
                    className=THEME,
                )
            )

            cat_values.append(value_list)

        # create slider layouts
        # obtain numerical values
        num_values = []
        new_slider = []
        for idx, item in enumerate(num_keys):
            if item in new_data.columns:
                # use `.tolist()` to convert numpy type ot python type
                var_min = np.floor(np.min(new_data[item])).tolist()
                var_max = np.ceil(np.max(new_data[item])).tolist()
            else:
                var_min = 0
                var_max = 0

            new_slider.append(dbc.Label(keys_dict[item]["description"]))
            new_slider.append(
                dcc.RangeSlider(
                    id={"type": "filter-slider", "index": idx},
                    min=var_min,
                    max=var_max,
                    marks=None,
                    step=round((var_max - var_min) / 100, 3),
                    value=[var_min, var_max],
                    tooltip={"always_visible": False},
                )
            )

            num_values.append([var_min, var_max])

        # save categorical values and numerical values to Cache
        filter_kwargs["num_values"] = num_values
        filter_kwargs["cat_values"] = cat_values
        cache_set(filter_kwargs, session_id, CACHE_KEYS["filter_kwargs"])

        # dimensions picker default value
        if len(cat_keys) == 0:
            t_values_cat = None
        else:
            t_values_cat = cat_keys[0]

        set_progress(
            [
                {
                    "position": "fixed",
                    "top": 0,
                    "left": 0,
                    "width": "100%",
                    "height": "100%",
                    "backgroundColor": "rgba(0, 0, 0, 0.9)",
                    "display": "none",
                },
            ]
        )

        return {
            "key_dict": keys_dict,
            "file_load_trigger": file_loaded + 1,
            "stored_file": file,
            "frame_min": 0,
            "frame_max": len(frame_list) - 1,
            "dropdown_container": new_dropdown,
            "slider_container": new_slider,
            "dim_picker_opt": [{"label": ck, "value": ck} for ck in cat_keys],
            "dim_picker_val": [t_values_cat],
            "dp_opts_all": options_all,
            "dp_vals_all": values_all,
            "dp_opts_cat_color": options_cat_color,
            "dp_vals_cat_color": values_cat_color,
            "dp_opts_cat": options_cat,
            "dp_vals_cat": values_cat,
            "dp_opts_num": options_num,
            "dp_vals_num": xyz_all,
            "dp_opts_num_with_none": options_num_with_none,
            "dp_vals_num_with_none": xyz_ref_all,
        }

    @app.callback(
        output={"slider_value": Output("slider-frame", "value")},
        inputs={
            "unused_file_loaded": Input("file-loaded-trigger", "data"),
            "left_btn": Input("previous-button", "n_clicks"),
            "right_btn": Input("next-button", "n_clicks"),
            "interval": Input("interval-component", "n_intervals"),
        },
        state={
            "file": State("current-file", "data"),
            "slider_max": State("slider-frame", "max"),
            "slider_state": State("slider-frame", "value"),
            "session_id": State("session-id", "data"),
        },
    )
    def update_slider(
        unused_file_loaded: int,
        left_btn: int,
        right_btn: int,
        interval: int,
        file: str,
        slider_max: int,
        slider_state: int,
        session_id: str,
    ) -> dict:
        """
        Update the slider position based on user interactions.

        Args:
            unused_file_loaded (int): File load trigger count
            left_btn (int): Number of clicks on the previous button
            right_btn (int): Number of clicks on the next button
            interval (int): Number of intervals
            file (str): Selected file information
            slider_max (int): Maximum slider value
            slider_state (int): Current slider position
            session_id (str): Session identifier

        Returns:
            dict: Contains:
                - slider_value (int): New slider position

        Raises:
            PreventUpdate: If file is None or no valid trigger is detected
        """
        if file is None:
            raise PreventUpdate

        ctx = dash.callback_context
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        if trigger_id == "file-loaded-trigger":
            return {"slider_value": 0}

        if trigger_id == "previous-button":
            if left_btn == 0:
                raise PreventUpdate

            # previous button is clicked
            return {"slider_value": (slider_state - 1) % (slider_max + 1)}

        if trigger_id == "next-button":
            if right_btn == 0:
                raise PreventUpdate

            # next button is clicked
            return {"slider_value": (slider_state + 1) % (slider_max + 1)}

        if trigger_id == "interval-component":
            if interval == 0:
                raise PreventUpdate

            fig_idx = cache_get(session_id, CACHE_KEYS["figure_idx"])
            if fig_idx is not None:
                if slider_state > fig_idx:
                    return {"slider_value": dash.no_update}

                return {"slider_value": (slider_state + 1) % (slider_max + 1)}

            return {"slider_value": dash.no_update}

    @app.callback(
        output={"state": Output("collapse-add", "is_open")},
        inputs={"click": Input("button-add", "n_clicks")},
        state={
            "open_state": State("collapse-add", "is_open"),
            "add_file_value": State("file-add", "value"),
        },
    )
    def add_data(click: int, open_state: bool, add_file_value: str) -> dict:
        """
        Toggle the state of the add data collapse element.

        Args:
            click (int): Number of button clicks
            open_state (bool): Current state of the collapse element
            add_file_value (str): Value of the file add input

        Returns:
            dict: Contains:
                - state (bool): New state of the collapse element

        Raises:
            PreventUpdate: If button has not been clicked
        """
        if click == 0:
            raise PreventUpdate

        if open_state is True and not add_file_value:
            return {"state": False}

        return {"state": True}

    @app.callback(
        output={
            "left_switch": Output("left-switch", "value"),
            "right_switch": Output("right-switch", "value"),
            "hist_switch": Output("histogram-switch", "value"),
            "violin_switch": Output("violin-switch", "value"),
            "parallel_switch": Output("parallel-switch", "value"),
            "heat_switch": Output("heat-switch", "value"),
        },
        inputs={"unused_file_loaded": Input("file-loaded-trigger", "data")},
        state={
            "file": State("current-file", "data"),
            "case": State("test-case", "value"),
        },
    )
    def reset_switch_state(unused_file_loaded: int, file: str, case: str) -> dict:
        """
        Reset the state of all switch components when a new file is loaded.

        Args:
            unused_file_loaded (int): File load trigger count
            file (str): Selected file value
            case (str): Selected test case value

        Returns:
            dict: Contains empty lists for all switches:
                - left_switch (list)
                - right_switch (list)
                - hist_switch (list)
                - violin_switch (list)
                - parallel_switch (list)
                - heat_switch (list)

        Raises:
            PreventUpdate: If either file or case is None
        """
        if file is None:
            raise PreventUpdate

        if case is None:
            raise PreventUpdate

        return {
            "left_switch": [],
            "right_switch": [],
            "hist_switch": [],
            "violin_switch": [],
            "parallel_switch": [],
            "heat_switch": [],
        }
