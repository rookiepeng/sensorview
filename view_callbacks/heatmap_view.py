"""SensorView Heatmap View Callbacks

Callback functions for heatmap visualization including dynamic plot generation,
axis configuration, collapse panel management, and PNG export functionality.

Usage:
    from view_callbacks.heatmap_view import get_heatmap_view_callbacks
    get_heatmap_view_callbacks(app)

Author: Zhengyu Peng
License: GPL-3.0
"""

import os
import datetime

import plotly.graph_objs as go

import dash
from dash.dcc import send_file  # pyright: ignore[reportPrivateImportUsage]
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from viz.viz import get_heatmap

from app_config import background_callback_manager
from app_config import CACHE_KEYS

from utils import filter_all
from utils import cache_get
from utils import load_data


def get_heatmap_view_callbacks(app: dash.Dash) -> None:
    """
    Register callback functions for heatmap view.

    Args:
        app (dash.Dash): The Dash application instance

    Returns:
        None
    """

    @app.callback(
        background=True,
        output={
            "heatmap": Output("heatmap", "figure"),
        },
        inputs={
            "unused_filter_trigger": Input("filter-trigger", "data"),
            "unused_left_hide_trigger": Input("left-hide-trigger", "data"),
            "unused_right_hide_trigger": Input("right-hide-trigger", "data"),
            "heat_sw": Input("heat-switch", "value"),
            "x_heat": Input("x-picker-heatmap", "value"),
            "y_heat": Input("y-picker-heatmap", "value"),
            "log_scale": Input("heatmap-log-scale", "value"),
            "colormap": Input("colormap-heatmap", "value"),
        },
        state={
            "session_id": State("session-id", "data"),
            "visible_list": State("visible-picker", "value"),
            "file": State("current-file", "data"),
            "file_list": State("file-add", "value"),
        },
        manager=background_callback_manager,
        running=[
            (Output("loading_heat", "display"), "show", "hide"),
        ],
    )
    def regenerate_heatmap_callback(
        unused_filter_trigger: int,
        unused_left_hide_trigger: int,
        unused_right_hide_trigger: int,
        heat_sw: list,
        x_heat: str,
        y_heat: str,
        log_scale: list,
        colormap: str,
        session_id: str,
        visible_list: list,
        file: str,
        file_list: list,
    ) -> dict:
        """
        Regenerate heatmap based on user inputs.

        Args:
            unused_filter_trigger (int): Filter trigger count
            unused_left_hide_trigger (int): Left hide trigger count
            unused_right_hide_trigger (int): Right hide trigger count
            heat_sw (list): Heatmap switch state
            x_heat (str): Selected x-axis key
            y_heat (str): Selected y-axis key
            session_id (str): Session identifier
            visible_list (list): List of visible elements
            file (str): Current file path
            file_list (list): List of all file paths

        Returns:
            dict: Contains:
                - heatmap (dict): Updated heatmap figure
        """
        if not heat_sw:
            heat_fig = {"data": [{"type": "histogram2dcontour", "x": []}], "layout": {}}

            return {
                "heatmap": heat_fig,
            }

        config = cache_get(session_id, CACHE_KEYS["config"])
        if config is None:
            # Return empty heatmap if config is not available
            heat_fig = {"data": [{"type": "histogram2dcontour", "x": []}], "layout": {}}
            return {"heatmap": heat_fig}

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        if filter_kwargs is None:
            # Return empty heatmap if config is not available
            heat_fig = {"data": [{"type": "histogram2dcontour", "x": []}], "layout": {}}
            return {"heatmap": heat_fig}
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]
        cat_values = filter_kwargs["cat_values"]
        num_values = filter_kwargs["num_values"]

        x_key = x_heat
        x_label = config["keys"][x_heat]["description"]
        y_key = y_heat
        y_label = config["keys"][y_heat]["description"]

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

        heat_fig = get_heatmap(
            filtered_table,
            x_key,
            y_key,
            x_label,
            y_label,
            log_scale=bool(log_scale),
            colormap=colormap or "Jet",
        )

        return {
            "heatmap": heat_fig,
        }

    @app.callback(
        output={
            "collapse": Output("collapse-heatmap", "is_open"),
        },
        inputs={
            "heat_sw": Input("heat-switch", "value"),
        },
    )
    def enable_heatmap_callback(
        heat_sw: list,
    ) -> dict:
        """
        Toggle heatmap collapse element.

        Args:
            heat_sw (list): Heatmap switch state

        Returns:
            dict: Contains:
                - collapse (bool): New state of collapse element
        """
        collapse = False
        if heat_sw:
            collapse = True

        return {"collapse": collapse}

    @app.callback(
        output={"download": Output("download", "data", allow_duplicate=True)},
        inputs={"btn": Input("export-heatmap", "n_clicks")},
        state={
            "fig": State("heatmap", "figure"),
        },
        prevent_initial_call=True,
    )
    def export_heatmap(btn: int, fig: dict) -> dict:
        """
        Export heatmap as PNG image.

        Args:
            btn (int): Button click count
            fig (dict): Current heatmap figure

        Returns:
            dict: Contains:
                - download (send_file): File download data

        Raises:
            PreventUpdate: If button not clicked
        """
        if btn == 0:
            raise PreventUpdate

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        if not os.path.exists("temp"):
            os.mkdir("temp")

        file_name = "temp/" + timestamp + "_heatmap.png"

        temp_fig = go.Figure(fig)
        temp_fig.write_image(file_name, scale=2)

        return {"download": send_file(file_name)}
