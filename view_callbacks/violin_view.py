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

import plotly.express as px
import plotly.graph_objs as go

from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from app_config import background_callback_manager
from app_config import CACHE_KEYS

from utils import filter_all
from utils import cache_get
from utils import load_data


def get_violin_view_callbacks(app):
    """
    Register the callback functions for the violin view.

    Parameters:
    - app (Dash app): The Dash app.

    Returns:
    - None
    """

    @app.callback(
        background=True,
        output={
            "violin": Output("violin", "figure"),
        },
        inputs={
            "unused_filter_trigger": Input("filter-trigger", "data"),
            "unused_left_hide_trigger": Input("left-hide-trigger", "data"),
            "violin_sw": Input("violin-switch", "value"),
            "x_violin": Input("x-picker-violin", "value"),
            "y_violin": Input("y-picker-violin", "value"),
            "c_violin": Input("c-picker-violin", "value"),
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
    def regenerate_violin_callback(
        unused_filter_trigger,
        unused_left_hide_trigger,
        violin_sw,
        x_violin,
        y_violin,
        c_violin,
        session_id,
        visible_list,
        case,
        file,
        file_list,
    ):
        """
        Regenerate the violin plot based on user inputs.

        Parameters:
        - unused_filter_trigger (any): Unused filter trigger input.
        - unused_left_hide_trigger (any): Unused left hide trigger input.
        - violin_sw (bool): The violin switch value.
        - x_violin (str): The selected x-axis violin key.
        - y_violin (str): The selected y-axis violin key.
        - c_violin (str): The selected color key for the violin plot.
        - session_id (str): The session ID.
        - visible_list (list): The list of visible values.
        - case (str): The selected case.
        - file (str): The selected file.
        - file_list (list): The list of selected files.

        Returns:
        - dict: The output figure dictionary.
        """
        if not violin_sw:
            violin_fig = {"data": [{"type": "histogram", "x": []}], "layout": {}}

            return {"violin": violin_fig}

        config = cache_get(session_id, CACHE_KEYS["config"])

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]
        cat_values = filter_kwargs["cat_values"]
        num_values = filter_kwargs["num_values"]

        x_key = x_violin
        if x_violin is None:
            raise PreventUpdate

        x_label = config["keys"][x_violin].get("description", x_key)
        y_key = y_violin
        y_label = config["keys"][y_violin].get("description", y_key)

        data = load_data(file, file_list, case)
        visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])
        filtered_table = filter_all(
            data, num_keys, num_values, cat_keys, cat_values, visible_table, visible_list
        )

        if c_violin == "None":
            violin_fig = px.violin(
                filtered_table,
                x=x_key,
                y=y_key,
                box=True,
                violinmode="group",
                labels={x_key: x_label, y_key: y_label},
            )
        else:
            violin_fig = px.violin(
                filtered_table,
                x=x_key,
                y=y_key,
                color=c_violin,
                box=True,
                violinmode="group",
                labels={x_key: x_label, y_key: y_label},
            )

        return {"violin": violin_fig}


    @app.callback(
        output={
            "collapse": Output("collapse-violin", "is_open"),
        },
        inputs={
            "violin_sw": Input("violin-switch", "value"),
        },
    )
    def enable_violin_callback(
        violin_sw,
    ):
        """
        Enable or disable the violin plot collapse based on the violin switch value.

        Parameters:
        - violin_sw (bool): The violin switch value.

        Returns:
        - dict: The output collapse value.
        """
        collapse = False
        if violin_sw:
            collapse = True

        return {"collapse": collapse}


    @app.callback(
        output={"dummy": Output("dummy-export-violin", "data")},
        inputs={"btn": Input("export-violin", "n_clicks")},
        state={"fig": State("violin", "figure"), "case": State("case-picker", "value")},
    )
    def export_violin(btn, fig, case):
        """
        Export the violin plot as an image.

        Parameters:
        - btn (int): The number of clicks on the export button.
        - fig (dict): The figure dictionary of the violin plot.
        - case (str): The selected case.

        Returns:
        - dict: The output dummy data.
        """
        if btn == 0:
            raise PreventUpdate

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        if not os.path.exists("data/" + case + "/images"):
            os.makedirs("data/" + case + "/images")

        temp_fig = go.Figure(fig)
        temp_fig.write_image(
            "data/" + case + "/images/" + timestamp + "_violin.png", scale=2
        )
        return {"dummy": 0}
