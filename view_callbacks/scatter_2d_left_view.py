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


def get_scatter_2d_left_view_callbacks(app):
    """
    Register the callback functions for the left 2D view.

    Parameters:
    - app (Dash app): The Dash app.

    Returns:
    - None
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
        unused_slider_arg,
        unused_stop_click,
        all_frame_sw,
        ispaused,
        left_sw,
        current_regenerate_trigger,
    ):
        """
        Callback function to invoke the trigger to regenerate per-frame plot of
        left scatter2d figure.

        Parameters:
        - unused_slider_arg (int): The unused slider value.
        - unused_stop_click (int): The unused stop click value.
        - all_frame_sw (str): The selection between current frame of all frames.
        - ispaused (bool): If the video is paused.
        - left_sw (bool): If the figure is enabled.
        - current_regenerate_trigger (int): The current value of the trigger.

        Returns:
        - dict: A dictionary containing the updated filter trigger value.

        Output Properties:
        - regenerate_trigger (int): The updated filter trigger value.
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
        unused_filter_trigger,
        unused_left_hide_trigger,
        unused_regenerate_trigger,
        left_sw,
        x_left,
        y_left,
        color_left,
        slider_arg,
        all_frame_sw,
        colormap,
        session_id,
        visible_list,
        file,
        file_list,
    ):
        """
        Background callback function to regenerate the left 2D scatter plot
        based on the input values.

        Parameters:
        - unused_filter_trigger (any): Unused input trigger for filtering data.
        - unused_left_hide_trigger (any): Unused input trigger for hiding left
        panel.
        - unused_regenerate_trigger (any): Input trigger to update the per-frame plot.
        - left_sw (bool): The value of the left switch.
        - x_left (str): The selected x-axis key for the left scatter plot.
        - y_left (str): The selected y-axis key for the left scatter plot.
        - color_left (str): The selected color key for the left scatter plot.
        - colormap (str): The selected colormap for the left scatter plot.
        - session_id (str): The ID of the current session.
        - visible_list (list): The list of visible items.
        - file (str): The selected file.
        - file_list (list): The list of selected files.

        Returns:
        - dict: A dictionary containing the updated left 2D scatter plot figure.

        Output Properties:
        - figure (dict): The updated left 2D scatter plot figure.
        """
        if not left_sw:
            left_fig = {
                "data": [{"mode": "markers", "type": "scattergl", "x": [], "y": []}],
                "layout": {},
            }

            return {"figure": left_fig}

        config = cache_get(session_id, CACHE_KEYS["config"])

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
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
            data = load_data(file, file_list)
        else:
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
        colormap,
        fig_in,
        left_sw,
    ):
        """
        Callback function to update the colormap of the left 2D scatter plot.

        Parameters:
        - colormap (str): The selected colormap.
        - fig_in (dict): The current figure of the left 2D scatter plot.
        - left_sw (bool): The value of the left switch.

        Returns:
        - dict: A dictionary containing the updated figure of the left 2D scatter plot.

        Output Properties:
        - figure (dict): The updated figure of the left 2D scatter plot.
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
    def enable_scatter2d_left_callback(
        left_sw,
    ):
        """
        Callback function to enable or disable the left 2D scatter plot collapse.

        Parameters:
        - left_sw (bool): The value of the left switch.

        Returns:
        - dict: A dictionary containing the updated value for the collapse property.

        Output Properties:
        - collapse (bool): Whether the left 2D scatter plot should be collapsed or not.
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
    def export_left_2d_scatter(btn, fig):
        """
        Callback function to export the left 2D scatter plot as an image.

        Parameters:
        - btn (int): The number of times the export button has been clicked.
        - fig (dict): The left 2D scatter plot figure.

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

        file_name = "temp/" + timestamp + "_fig_left.png"

        temp_fig = go.Figure(fig)
        temp_fig.write_image(file_name, scale=2)

        return {"download": dcc.send_file(file_name)}

    @app.callback(
        output={"dummy": Output("selected-data-left", "data")},
        inputs={"selected_data": Input("scatter2d-left", "selectedData")},
        state={"session_id": State("session-id", "data")},
    )
    def select_left_figure(selected_data, session_id):
        """
        Callback function to store the selected data from the left 2D scatter plot.

        Parameters:
        - selectedData (dict): The selected data from the left 2D scatter plot.
        - session_id (str): The ID of the current session.

        Returns:
        - dict: A dictionary containing a dummy value for the output property.

        Output Properties:
        - dummy (int): A dummy value to trigger the update.
        """
        cache_set(selected_data, session_id, CACHE_KEYS["selected_data"])
        return {"dummy": 0}

    @app.callback(
        output={"output_trigger": Output("left-hide-trigger", "data")},
        inputs={"btn": Input("hide-left", "n_clicks")},
        state={
            "trigger_idx": State("left-hide-trigger", "data"),
            "session_id": State("session-id", "data"),
        },
    )
    def left_hide_button(btn, trigger_idx, session_id):
        """
        Callback function to handle the hide left button click event.

        Parameters:
        - btn (int): The number of times the hide left button has been clicked.
        - trigger_idx (int): The current value of the left hide trigger.
        - session_id (str): The ID of the current session.

        Returns:
        - dict: A dictionary containing the updated value for the output trigger.

        Output Properties:
        - output_trigger (int): The updated value for the left hide trigger.
        """
        if btn == 0:
            raise PreventUpdate

        selected_data = cache_get(session_id, CACHE_KEYS["selected_data"])

        if selected_data is None:
            raise PreventUpdate

        visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])

        s_data = pd.DataFrame(selected_data["points"])
        idx = s_data["id"]
        idx.index = idx

        vis_idx = idx[visible_table["_VIS_"][idx] == "visible"]
        hid_idx = idx[visible_table["_VIS_"][idx] == "hidden"]

        visible_table.loc[vis_idx, "_VIS_"] = "hidden"
        visible_table.loc[hid_idx, "_VIS_"] = "visible"

        cache_set(visible_table, session_id, CACHE_KEYS["visible_table"])

        return {"output_trigger": trigger_idx + 1}
