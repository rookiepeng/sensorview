"""SensorView Parallel Coordinates View Callbacks

This module provides callback functions for managing parallel coordinates visualization
in the SensorView application.

Core Features:
-------------
1. Visualization Management:
   - Dynamic parallel coordinates plot generation
   - Color mapping for dimensions
   - Interactive dimension selection
   - Plot visibility controls

2. UI Controls:
   - Dimension picker updates
   - Color dimension selection
   - Collapse panel management
   - Plot export functionality

3. Data Processing:
   - Data filtering and transformation
   - Categorical and numerical data handling
   - Color scale generation
   - Plot configuration

Dependencies:
------------
- dash & plotly
- numpy
- app_config settings
- Standard Python libraries

Usage:
------
Register callbacks with app instance:
    from view_callbacks.parcats_view import get_parcats_view_callbacks
    get_parcats_view_callbacks(app)

Author: Zhengyu Peng
Email: zpeng.me@gmail.com
Website: https://zpeng.me
License: GPL-3.0
"""

import os

import datetime

import numpy as np

import plotly.graph_objs as go

import dash
from dash import dcc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from app_config import background_callback_manager
from app_config import CACHE_KEYS

from utils import filter_all
from utils import cache_get
from utils import load_data


def get_parcats_view_callbacks(app: dash.Dash) -> None:
    """
    Register callback functions for parallel coordinates view.

    Args:
        app (dash.Dash): The Dash application instance

    Returns:
        None
    """

    @app.callback(
        background=True,
        output={
            "parallel": Output("parallel", "figure"),
        },
        inputs={
            "unused_filter_trigger": Input("filter-trigger", "data"),
            "unused_left_hide_trigger": Input("left-hide-trigger", "data"),
            "unused_right_hide_trigger": Input("right-hide-trigger", "data"),
            "parallel_sw": Input("parallel-switch", "value"),
            "dim_parallel": Input("dim-picker-parallel", "value"),
            "c_key": Input("c-picker-parallel", "value"),
        },
        state={
            "session_id": State("session-id", "data"),
            "visible_list": State("visible-picker", "value"),
            "file": State("current-file", "data"),
            "file_list": State("file-add", "value"),
        },
        manager=background_callback_manager,
    )
    def regenerate_parallel_callback(
        unused_filter_trigger: int,
        unused_left_hide_trigger: int,
        unused_right_hide_trigger: int,
        parallel_sw: list,
        dim_parallel: list,
        c_key: str,
        session_id: str,
        visible_list: list,
        file: str,
        file_list: list,
    ) -> dict:
        """
        Regenerate parallel coordinates plot based on user inputs.

        Args:
            unused_filter_trigger (int): Filter trigger count
            unused_left_hide_trigger (int): Left hide trigger count
            unused_right_hide_trigger (int): Right hide trigger count
            parallel_sw (list): Parallel coordinates switch state
            dim_parallel (list): Selected dimensions
            c_key (str): Selected color key
            session_id (str): Session identifier
            visible_list (list): List of visible elements
            file (str): Current file path
            file_list (list): List of all file paths

        Returns:
            dict: Contains:
                - parallel (dict): Updated parallel coordinates figure
        """
        if not parallel_sw:
            parallel_fig = {"data": [{"type": "histogram", "x": []}], "layout": {}}

            return {
                "parallel": parallel_fig,
            }

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]
        cat_values = filter_kwargs["cat_values"]
        num_values = filter_kwargs["num_values"]

        if len(dim_parallel) > 0:
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

            dims = []
            for _, dim_key in enumerate(dim_parallel):
                dims.append(
                    go.parcats.Dimension(values=filtered_table[dim_key], label=dim_key)
                )

            if c_key != "None":
                unique_list = np.sort(filtered_table[c_key].unique())

                if np.issubdtype(unique_list.dtype, np.integer) or np.issubdtype(
                    unique_list.dtype, np.floating
                ):
                    parallel_fig = go.Figure(
                        data=[
                            go.Parcats(
                                dimensions=dims,
                                line={
                                    "color": filtered_table[c_key],
                                    "colorbar": dict(title=c_key),
                                },
                                hoveron="color",
                                hoverinfo="count+probability",
                                arrangement="freeform",
                            )
                        ]
                    )
                else:
                    filtered_table["_C_"] = np.zeros_like(filtered_table[c_key])
                    for idx, var in enumerate(unique_list):
                        filtered_table.loc[filtered_table[c_key] == var, "_C_"] = idx

                    parallel_fig = go.Figure(
                        data=[
                            go.Parcats(
                                dimensions=dims,
                                line={"color": filtered_table["_C_"]},
                                hoverinfo="count+probability",
                                arrangement="freeform",
                            )
                        ]
                    )
            else:
                parallel_fig = go.Figure(
                    data=[go.Parcats(dimensions=dims, arrangement="freeform")]
                )
        else:
            parallel_fig = {"data": [{"type": "histogram", "x": []}], "layout": {}}

        return {
            "parallel": parallel_fig,
        }

    @app.callback(
        output={
            "collapse": Output("collapse-parallel", "is_open"),
        },
        inputs={
            "parallel_sw": Input("parallel-switch", "value"),
        },
    )
    def enable_parallel_callback(
        parallel_sw: list,
    ) -> dict:
        """
        Toggle parallel coordinates collapse element.

        Args:
            parallel_sw (list): Parallel coordinates switch state

        Returns:
            dict: Contains:
                - collapse (bool): New state of collapse element
        """
        collapse = False
        if parallel_sw:
            collapse = True

        return {"collapse": collapse}

    @app.callback(
        output={"download": Output("download", "data", allow_duplicate=True)},
        inputs={"btn": Input("export-parallel", "n_clicks")},
        state={
            "fig": State("parallel", "figure"),
        },
        prevent_initial_call=True,
    )
    def export_parallel(btn: int, fig: dict) -> dict:
        """
        Export parallel coordinates plot as PNG image.

        Args:
            btn (int): Button click count
            fig (dict): Current parallel coordinates figure

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

        file_name = "temp/" + timestamp + "_parallel.png"

        temp_fig = go.Figure(fig)
        temp_fig.write_image(file_name, scale=2)

        return {"download": dcc.send_file(file_name)}
