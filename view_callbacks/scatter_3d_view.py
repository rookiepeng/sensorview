"""SensorView 3D Scatter View Callbacks

This module provides callback functions for managing the 3D scatter plot view in the
SensorView application. It handles real-time visualization updates, user interactions,
and data export functionality.

Core Features:
-------------
1. View Management:
   - Real-time plot updates
   - Frame-by-frame navigation
   - Overlay mode support
   - Dark/light theme switching

2. Data Processing:
   - Frame buffering and caching
   - Background processing
   - Data filtering
   - Decay effect handling

3. User Interactions:
   - Click handling
   - Selection management
   - Export capabilities
   - Animation controls

Dependencies:
------------
- dash & plotly
- numpy & pandas
- app_config settings
- utils functions
- viz modules

Usage:
------
Register callbacks with app instance:
    from view_callbacks.scatter_3d_view import get_scatter_3d_view_callbacks
    get_scatter_3d_view_callbacks(app)

Author: Zhengyu Peng
Email: zpeng.me@gmail.com
Website: https://zpeng.me
License: GPL-3.0
"""

from typing import Dict, List, Union, Any, Callable
import json
import os
import datetime

import dash
from dash import dcc
from dash.dependencies import Input, Output, State, ALL
from dash.exceptions import PreventUpdate
import plotly.io as pio
import plotly.graph_objs as go

import numpy as np

from app_config import background_callback_manager
from app_config import CACHE_KEYS, KEY_TYPES

from utils import filter_all
from utils import cache_set, cache_get, cache_expire
from utils import load_data
from utils import load_image
from utils import prepare_figure_kwargs

from viz.viz import get_animation_data
from viz.graph_data import get_ref_scatter3d_data
from viz.graph_data import get_scatter3d_data
from viz.graph_layout import get_scatter3d_layout

from process_frame import process_overlay_frame
from process_frame import process_single_frame


