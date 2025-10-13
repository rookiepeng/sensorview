"""SensorView Left 2D Scatter View Callbacks

This module provides callback functions for managing the left 2D scatter plot
visualization in the SensorView application.

Core Features:
-------------
1. View Management:
   - Real-time plot updates
   - Frame-based visualization
   - View state persistence
   - Dynamic colormap updates

2. Interaction Handling:
   - Selection management
   - Visibility toggling
   - Export capabilities
   - Frame navigation

3. Data Processing:
   - Data filtering
   - Cache integration
   - Frame-specific updates
   - All-frame mode support

Dependencies:
------------
- dash & plotly
- pandas
- app_config settings
- viz.viz components
- utils functions

Usage:
------
Register callbacks with app instance:
    from view_callbacks.scatter_2d_left_view import get_scatter_2d_left_view_callbacks
    get_scatter_2d_left_view_callbacks(app)

Author: Zhengyu Peng
Email: zpeng.me@gmail.com
Website: https://zpeng.me
License: GPL-3.0
"""

import os

import datetime

import pandas as pd

import plotly.graph_objs as go

import dash
from dash import dcc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from viz.viz import get_scatter2d

from app_config import background_callback_manager
from app_config import CACHE_KEYS, KEY_TYPES

from utils import filter_all
from utils import cache_set, cache_get
from utils import load_data


