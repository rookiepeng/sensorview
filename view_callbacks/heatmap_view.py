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

import plotly.graph_objs as go

from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from viz.viz import get_heatmap

from dash_config import background_callback_manager
from dash_config import CACHE_KEYS

from utils import filter_all
from utils import cache_get
from utils import load_data


def get_heatmap_view_callbacks(app):
    """
    Register the callback functions for the heatmap view.

    Parameters:
    - app (Dash app): The Dash app.

    Returns:
    - None
    """

    @app.callback(
        background=True,
        output={
            "heatmap": Output("heatmap", "figure"),
        },
        inputs={
            "unused_filter_trigger": Input("filter-trigger", "data"),
            "unused_left_hide_trigger": Input("left-hide-trigger", "data"),
            "heat_sw": Input("heat-switch", "value"),
            "x_heat": Input("x-picker-heatmap", "value"),
            "y_heat": Input("y-picker-heatmap", "value"),
        },
        state={
            "session_id": State("session-id", "data"),
            "visible_list": State("visible-picker", "value"),
            "case": State("case-picker", "value"),
            "file": State("file-picker", "value"),
            "file_list": State("file-add", "value"),
        },
        manager=background_callback_manager,
    )
    def regenerate_heatmap_callback(
        unused_filter_trigger,
        unused_left_hide_trigger,
        heat_sw,
        x_heat,
        y_heat,
        session_id,
        visible_list,
        case,
        file,
        file_list,
    ):
        """
        Background callback function to regenerate the heatmap figure based on the input values.

        Parameters:
        - unused_filter_trigger (any): Unused input trigger for filtering data.
        - unused_left_hide_trigger (any): Unused input trigger for hiding left panel.
        - heat_sw (bool): The value of the heat switch.
        - x_heat (str): The selected x-axis key for the heatmap.
        - y_heat (str): The selected y-axis key for the heatmap.
        - session_id (str): The ID of the current session.
        - visible_list (list): The list of visible items.
        - case (str): The selected case.
        - file (str): The selected file.
        - file_list (list): The list of selected files.

        Returns:
        - dict: A dictionary containing the updated heatmap figure.

        Output Properties:
        - heatmap (dict): The updated heatmap figure.
        """
        if not heat_sw:
            heat_fig = {"data": [{"type": "histogram2dcontour", "x": []}], "layout": {}}

            return {
                "heatmap": heat_fig,
            }

        config = cache_get(session_id, CACHE_KEYS["config"])

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]
        cat_values = filter_kwargs["cat_values"]
        num_values = filter_kwargs["num_values"]

        x_key = x_heat
        x_label = config["keys"][x_heat]["description"]
        y_key = y_heat
        y_label = config["keys"][y_heat]["description"]

        data = load_data(file, file_list, case)
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
        heat_sw,
    ):
        """
        Callback function to enable or disable the heatmap collapse.

        Parameters:
        - heat_sw (bool): The value of the heat switch.

        Returns:
        - dict: A dictionary containing the updated value for the collapse property.

        Output Properties:
        - collapse (bool): Whether the heatmap should be collapsed or not.
        """
        collapse = False
        if heat_sw:
            collapse = True

        return {"collapse": collapse}

    @app.callback(
        output={"dummy": Output("dummy-export-heatmap", "data")},
        inputs={"btn": Input("export-heatmap", "n_clicks")},
        state={
            "fig": State("heatmap", "figure"),
            "case": State("case-picker", "value"),
        },
    )
    def export_heatmap(btn, fig, case):
        """
        Callback function to export the heatmap figure as an image.

        Parameters:
        - btn (int): The number of times the export button has been clicked.
        - fig (dict): The heatmap figure.
        - case (str): The selected case.

        Returns:
        - dict: A dictionary containing a dummy value for the output property.

        Output Properties:
        - dummy (int): A dummy value to trigger the export.
        """
        if btn == 0:
            raise PreventUpdate

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        if not os.path.exists("data/" + case + "/images"):
            os.makedirs("data/" + case + "/images")

        temp_fig = go.Figure(fig)
        temp_fig.write_image(
            "data/" + case + "/images/" + timestamp + "_heatmap.png", scale=2
        )
        return {"dummy": 0}
