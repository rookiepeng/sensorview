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

import os

import datetime

import pandas as pd

import plotly.graph_objs as go
import plotly.express as px

from dash import dcc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from app_config import background_callback_manager
from app_config import CACHE_KEYS

from utils import filter_all
from utils import cache_get
from utils import load_data


def get_histogram_view_callbacks(app):
    """
    Register the callback functions for the histogram view.

    Parameters:
    - app (Dash app): The Dash app.

    Returns:
    - None
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
        unused_filter_trigger,
        unused_left_hide_trigger,
        unused_right_hide_trigger,
        histogram_sw,
        x_histogram,
        y_histogram,
        c_histogram,
        session_id,
        visible_list,
        file,
        file_list,
    ):
        """
        Background callback function to regenerate the histogram figure based on the input values.

        Parameters:
        - unused_filter_trigger (any): Unused input trigger for filtering data.
        - unused_left_hide_trigger (any): Unused input trigger for hiding left panel.
        - histogram_sw (bool): The value of the histogram switch.
        - x_histogram (str): The selected x-axis key for the histogram.
        - y_histogram (str): The selected y-axis key for the histogram.
        - c_histogram (str): The selected color key for the histogram.
        - session_id (str): The ID of the current session.
        - visible_list (list): The list of visible items.
        - file (str): The selected file.
        - file_list (list): The list of selected files.

        Returns:
        - dict: A dictionary containing the updated histogram figure.

        Output Properties:
        - histogram (dict): The updated histogram figure.
        """
        if not histogram_sw:
            histogram_fig = {"data": [{"type": "histogram", "x": []}], "layout": {}}

            return {
                "histogram": histogram_fig,
            }

        config = cache_get(session_id, CACHE_KEYS["config"])

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
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
        if c_histogram == "None":
            if x_key == config["slider"]:
                nbins = pd.unique(filtered_table[x_key]).size
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
                nbins = pd.unique(filtered_table[x_key]).size
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
        histogram_sw,
    ):
        """
        Callback function to enable or disable the histogram collapse.

        Parameters:
        - histogram_sw (bool): The value of the histogram switch.

        Returns:
        - dict: A dictionary containing the updated value for the collapse property.

        Output Properties:
        - collapse (bool): Whether the histogram should be collapsed or not.
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
    def export_histogram(btn, fig):
        """
        Callback function to export the histogram figure as an image.

        Parameters:
        - btn (int): The number of times the export button has been clicked.
        - fig (dict): The histogram figure.

        Returns:
        - dict: A dictionary containing a dummy value for the output property.

        Output Properties:
        - dummy (int): A dummy value to trigger the export.
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