def get_scatter_2d_left_view_callbacks(app: dash.Dash) -> None:
    """
    Register the callback functions for the left 2D view.

    Args:
        app (dash.Dash): The Dash application instance

    Returns:
        None
    """

    @app.callback(
        output={"regenerate_trigger": Output("left-regenerate-trigger", "data")},
        inputs={
            "unused_slider_arg": Input("slider-frame", "value"),
            "unused_stop_click": Input("stop-button", "n_clicks"),
            "all_frame_sw": Input("scatter2dl-allframe-switch", "value"),
        },
        state={
            "ispaused": State("interval-component", "disabled"),
            "left_sw": State("left-switch", "value"),
            "current_regenerate_trigger": State("left-regenerate-trigger", "data"),
        },
    )
    def invoke_scatter2d_left_frame_trigger(
        unused_slider_arg: int,
        unused_stop_click: int,
        all_frame_sw: str,
        ispaused: bool,
        left_sw: list,
        current_regenerate_trigger: int,
    ) -> dict:
        """
        Invoke trigger to regenerate per-frame plot of left scatter2d figure.

        Args:
            unused_slider_arg (int): Current slider position
            unused_stop_click (int): Stop button click count
            all_frame_sw (str): Frame selection mode ('current' or 'all')
            ispaused (bool): Animation pause state
            left_sw (list): Left panel switch state
            current_regenerate_trigger (int): Current trigger value

        Returns:
            dict: Contains:
                - regenerate_trigger (int): Updated trigger value

        Raises:
            PreventUpdate: If conditions for regeneration are not met
        """

        ctx = dash.callback_context
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        if trigger_id == "stop-button":
            ispaused = True

        if ispaused and all_frame_sw == "current" and left_sw:
            trig = current_regenerate_trigger + 1

            return {"regenerate_trigger": trig}

        raise PreventUpdate

    @app.callback(
        background=True,
        output={
            "figure": Output("scatter2d-left", "figure", allow_duplicate=True),
        },
        inputs={
            "unused_filter_trigger": Input("filter-trigger", "data"),
            "unused_left_hide_trigger": Input("left-hide-trigger", "data"),
            "unused_right_hide_trigger": Input("right-hide-trigger", "data"),
            "unused_regenerate_trigger": Input("left-regenerate-trigger", "data"),
            "left_sw": Input("left-switch", "value"),
            "all_frame_sw": Input("scatter2dl-allframe-switch", "value"),
            "x_left": Input("x-picker-2d-left", "value"),
            "y_left": Input("y-picker-2d-left", "value"),
            "color_left": Input("c-picker-2d-left", "value"),
        },
        state={
            "slider_arg": State("slider-frame", "value"),
            "colormap": State("colormap-scatter2d-left", "value"),
            "session_id": State("session-id", "data"),
            "visible_list": State("visible-picker", "value"),
            "file": State("current-file", "data"),
            "file_list": State("file-add", "value"),
        },
        manager=background_callback_manager,
        prevent_initial_call=True,
    )
    def regenerate_scatter2d_left_callback(
        unused_filter_trigger: int,
        unused_left_hide_trigger: int,
        unused_right_hide_trigger: int,
        unused_regenerate_trigger: int,
        left_sw: list,
        x_left: str,
        y_left: str,
        color_left: str,
        slider_arg: int,
        all_frame_sw: str,
        colormap: str,
        session_id: str,
        visible_list: list,
        file: str,
        file_list: list,
    ) -> dict:
        """
        Regenerate the left 2D scatter plot.

        Args:
            unused_filter_trigger (int): Filter trigger count
            unused_left_hide_trigger (int): Left hide trigger count
            unused_right_hide_trigger (int): Right hide trigger count
            unused_regenerate_trigger (int): Regenerate trigger count
            left_sw (list): Left panel switch state
            x_left (str): Selected x-axis key
            y_left (str): Selected y-axis key
            color_left (str): Selected color key
            slider_arg (int): Current slider position
            all_frame_sw (str): Frame selection mode
            colormap (str): Selected colormap name
            session_id (str): Session identifier
            visible_list (list): List of visible elements
            file (str): Current file path
            file_list (list): List of all file paths

        Returns:
            dict: Contains:
                - figure (dict): Updated scatter plot figure
        """
        if not left_sw:
            left_fig = {
                "data": [{"mode": "markers", "type": "scattergl", "x": [], "y": []}],
                "layout": {},
            }

            return {"figure": left_fig}

        config = cache_get(session_id, CACHE_KEYS["config"])
        if config is None:
            raise PreventUpdate

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        if filter_kwargs is None:
            raise PreventUpdate
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]
        cat_values = filter_kwargs["cat_values"]
        num_values = filter_kwargs["num_values"]

        x_key = x_left
        y_key = y_left
        c_key = color_left
        x_label = config["keys"][x_left]["description"]
        y_label = config["keys"][y_left]["description"]
        c_label = config["keys"][color_left]["description"]

        if all_frame_sw == "all":
            data = load_data(file_list, file)
        else:
            frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])
            if frame_list is None:
                raise PreventUpdate
            data = cache_get(
                session_id, CACHE_KEYS["frame_data"], str(frame_list[slider_arg])
            )

        visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])

        if data is None:
            raise PreventUpdate

        filtered_table = filter_all(
            data,
            num_keys,
            num_values,
            cat_keys,
            cat_values,
            visible_table,
            visible_list,
        )

        left_fig = get_scatter2d(
            filtered_table,
            x_key,
            y_key,
            c_key,
            x_label,
            y_label,
            c_label,
            colormap=colormap,
            c_type=config["keys"][c_key].get("type", KEY_TYPES["NUM"]),
        )

        return {"figure": left_fig}

    @app.callback(
        output={
            "figure": Output("scatter2d-left", "figure", allow_duplicate=True),
        },
        inputs={
            "colormap": Input("colormap-scatter2d-left", "value"),
        },
        state={
            "fig_in": State("scatter2d-left", "figure"),
            "left_sw": State("left-switch", "value"),
        },
        prevent_initial_call=True,
    )
    def scatter2d_left_colormap_change_callback(
        colormap: str,
        fig_in: dict,
        left_sw: list,
    ) -> dict:
        """
        Update the colormap of the left 2D scatter plot.

        Args:
            colormap (str): Selected colormap name
            fig_in (dict): Current figure configuration
            left_sw (list): Left panel switch state

        Returns:
            dict: Contains:
                - figure (dict): Updated figure with new colormap
        """
        if not left_sw:
            left_fig = {
                "data": [{"mode": "markers", "type": "scattergl", "x": [], "y": []}],
                "layout": {},
            }

            return {
                "figure": left_fig,
            }

        for idx in range(0, len(fig_in["data"])):
            fig_in["data"][idx]["marker"]["colorscale"] = colormap

        return {
            "figure": fig_in,
        }

    @app.callback(
        output={
            "collapse": Output("collapse-left2d", "is_open"),
        },
        inputs={
            "left_sw": Input("left-switch", "value"),
        },
    )
    def enable_scatter2d_left_callback(left_sw: list) -> dict:
        """
        Toggle the left 2D scatter plot collapse element.

        Args:
            left_sw (list): Left panel switch state

        Returns:
            dict: Contains:
                - collapse (bool): New state of collapse element
        """
        collapse = False
        if left_sw:
            collapse = True

        return {"collapse": collapse}

    @app.callback(
        output={"download": Output("download", "data", allow_duplicate=True)},
        inputs={"btn": Input("export-scatter2d-left", "n_clicks")},
        state={
            "fig": State("scatter2d-left", "figure"),
        },
        prevent_initial_call=True,
    )
    def export_left_2d_scatter(btn: int, fig: dict) -> dict:
        """
        Export left 2D scatter plot as PNG image.

        Args:
            btn (int): Button click count
            fig (dict): Current figure configuration

        Returns:
            dict: Contains:
                - download (dcc.send_file): File download data

        Raises:
            PreventUpdate: If button not clicked
        """
        if btn == 0:
            raise PreventUpdate

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        if not os.path.exists("temp"):
            os.mkdir("temp")

        file_name = "temp/" + timestamp + "_fig_left.png"

        temp_fig = go.Figure(fig)
        temp_fig.write_image(file_name, scale=2)

        return {"download": dcc.send_file(file_name)}

    @app.callback(
        output={"dummy": Output("selected-data-left", "data")},
        inputs={"selected_data": Input("scatter2d-left", "selectedData")},
        state={"session_id": State("session-id", "data")},
    )
    def select_left_figure(selected_data: dict, session_id: str) -> dict:
        """
        Store selected data from left 2D scatter plot.

        Args:
            selected_data (dict): Selected points data
            session_id (str): Session identifier

        Returns:
            dict: Contains:
                - dummy (int): Update trigger value
        """
        cache_set(selected_data, session_id, CACHE_KEYS["selected_data_left"])
        return {"dummy": 0}

    @app.callback(
        output={"output_trigger": Output("left-hide-trigger", "data")},
        inputs={"btn": Input("hide-left", "n_clicks")},
        state={
            "trigger_idx": State("left-hide-trigger", "data"),
            "session_id": State("session-id", "data"),
        },
    )
    def left_hide_button(btn: int, trigger_idx: int, session_id: str) -> dict:
        """
        Toggle visibility of selected points in left plot.

        Args:
            btn (int): Button click count
            trigger_idx (int): Current trigger value
            session_id (str): Session identifier

        Returns:
            dict: Contains:
                - output_trigger (int): Updated trigger value

        Raises:
            PreventUpdate: If button not clicked or no selection
        """
        if btn == 0:
            raise PreventUpdate

        selected_data = cache_get(session_id, CACHE_KEYS["selected_data_left"])
        if selected_data is None or "points" not in selected_data:
            raise PreventUpdate

        visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])
        if visible_table is None:
            raise PreventUpdate

        # Extract selected point IDs more efficiently
        try:
            s_data = pd.DataFrame(selected_data["points"])
            if s_data.empty or "id" not in s_data.columns:
                raise PreventUpdate
            
            selected_ids = s_data["id"].values
        except (KeyError, ValueError, TypeError):
            raise PreventUpdate

        # Toggle visibility for selected points efficiently
        mask = visible_table.index.isin(selected_ids)
        current_visibility = visible_table.loc[mask, "_VIS_"]
        
        # Toggle: visible -> hidden, hidden -> visible
        visible_table.loc[mask, "_VIS_"] = current_visibility.map({
            "visible": "hidden",
            "hidden": "visible"
        }).fillna(current_visibility)  # Keep original value if not visible/hidden

        cache_set(visible_table, session_id, CACHE_KEYS["visible_table"])

        return {"output_trigger": trigger_idx + 1}