def get_scatter_3d_view_callbacks(app: dash.Dash) -> None:
    """
    Register the callback functions for the 3D scatter plot view.

    Args:
        app (dash.Dash): The Dash application instance

    Returns:
        None
    """

    # Common state definitions to reduce repetition
    COMMON_STATE = {
        "session_id": State("session-id", "data"),
        "file": State("current-file", "data"),
        "file_list": State("file-add", "value"),
        "c_key": State("c-picker-3d", "value"),
        "size_vary": State("size-vary-switch", "value"),
        "darkmode": State("darkmode-switch", "value"),
    }

    FILTER_STATE = {
        "cat_values": State({"type": "filter-dropdown", "index": ALL}, "value"),
        "num_values": State({"type": "filter-slider", "index": ALL}, "value"),
        "visible_list": State("visible-picker", "value"),
    }

    ANIMATION_STATE = {
        "slider_arg": State("slider-frame", "value"),
        "ispaused": State("interval-component", "disabled"),
        "decay": State("decay-slider", "value"),
    }

    VISUAL_STATE = {
        "colormap": State("colormap-3d", "value"),
        "overlay_enable": State("overlay-switch", "value"),
    }

    PICKER_3D_STATE = {
        "slider_picker_3d": State("slider-picker-3d", "value"),
        "x_picker_3d": State("x-picker-3d", "value"),
        "y_picker_3d": State("y-picker-3d", "value"),
        "z_picker_3d": State("z-picker-3d", "value"),
        "x_ref_picker_3d": State("x-ref-picker-3d", "value"),
        "y_ref_picker_3d": State("y-ref-picker-3d", "value"),
        "z_ref_picker_3d": State("z-ref-picker-3d", "value"),
    }

    # Common input definitions
    FILTER_INPUTS = {
        "cat_values": Input({"type": "filter-dropdown", "index": ALL}, "value"),
        "num_values": Input({"type": "filter-slider", "index": ALL}, "value"),
        "visible_list": Input("visible-picker", "value"),
    }

    PICKER_3D_INPUTS = {
        "slider_picker_3d": Input("slider-picker-3d", "value"),
        "x_picker_3d": Input("x-picker-3d", "value"),
        "y_picker_3d": Input("y-picker-3d", "value"),
        "z_picker_3d": Input("z-picker-3d", "value"),
        "x_ref_picker_3d": Input("x-ref-picker-3d", "value"),
        "y_ref_picker_3d": Input("y-ref-picker-3d", "value"),
        "z_ref_picker_3d": Input("z-ref-picker-3d", "value"),
    }

    TRIGGER_INPUTS = {
        "unused_vistable_trigger": Input("visible-table-change-trigger", "data"),
        "unused_left_hide_trigger": Input("left-hide-trigger", "data"),
        "unused_right_hide_trigger": Input("right-hide-trigger", "data"),
        "unused_file_loaded": Input("file-loaded-trigger", "data"),
    }

    @app.callback(
        output={
            "is_open": Output("3d-config-collapse", "is_open"),
        },
        inputs={
            "n_clicks": Input("3d-config-more-button", "n_clicks"),
        },
        state={
            "is_open": State("3d-config-collapse", "is_open"),
        },
    )
    def toggle_3d_config_collapse(n_clicks: int, is_open: bool) -> dict:
        """
        Toggle the visibility of the 3D configuration collapse panel.

        Args:
            n_clicks (int): Number of times the more button has been clicked
            is_open (bool): Current state of the collapse panel

        Returns:
            dict: Updated collapse panel state

        Raises:
            PreventUpdate: If button has not been clicked
        """
        if n_clicks == 0:
            raise PreventUpdate

        return {"is_open": not is_open}

    @app.callback(
        output={
            "scatter3d": Output("scatter3d", "figure", allow_duplicate=True),
        },
        inputs={
            "unused_remote_trigger": Input("trigger-remote-figure", "data"),
            "overlay_enable": Input("overlay-switch", "value"),
        },
        state={
            **ANIMATION_STATE,
            **FILTER_STATE,
            **VISUAL_STATE,
            **COMMON_STATE,
        },
        prevent_initial_call=True,
    )
    def slider_change_callback(
        # Input parameters (ordered by input definition)
        unused_remote_trigger: int,
        overlay_enable: list,
        # Animation state parameters
        slider_arg: int,
        ispaused: bool,
        decay: int,
        # Filter state parameters
        cat_values: Dict[str, List[str]],
        num_values: List[Union[float, int]],
        visible_list: list,
        # Visual state parameters
        colormap: str,
        # Common state parameters
        session_id: str,
        file: str,
        file_list: list,
        c_key: str,
        size_vary: str,
        darkmode: list,
    ) -> dict:
        """
        Update the 3D scatter plot when slider position changes.

        Args:
            unused_remote_trigger (int): Remote figure trigger count
            overlay_enable (list): Overlay mode enable state
            slider_arg (int): Current slider position
            ispaused (bool): Animation pause state
            decay (int): Number of past frames to show
            cat_values (list): Selected categorical filter values
            num_values (list): Selected numerical filter values
            visible_list (list): List of visible elements
            colormap (str): Selected colormap name
            session_id (str): Session identifier
            file (str): Current file path
            file_list (list): List of all file paths
            c_key (str): Selected color key
            size_vary (str): Size variation enable state
            darkmode (list): Dark mode enable state

        Returns:
            dict: Updated scatter plot figure data
        """
        config = cache_get(session_id, CACHE_KEYS["config"])
        if config is None:
            raise PreventUpdate

        if overlay_enable:
            fig = process_overlay_frame(
                slider_arg,
                config,
                cat_values,
                num_values,
                colormap,
                visible_list,
                c_key,
                bool(size_vary),
                session_id,
                file,
                file_list,
            )
        else:
            fig = process_single_frame(
                config,
                cat_values,
                num_values,
                colormap,
                visible_list,
                c_key,
                bool(size_vary),
                decay,
                session_id,
                file,
                slider_arg,
                ispaused,
            )

        if darkmode:
            fig["layout"]["template"] = pio.templates["plotly_dark"]
        else:
            fig["layout"]["template"] = pio.templates["plotly"]

        return {"scatter3d": fig}

    @app.callback(
        output={
            "scatter3d": Output("scatter3d", "figure", allow_duplicate=True),
        },
        inputs={
            "colormap": Input("colormap-3d", "value"),
        },
        state={
            "fig": State("scatter3d", "figure"),
        },
        prevent_initial_call=True,
    )
    def colormap_change_callback(colormap: str, fig: dict) -> dict:
        """
        Update the colormap of the 3D scatter plot.

        Args:
            colormap (str): Name of the selected colormap
            fig (dict): Current figure dictionary

        Returns:
            dict: Updated figure with new colormap
        """
        for idx in range(0, len(fig["data"])):
            fig["data"][idx]["marker"]["colorscale"] = colormap

        return {"scatter3d": fig}

    @app.callback(
        output={
            "scatter3d": Output("scatter3d", "figure", allow_duplicate=True),
        },
        inputs={
            "darkmode": Input("darkmode-switch", "value"),
        },
        state={
            "fig": State("scatter3d", "figure"),
        },
        prevent_initial_call=True,
    )
    def darkmode_change_callback(darkmode: list, fig: dict) -> dict:
        """
        Toggle dark mode for the 3D scatter plot.

        Args:
            darkmode (list): Dark mode enable state
            fig (dict): Current figure dictionary

        Returns:
            dict: Updated figure with new theme
        """
        if darkmode:
            fig["layout"]["template"] = pio.templates["plotly_dark"]
        else:
            fig["layout"]["template"] = pio.templates["plotly"]

        return {"scatter3d": fig}

    @app.callback(
        output={
            "scatter3d": Output("scatter3d", "figure", allow_duplicate=True),
        },
        inputs={
            "size_vary": Input("size-vary-switch", "value"),
        },
        state={
            "fig": State("scatter3d", "figure"),
            "session_id": State("session-id", "data"),
            "c_key": State("c-picker-3d", "value"),
        },
        prevent_initial_call=True,
    )
    def size_vary_callback(
        size_vary: list, fig: dict, session_id: str, c_key: str
    ) -> dict:
        """
        Toggle size variation for the 3D scatter plot.

        Args:
            size_vary (list): Size variation enable state
            fig (dict): Current figure dictionary

        Returns:
            dict: Updated figure with new theme
        """

        config = cache_get(session_id, CACHE_KEYS["config"])
        if config is None or "keys" not in config:
            raise PreventUpdate
        keys_dict = config["keys"]

        ctype = keys_dict[c_key].get("type", KEY_TYPES["NUM"])

        if (
            config.get("x_ref", None) is not None
            and config.get("y_ref", None) is not None
        ):
            data_length = len(fig["data"]) - 1
        else:
            data_length = len(fig["data"])

        if size_vary and ctype == KEY_TYPES["CAT"]:
            for i in range(0, data_length):
                size_offset = data_length - 1 - i
                fig["data"][i]["marker"]["size"] = 3 + size_offset
        else:
            for i in range(0, data_length):
                fig["data"][i]["marker"]["size"] = 3

        return {"scatter3d": fig}

    @app.callback(
        output={
            "trigger": Output("visible-table-change-trigger", "data"),
        },
        inputs={
            "click_data": Input("scatter3d", "clickData"),
        },
        state={
            "trigger_input": State("visible-table-change-trigger", "data"),
            "click_hide": State("click-hide-switch", "value"),
            "session_id": State("session-id", "data"),
        },
        prevent_initial_call=True,
    )
    def visible_table_change_callback(
        click_data: dict,
        trigger_input: int,
        click_hide: list,
        session_id: str,
    ) -> dict:
        """
        Handle visibility changes from click interactions.

        Args:
            click_data (dict): Data from click event
            trigger_input (int): Current trigger state
            click_hide (list): Click-to-hide feature state
            session_id (str): Session identifier

        Returns:
            dict: Updated trigger value

        Raises:
            PreventUpdate: If click-to-hide is not enabled
        """
        visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])
        if click_hide and visible_table is not None and click_data is not None:
            point_id = (
                click_data.get("points", [{}])[0].get("id")
                if click_data.get("points")
                else None
            )
            if (
                point_id is not None
                and "_VIS_" in visible_table
                and point_id in visible_table["_VIS_"]
            ):
                if visible_table["_VIS_"][point_id] == "visible":
                    visible_table.at[point_id, "_VIS_"] = "hidden"
                else:
                    visible_table.at[point_id, "_VIS_"] = "visible"

                cache_set(visible_table, session_id, CACHE_KEYS["visible_table"])

                return {"trigger": trigger_input + 1}

        raise PreventUpdate

    @app.callback(
        output={
            "scatter3d": Output("scatter3d", "figure", allow_duplicate=True),
            "trigger": Output("background-trigger", "data"),
            "local_buffer_idx": Output(
                "local-buffer-index", "data", allow_duplicate=True
            ),
        },
        inputs={
            **FILTER_INPUTS,  # cat_values, num_values, visible_list
            **PICKER_3D_INPUTS,  # slider_picker_3d, x_picker_3d, etc.
            **TRIGGER_INPUTS,  # unused triggers
            "c_key": Input("c-picker-3d", "value"),
        },
        state={
            **ANIMATION_STATE,  # ispaused, slider_arg, decay
            **VISUAL_STATE,  # overlay_enable, colormap
            **COMMON_STATE,  # size_vary, darkmode, session_id, file, file_list
            "trigger_val": State("background-trigger", "data"),
            "data_path": State("data-path", "value"),
            "case": State("test-case", "value"),
        },
        prevent_initial_call=True,
    )
    def regenerate_figure_callback(
        # Filter inputs
        cat_values: list,
        num_values: list,
        visible_list: list,
        # Picker 3D inputs
        slider_picker_3d: str,
        x_picker_3d: str,
        y_picker_3d: str,
        z_picker_3d: str,
        x_ref_picker_3d: str,
        y_ref_picker_3d: str,
        z_ref_picker_3d: str,
        # Trigger inputs
        unused_vistable_trigger: int,
        unused_left_hide_trigger: int,
        unused_right_hide_trigger: int,
        unused_file_loaded: int,
        # Other inputs
        c_key: str,
        # Animation state
        ispaused: bool,
        slider_arg: int,
        decay: int,
        # Visual state
        overlay_enable: list,
        colormap: str,
        # Common state
        size_vary: str,
        darkmode: list,
        session_id: str,
        file: str,
        file_list: list,
        # Additional state
        trigger_val: int,
        data_path: str,
        case: str,
    ) -> dict:
        """
        Regenerate the 3D scatter plot figure.

        Args:
            cat_values (list): Selected categorical filter values
            num_values (list): Selected numerical filter values
            visible_list (list): List of visible elements
            slider_picker_3d (str): Selected slider for 3D plot
            x_picker_3d (str): Selected x-axis for 3D plot
            y_picker_3d (str): Selected y-axis for 3D plot
            z_picker_3d (str): Selected z-axis for 3D plot
            x_ref_picker_3d (str): Selected x-reference for 3D plot
            y_ref_picker_3d (str): Selected y-reference for 3D plot
            z_ref_picker_3d (str): Selected z-reference for 3D plot
            unused_vistable_trigger (int): Visibility table trigger
            unused_left_hide_trigger (int): Left hide trigger
            unused_right_hide_trigger (int): Right hide trigger
            unused_file_loaded (int): File loaded trigger
            c_key (str): Selected color key
            ispaused (bool): Animation pause state
            slider_arg (int): Current slider position
            decay (int): Number of past frames to show
            overlay_enable (list): Overlay mode enable state
            colormap (str): Selected colormap name
            size_vary (str): Size variation enable state
            darkmode (list): Dark mode enable state
            session_id (str): Session identifier
            file (str): Current file path
            file_list (list): List of all file paths
            trigger_val (int): Current trigger value
            data_path (str): Data path for configuration
            case (str): Test case name

        Returns:
            dict: Updated figure data and trigger values
        """
        # invoke task
        cache_set(-1, session_id, CACHE_KEYS["task_id"])
        cache_set(-1, session_id, CACHE_KEYS["figure_idx"])

        # save filter key word arguments to Redis
        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        filter_kwargs["num_values"] = num_values
        filter_kwargs["cat_values"] = cat_values
        cache_set(filter_kwargs, session_id, CACHE_KEYS["filter_kwargs"])

        if file not in file_list:
            file_list.append(file)

        # get config from Redis
        config = cache_get(session_id, CACHE_KEYS["config"])
        config["slider"] = slider_picker_3d
        config["x_3d"] = x_picker_3d
        config["y_3d"] = y_picker_3d
        config["z_3d"] = z_picker_3d
        config["x_ref"] = x_ref_picker_3d
        config["y_ref"] = y_ref_picker_3d
        config["z_ref"] = z_ref_picker_3d
        cache_set(config, session_id, CACHE_KEYS["config"])
        # save the config to os.path.join(data_path, case, "info.json"
        with open(
            os.path.join(data_path, case, "info.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(config, f, indent=4)

        if overlay_enable:
            fig = process_overlay_frame(
                slider_arg,
                config,
                cat_values,
                num_values,
                colormap,
                visible_list,
                c_key,
                bool(size_vary),
                session_id,
                file,
                file_list,
            )
        else:
            fig = process_single_frame(
                config,
                cat_values,
                num_values,
                colormap,
                visible_list,
                c_key,
                bool(size_vary),
                decay,
                session_id,
                file,
                slider_arg,
                ispaused,
            )

        if darkmode:
            fig["layout"]["template"] = pio.templates["plotly_dark"]
        else:
            fig["layout"]["template"] = pio.templates["plotly"]

        return {"scatter3d": fig, "trigger": trigger_val + 1, "local_buffer_idx": -1}

    @app.callback(
        background=True,
        output={
            "dummy": Output("dummy-background", "data"),
        },
        inputs={
            "trigger_idx": Input("background-trigger", "data"),
        },
        state={
            **FILTER_STATE,  # cat_values, num_values, visible_list
            "c_key": State("c-picker-3d", "value"),
            "session_id": State("session-id", "data"),
            "file": State("current-file", "data"),
            "file_list": State("file-add", "value"),
        },
        cancel=[Input("background-trigger", "data")],
        progress=[
            Output("buffer", "value"),
            Output("buffer-tooltip", "children"),
        ],
        manager=background_callback_manager,
        prevent_initial_call=True,
    )
    def regenerate_figure_background_callback(
        set_progress: Callable,
        trigger_idx: int,
        cat_values: list,
        num_values: list,
        visible_list: list,
        c_key: str,
        session_id: str,
        file: str,
        file_list: list,
    ) -> dict:
        """
        Background task for regenerating the 3D scatter plot.

        Args:
            set_progress (callable): Progress update function
            trigger_idx (int): Task trigger index
            cat_values (list): Selected categorical filter values
            num_values (list): Selected numerical filter values
            visible_list (list): List of visible elements
            c_key (str): Selected color key
            session_id (str): Session identifier
            file (str): Current file path
            file_list (list): List of all file paths

        Returns:
            dict: Dummy output for completion
        """
        cache_set(trigger_idx, session_id, CACHE_KEYS["task_id"])
        print("start new task (" + str(trigger_idx) + ")")

        set_progress([0, "Buffering ... (0 %)"])

        cache_expire()

        if file not in file_list:
            file_list.append(file)

        # set figure index to -1 (no buffer is ready)
        cache_set(-1, session_id, CACHE_KEYS["figure_idx"])

        config = cache_get(session_id, CACHE_KEYS["config"])
        keys_dict = config["keys"]

        slider_label = keys_dict[config["slider"]]["description"]

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]

        visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])
        # frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])

        dataset = load_data(file_list)
        dataset[config["slider"]] = dataset[config["slider"]].astype(int)
        frame_list = np.sort(dataset[config["slider"]].unique())
        cache_set(frame_list, session_id, CACHE_KEYS["frame_list"])

        frame_group = dataset.groupby(config["slider"])

        # prepare figure key word arguments
        fig_kwargs = prepare_figure_kwargs(
            config,
            num_keys,
            num_values,
            c_key,
            False,
            frame_list,
        )

        for slider_arg, frame_idx in enumerate(frame_list):
            file = json.loads(file_list[0])
            img_path = os.path.join(
                file["path"], file["name"][0:-4], str(frame_list[slider_arg]) + ".jpg"
            )

            # encode image frame
            fig_kwargs["image"] = load_image(img_path)

            fig_kwargs["name"] = (
                "Index: "
                + str(slider_arg)
                + " ("
                + slider_label
                + ": "
                + str(frame_idx)
                + ")"
            )

            data = frame_group.get_group(frame_idx)
            filterd_frame = filter_all(
                data,
                num_keys,
                num_values,
                cat_keys,
                cat_values,
                visible_table,
                visible_list,
            )

            result = get_scatter3d_data(filterd_frame, hover=keys_dict, **fig_kwargs)
            fig = result["scatter_data"]
            hover_strings = result["hover_strings"]

            if fig_kwargs["x_ref"] is not None and fig_kwargs["y_ref"] is not None:
                ref_fig = [
                    get_ref_scatter3d_data(
                        data_frame=filterd_frame,
                        x_key=fig_kwargs["x_ref"],
                        y_key=fig_kwargs["y_ref"],
                        z_key=fig_kwargs["z_ref"],
                        name=fig_kwargs.get("ref_name", None),
                    )
                ]
            else:
                ref_fig = []

            fig_layout = get_scatter3d_layout(**fig_kwargs)

            if trigger_idx != cache_get(session_id, CACHE_KEYS["task_id"]):
                print("task (" + str(trigger_idx) + ") cancelled")
                set_progress([0, "Buffering ... (0 %)"])
                return {"dummy": 0}

            cache_set(slider_arg, session_id, CACHE_KEYS["figure_idx"])
            cache_set(fig, session_id, CACHE_KEYS["figure"], str(slider_arg))
            cache_set(hover_strings, session_id, CACHE_KEYS["hover"], str(slider_arg))
            cache_set(ref_fig, session_id, CACHE_KEYS["figure_ref"], str(slider_arg))
            cache_set(
                fig_layout, session_id, CACHE_KEYS["figure_layout"], str(slider_arg)
            )

            percent = slider_arg / len(frame_list) * 100
            set_progress(
                [
                    percent,
                    "Buffering ... (" + str(round(percent, 2)) + " %)",
                ]
            )

        set_progress([100, "Buffer ready (100 %)"])

        print("task (" + str(trigger_idx) + ") completed")

        return {"dummy": 0}

    @app.callback(
        output={"filter_trigger": Output("filter-trigger", "data")},
        inputs={
            "unused_cat_values": Input(
                {"type": "filter-dropdown", "index": ALL}, "value"
            ),
            "unused_num_values": Input(
                {"type": "filter-slider", "index": ALL}, "value"
            ),
            "unused_visible_list": Input("visible-picker", "value"),
            "unused_vistable_trigger": Input("visible-table-change-trigger", "data"),
            "unused_file_loaded": Input("file-loaded-trigger", "data"),
        },
        state={
            "trigger_idx": State("filter-trigger", "data"),
        },
    )
    def invoke_filter_trigger(
        unused_cat_values: list,
        unused_num_values: list,
        unused_visible_list: list,
        unused_vistable_trigger: int,
        unused_file_loaded: int,
        trigger_idx: int,
    ) -> dict:
        """
        Increment the filter trigger counter.

        Args:
            unused_cat_values (list): Categorical filter values
            unused_num_values (list): Numerical filter values
            unused_visible_list (list): Visible elements list
            unused_vistable_trigger (int): Visibility table trigger
            unused_file_loaded (int): File loaded trigger
            trigger_idx (int): Current trigger value

        Returns:
            dict: Incremented trigger value
        """
        filter_trig = trigger_idx + 1

        return {"filter_trigger": filter_trig}

    @app.callback(
        background=True,
        output={"download": Output("download", "data", allow_duplicate=True)},
        inputs={"btn": Input("export-scatter3d", "n_clicks")},
        state={
            "case": State("test-case", "value"),
            "session_id": State("session-id", "data"),
            "c_key": State("c-picker-3d", "value"),
            "size_vary": State("size-vary-switch", "value"),
            "colormap": State("colormap-3d", "value"),
            "visible_list": State("visible-picker", "value"),
            "file": State("current-file", "data"),
            "file_list": State("file-add", "value"),
            "decay": State("decay-slider", "value"),
            "darkmode": State("darkmode-switch", "value"),
        },
        cancel=[Input("background-trigger", "data")],
        progress=[
            Output("export-spinner", "display"),
        ],
        manager=background_callback_manager,
        prevent_initial_call=True,
    )
    def export_3d_scatter_animation(
        set_progress: Callable,
        btn: int,
        case: str,
        session_id: str,
        c_key: str,
        size_vary: str,
        colormap: str,
        visible_list: list,
        file: str,
        file_list: list,
        decay: int,
        darkmode: list,
    ) -> dict:
        """
        Export 3D scatter plot animation to HTML file.

        Args:
            btn (int): Button click count
            case (str): Test case name
            session_id (str): Session identifier
            c_key (str): Selected color key
            colormap (str): Selected colormap name
            visible_list (list): List of visible elements
            file (str): Current file path
            file_list (list): List of all file paths
            decay (int): Number of past frames to show
            darkmode (list): Dark mode enable state

        Returns:
            dict: Dummy output for completion

        Raises:
            PreventUpdate: If button not clicked
        """
        if btn == 0:
            raise PreventUpdate

        set_progress(["show"])

        if not os.path.exists("data/" + case + "/images"):
            os.makedirs("data/" + case + "/images")

        config = cache_get(session_id, CACHE_KEYS["config"])
        keys_dict = config["keys"]
        c_type = keys_dict[c_key].get("type", KEY_TYPES["NUM"])

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]
        num_values = filter_kwargs["num_values"]
        cat_values = filter_kwargs["cat_values"]

        frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])

        fig_kwargs = prepare_figure_kwargs(
            config,
            num_keys,
            num_values,
            c_key,
            bool(size_vary),
            frame_list,
        )

        if darkmode:
            fig_kwargs["template"] = "plotly_dark"
        else:
            fig_kwargs["template"] = "plotly"

        if file not in file_list:
            file_list.append(file)

        visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])

        dataset = load_data(file_list)
        filtered_table = filter_all(
            dataset,
            num_keys,
            num_values,
            cat_keys,
            cat_values,
            visible_table,
            visible_list,
        )

        img_list = []

        for _, f_val in enumerate(frame_list):
            file = json.loads(file_list[0])
            img_list.append(
                os.path.join(file["path"], file["name"][0:-4], str(f_val) + ".jpg")
            )

        fig_kwargs["title"] = file["name"][0:-4]

        fig_kwargs["height"] = 750

        fig_kwargs["decay"] = decay
        fig_kwargs["c_type"] = c_type
        fig_kwargs["keys_dict"] = keys_dict

        fig = go.Figure(
            get_animation_data(
                filtered_table,
                frame_key=config["slider"],
                img_list=img_list,
                colormap=colormap,
                dark_mode=darkmode,
                **fig_kwargs
            )
        )

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        file_name = "temp/" + timestamp + "_" + file["name"][0:-4] + "_3dview.html"

        fig.write_html(file_name)

        set_progress(["hide"])

        return {"download": dcc.send_file(file_name)}

    @app.callback(
        output={"download": Output("download", "data", allow_duplicate=True)},
        inputs={"btn": Input("export-scatter3d-html", "n_clicks")},
        state={
            "fig": State("scatter3d", "figure"),
        },
        prevent_initial_call=True,
    )
    def export_3d_scatter_html(btn: int, fig: dict) -> dict:
        """
        Export current 3D scatter plot to HTML file.

        Args:
            btn (int): Button click count
            fig (dict): Current figure dictionary

        Returns:
            dict: Download data for file

        Raises:
            PreventUpdate: If button not clicked
        """
        if btn == 0:
            raise PreventUpdate

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        if not os.path.exists("temp"):
            os.mkdir("temp")

        file_name = "temp/" + timestamp + "_3dscatter.html"

        temp_fig = go.Figure(fig)
        temp_fig.write_html(file_name)

        return {"download": dcc.send_file(file_name)}

    @app.callback(
        output={"download": Output("download", "data", allow_duplicate=True)},
        inputs={"btn": Input("export-scatter3d-png", "n_clicks")},
        state={
            "fig": State("scatter3d", "figure"),
        },
        prevent_initial_call=True,
    )
    def export_3d_scatter_png(btn: int, fig: dict) -> dict:
        """
        Export current 3D scatter plot to PNG image.

        Args:
            btn (int): Button click count
            fig (dict): Current figure dictionary

        Returns:
            dict: Download data for file

        Raises:
            PreventUpdate: If button not clicked
        """
        if btn == 0:
            raise PreventUpdate

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        if not os.path.exists("temp"):
            os.mkdir("temp")

        file_name = "temp/" + timestamp + "_3dscatter.png"

        temp_fig = go.Figure(fig)
        temp_fig.write_image(file_name, scale=2)

        return {"download": dcc.send_file(file_name)}

    @app.callback(
        output={"download": Output("download", "data", allow_duplicate=True)},
        inputs={"btn": Input("export-data-all", "n_clicks")},
        state={
            "session_id": State("session-id", "data"),
            "visible_list": State("visible-picker", "value"),
            "file": State("current-file", "data"),
            "file_list": State("file-add", "value"),
        },
        prevent_initial_call=True,
    )
    def export_all_frame_data(
        btn: int, session_id: str, visible_list: list, file: str, file_list: list
    ) -> dict:
        """
        Export data from all frames to CSV file.

        Args:
            btn (int): Button click count
            session_id (str): Session identifier
            visible_list (list): List of visible elements
            file (str): Current file path
            file_list (list): List of all file paths

        Returns:
            dict: Download data for file

        Raises:
            PreventUpdate: If button not clicked
        """
        if btn == 0:
            raise PreventUpdate

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        if filter_kwargs is None:
            raise PreventUpdate
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]
        cat_values = filter_kwargs["cat_values"]
        num_values = filter_kwargs["num_values"]

        # file = json.loads(file)
        data = load_data(file_list, file)
        visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])

        filtered_table = filter_all(
            data,
            num_keys,
            num_values,
            cat_keys,
            cat_values,
            visible_table,
            visible_list,
        )
        file = json.loads(file)

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        file_name = "temp/" + file["name"][0:-4] + "_" + timestamp + ".csv"

        filtered_table.to_csv(
            file_name,
            index=False,
        )

        return {"download": dcc.send_file(file_name)}

    @app.callback(
        output={"download": Output("download", "data", allow_duplicate=True)},
        inputs={"btn": Input("export-data-current", "n_clicks")},
        state={
            "slider_arg": State("slider-frame", "value"),
            "session_id": State("session-id", "data"),
            "visible_list": State("visible-picker", "value"),
            "file": State("current-file", "data"),
        },
        prevent_initial_call=True,
    )
    def export_current_frame_data(
        btn: int, slider_arg: int, session_id: str, visible_list: list, file: str
    ) -> dict:
        """
        Export data from current frame to CSV file.

        Args:
            btn (int): Button click count
            slider_arg (int): Current slider position
            session_id (str): Session identifier
            visible_list (list): List of visible elements
            file (str): Current file path

        Returns:
            dict: Download data for file

        Raises:
            PreventUpdate: If button not clicked
        """
        if btn == 0:
            raise PreventUpdate

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]
        cat_values = filter_kwargs["cat_values"]
        num_values = filter_kwargs["num_values"]

        # file = json.loads(file)
        frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])
        data = cache_get(
            session_id, CACHE_KEYS["frame_data"], str(frame_list[slider_arg])
        )
        visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])

        filtered_table = filter_all(
            data,
            num_keys,
            num_values,
            cat_keys,
            cat_values,
            visible_table,
            visible_list,
        )
        file = json.loads(file)

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        file_name = "temp/" + file["name"][0:-4] + "_" + timestamp + ".csv"

        filtered_table.to_csv(
            file_name,
            index=False,
        )

        return {"download": dcc.send_file(file_name)}

    @app.callback(Output("relayout-data", "data"), Input("scatter3d", "relayoutData"))
    def display_relayout_data(relayout_data):
        return relayout_data
