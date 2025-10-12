"""SensorView Histogram View Callbacks

This module provides callback functions for managing the histogram visualization in
the SensorView application, supporting data distribution analysis and filtering.

Core Features:
-------------
1. Histogram Generation:
   - Dynamic data binning
   - Multiple normalization options
   - Color-based grouping
   - Automatic range adjustment

2. View Controls:
   - Axis selection
   - Distribution mode switching
   - Category filtering
   - Export capabilities

3. Data Processing:
   - Filter application
   - Cache integration
   - Background processing
   - Results caching

Dependencies:
------------
- dash & plotly
- pandas
- app_config settings
- utils functions

Usage:
------
Register callbacks with app instance:
    from view_callbacks.histogram_view import get_histogram_view_callbacks
    get_histogram_view_callbacks(app)

Author: Zhengyu Peng
Email: zpeng.me@gmail.com
Website: https://zpeng.me
License: GPL-3.0
"""

import os

import datetime

import pandas as pd

import plotly.graph_objs as go
import plotly.express as px

import dash
from dash import dcc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from app_config import background_callback_manager
from app_config import CACHE_KEYS

from utils import filter_all
from utils import cache_get
from utils import load_data


def get_histogram_view_callbacks(app: dash.Dash) -> None:
    """
    Register callback functions for histogram view.

    Args:
        app (dash.Dash): The Dash application instance

    Returns:
        None
    """

    @app.callback(
        background=True,
        output={
            "histogram": Output("histogram", "figure"),
        },
        inputs={
            "unused_filter_trigger": Input("filter-trigger", "data"),
            "unused_left_hide_trigger": Input("left-hide-trigger", "data"),
            "unused_right_hide_trigger": Input("right-hide-trigger", "data"),
            "histogram_sw": Input("histogram-switch", "value"),
            "x_histogram": Input("x-picker-histogram", "value"),
            "y_histogram": Input("y-histogram", "value"),
            "c_histogram": Input("c-picker-histogram", "value"),
        },
        state={
            "session_id": State("session-id", "data"),
            "visible_list": State("visible-picker", "value"),
            "file": State("current-file", "data"),
            "file_list": State("file-add", "value"),
        },
        manager=background_callback_manager,
    )
    def regenerate_histogram_callback(
        unused_filter_trigger: int,
        unused_left_hide_trigger: int,
        unused_right_hide_trigger: int,
        histogram_sw: list,
        x_histogram: str,
        y_histogram: str,
        c_histogram: str,
        session_id: str,
        visible_list: list,
        file: str,
        file_list: list,
    ) -> dict:
        """
        Regenerate histogram based on user inputs.

        Args:
            unused_filter_trigger (int): Filter trigger count
            unused_left_hide_trigger (int): Left hide trigger count
            unused_right_hide_trigger (int): Right hide trigger count
            histogram_sw (list): Histogram switch state
            x_histogram (str): Selected x-axis key
            y_histogram (str): Selected y-axis type
            c_histogram (str): Selected color key
            session_id (str): Session identifier
            visible_list (list): List of visible elements
            file (str): Current file path
            file_list (list): List of all file paths

        Returns:
            dict: Contains:
                - histogram (dict): Updated histogram figure
        """
        if not histogram_sw:
            histogram_fig = {"data": [{"type": "histogram", "x": []}], "layout": {}}

            return {
                "histogram": histogram_fig,
            }

        config = cache_get(session_id, CACHE_KEYS["config"])
        if config is None:
            return {
                "histogram": {"data": [{"type": "histogram", "x": []}], "layout": {}},
            }

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        if filter_kwargs is None:
            return {
                "histogram": {"data": [{"type": "histogram", "x": []}], "layout": {}},
            }
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]
        cat_values = filter_kwargs["cat_values"]
        num_values = filter_kwargs["num_values"]

        x_key = x_histogram
        x_label = config["keys"][x_histogram]["description"]
        y_key = y_histogram

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

        if y_key == "probability":
            y_label = "Probability"
        elif y_key == "density":
            y_label = "Density"
        else:
            return {
                "histogram": dash.no_update,
            }

        if c_histogram == "None":
            if x_key == config["slider"]:
                nbins = len(pd.unique(filtered_table[x_key]))
                histogram_fig = px.histogram(
                    filtered_table,
                    x=x_key,
                    histnorm=y_key,
                    opacity=1,
                    barmode="group",
                    nbins=nbins,
                    labels={x_key: x_label, y_key: y_label},
                )
            else:
                histogram_fig = px.histogram(
                    filtered_table,
                    x=x_key,
                    histnorm=y_key,
                    opacity=1,
                    barmode="group",
                    labels={x_key: x_label, y_key: y_label},
                )
        else:
            if x_key == config["slider"]:
                nbins = len(pd.unique(filtered_table[x_key]))
                histogram_fig = px.histogram(
                    filtered_table,
                    x=x_key,
                    color=c_histogram,
                    histnorm=y_key,
                    opacity=1,
                    barmode="group",
                    nbins=nbins,
                    labels={x_key: x_label, y_key: y_label},
                )
            else:
                histogram_fig = px.histogram(
                    filtered_table,
                    x=x_key,
                    color=c_histogram,
                    histnorm=y_key,
                    opacity=1,
                    barmode="group",
                    labels={x_key: x_label, y_key: y_label},
                )

        return {
            "histogram": histogram_fig,
        }

    @app.callback(
        output={
            "collapse": Output("collapse-hist", "is_open"),
        },
        inputs={
            "histogram_sw": Input("histogram-switch", "value"),
        },
    )
    def enable_histogram_callback(
        histogram_sw: list,
    ) -> dict:
        """
        Toggle histogram collapse element.

        Args:
            histogram_sw (list): Histogram switch state

        Returns:
            dict: Contains:
                - collapse (bool): New state of collapse element
        """
        collapse = False
        if histogram_sw:
            collapse = True

        return {"collapse": collapse}

    @app.callback(
        output={"download": Output("download", "data", allow_duplicate=True)},
        inputs={"btn": Input("export-histogram", "n_clicks")},
        state={
            "fig": State("histogram", "figure"),
        },
        prevent_initial_call=True,
    )
    def export_histogram(btn: int, fig: dict) -> dict:
        """
        Export histogram as PNG image.

        Args:
            btn (int): Button click count
            fig (dict): Current histogram figure

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

        file_name = "temp/" + timestamp + "_histogram.png"

        temp_fig = go.Figure(fig)
        temp_fig.write_image(file_name, scale=2)

        return {"download": dcc.send_file(file_name)}
