"""SensorView 3D Scatter View Interactive Callbacks

This module provides interactive callback functions for the 3D scatter plot view in the
SensorView application. It handles real-time user interactions, UI state management,
and synchronous visualization updates that require immediate response.

Interactive Features:
--------------------
1. Real-time UI Controls:
   - Slider position changes and frame navigation
   - Configuration panel toggle and visibility
   - Color picker and colormap selection
   - Theme switching (dark/light mode)
   - Size variation and overlay mode controls

2. User Interaction Handling:
   - Click-to-hide functionality with point selection
   - Visibility table management from user clicks
   - Configuration collapse panel interactions
   - Export button handling for immediate operations

3. Synchronous Data Operations:
   - Filter parameter updates and validation
   - Figure regeneration triggers
   - Cache management for UI state
   - Configuration persistence to JSON files

4. Export Functionality:
   - Static HTML export of current view
   - PNG image export with high resolution
   - CSV data export for current and all frames
   - Timestamped file generation

Core Callback Functions:
-----------------------
- toggle_3d_config_collapse(): UI panel visibility control
- slider_change_callback(): Frame navigation and overlay processing
- colormap_change_callback(): Real-time colormap updates
- darkmode_change_callback(): Theme switching
- size_vary_callback(): Point size variation control
- visible_table_change_callback(): Click-to-hide interactions
- regenerate_figure_callback(): Main figure regeneration orchestrator
- export_*_callbacks(): Various export operations

Dependencies:
------------
- dash: Web application framework and callback decorators
- plotly: 3D visualization, graph objects, and I/O operations
- app_config: Application configuration and cache key management
- utils: Data loading, filtering, and caching utilities
- process_frame: Frame processing for single and overlay modes

Usage:
------
Register interactive callbacks with app instance:
    from view_callbacks.scatter_3d_view import get_scatter_3d_view_callbacks
    get_scatter_3d_view_callbacks(app)

Note: This module handles synchronous operations that require immediate UI response.
For computationally intensive background operations, see scatter_3d_view_background.py.

Author: Zhengyu Peng
Email: zpeng.me@gmail.com
Website: https://zpeng.me
License: GPL-3.0
"""

from typing import List, Tuple
import json
import os
import datetime

import dash
from dash.dcc import send_file  # pyright: ignore[reportPrivateImportUsage]
from dash.dependencies import Input, Output, State, ALL
from dash.exceptions import PreventUpdate
import plotly.io as pio
import plotly.graph_objs as go

from app_config import CACHE_KEYS, KEY_TYPES

from utils import filter_all
from utils import cache_set, cache_get
from utils import load_data

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
            "slider_arg": State("slider-frame", "value"),
            "ispaused": State("interval-component", "disabled"),
            "decay": State("decay-slider", "value"),
            "cat_values": State({"type": "filter-dropdown", "index": ALL}, "value"),
            "num_values": State({"type": "filter-slider", "index": ALL}, "value"),
            "visible_list": State("visible-picker", "value"),
            "colormap": State("colormap-3d", "value"),
            "c_key": State("c-picker-3d", "value"),
            "size_vary": State("size-vary-switch", "value"),
            "darkmode": State("darkmode-switch", "value"),
            "session_id": State("session-id", "data"),
            "file": State("current-file", "data"),
            "file_list": State("file-add", "value"),
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
        cat_values: List[List[str]],
        num_values: List[Tuple[float, float]],
        visible_list: list,
        # Visual state parameters
        colormap: str,
        c_key: str,
        size_vary: str,
        darkmode: list,
        # Common state parameters
        session_id: str,
        file: str,
        file_list: list,
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
                size_vary,
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
                size_vary,
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
            "cat_values": Input({"type": "filter-dropdown", "index": ALL}, "value"),
            "num_values": Input({"type": "filter-slider", "index": ALL}, "value"),
            "visible_list": Input("visible-picker", "value"),
            "slider_picker_3d": Input("slider-picker-3d", "value"),
            "x_picker_3d": Input("x-picker-3d", "value"),
            "y_picker_3d": Input("y-picker-3d", "value"),
            "z_picker_3d": Input("z-picker-3d", "value"),
            "x_ref_picker_3d": Input("x-ref-picker-3d", "value"),
            "y_ref_picker_3d": Input("y-ref-picker-3d", "value"),
            "z_ref_picker_3d": Input("z-ref-picker-3d", "value"),
            "unused_vistable_trigger": Input("visible-table-change-trigger", "data"),
            "unused_left_hide_trigger": Input("left-hide-trigger", "data"),
            "unused_right_hide_trigger": Input("right-hide-trigger", "data"),
            "unused_file_loaded": Input("file-loaded-trigger", "data"),
            "c_key": Input("c-picker-3d", "value"),
        },
        state={
            "slider_arg": State("slider-frame", "value"),
            "ispaused": State("interval-component", "disabled"),
            "decay": State("decay-slider", "value"),
            "colormap": State("colormap-3d", "value"),
            "overlay_enable": State("overlay-switch", "value"),
            "size_vary": State("size-vary-switch", "value"),
            "darkmode": State("darkmode-switch", "value"),
            "session_id": State("session-id", "data"),
            "file": State("current-file", "data"),
            "file_list": State("file-add", "value"),
            "trigger_val": State("background-trigger", "data"),
            "data_path": State("data-path", "value"),
            "case": State("test-case", "value"),
        },
        prevent_initial_call=True,
    )
    def regenerate_figure_callback(
        # Filter inputs
        cat_values: List[List[str]],
        num_values: List[Tuple[float, float]],
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
        if filter_kwargs is None:
            filter_kwargs = {}
        filter_kwargs["num_values"] = num_values
        filter_kwargs["cat_values"] = cat_values
        cache_set(filter_kwargs, session_id, CACHE_KEYS["filter_kwargs"])

        if file not in file_list:
            file_list.append(file)

        # get config from Redis
        config = cache_get(session_id, CACHE_KEYS["config"])
        if config is None:
            raise PreventUpdate
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
                size_vary,
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
                size_vary,
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

        return {"download": send_file(file_name)}

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

        return {"download": send_file(file_name)}

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
        file_dict = json.loads(file)

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        file_name = "temp/" + file_dict["name"][0:-4] + "_" + timestamp + ".csv"

        filtered_table.to_csv(
            file_name,
            index=False,
        )

        return {"download": send_file(file_name)}

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
        if filter_kwargs is None:
            raise PreventUpdate
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]
        cat_values = filter_kwargs["cat_values"]
        num_values = filter_kwargs["num_values"]

        # file = json.loads(file)
        frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])
        if frame_list is None:
            raise PreventUpdate
        data = cache_get(
            session_id, CACHE_KEYS["frame_data"], str(frame_list[slider_arg])
        )
        if data is None:
            raise PreventUpdate
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
        file_dict = json.loads(file)

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        file_name = "temp/" + file_dict["name"][0:-4] + "_" + timestamp + ".csv"

        filtered_table.to_csv(
            file_name,
            index=False,
        )

        return {"download": send_file(file_name)}

    @app.callback(Output("relayout-data", "data"), Input("scatter3d", "relayoutData"))
    def display_relayout_data(relayout_data):
        return relayout_data
