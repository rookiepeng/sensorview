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
from utils import cache_get, cache_set
from utils import load_data


def get_scatter_2d_right_view_callbacks(app):
    """
    Register the callback functions for the right 2D view.

    Parameters:
    - app (Dash app): The Dash app.

    Returns:
    - None
    """

    @app.callback(
        output={"regenerate_trigger": Output("right-regenerate-trigger", "data")},
        inputs={
            "unused_slider_arg": Input("slider-frame", "value"),
            "unused_stop_click": Input("stop-button", "n_clicks"),
            "all_frame_sw": Input("scatter2dl-allframe-switch", "value"),
        },
        state={
            "ispaused": State("interval-component", "disabled"),
            "right_sw": State("right-switch", "value"),
            "current_regenerate_trigger": State("right-regenerate-trigger", "data"),
        },
    )
    def invoke_scatter2d_right_frame_trigger(
        unused_slider_arg,
        unused_stop_click,
        all_frame_sw,
        ispaused,
        right_sw,
        current_regenerate_trigger,
    ):
        """
        Callback function to invoke the trigger to regenerate per-frame plot of
        right scatter2d figure.

        Parameters:
        - unused_slider_arg (int): The unused slider value.
        - unused_stop_click (int): The unused stop click value.
        - all_frame_sw (str): The selection between current frame of all frames.
        - ispaused (bool): If the video is paused.
        - right_sw (bool): If the figure is enabled.
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

        if ispaused and all_frame_sw == "current" and right_sw:
            trig = current_regenerate_trigger + 1

            return {"regenerate_trigger": trig}

        raise PreventUpdate

    @app.callback(
        background=True,
        output={
            "figure": Output("scatter2d-right", "figure", allow_duplicate=True),
        },
        inputs={
            "unused_filter_trigger": Input("filter-trigger", "data"),
            "unused_left_hide_trigger": Input("left-hide-trigger", "data"),
            "unused_right_hide_trigger": Input("right-hide-trigger", "data"),
            "unused_regenerate_trigger": Input("right-regenerate-trigger", "data"),
            "right_sw": Input("right-switch", "value"),
            "all_frame_sw": Input("scatter2dr-allframe-switch", "value"),
            "x_right": Input("x-picker-2d-right", "value"),
            "y_right": Input("y-picker-2d-right", "value"),
            "color_right": Input("c-picker-2d-right", "value"),
        },
        state={
            "slider_arg": State("slider-frame", "value"),
            "colormap": State("colormap-scatter2d-right", "value"),
            "session_id": State("session-id", "data"),
            "visible_list": State("visible-picker", "value"),
            "file": State("current-file", "data"),
            "file_list": State("file-add", "value"),
        },
        manager=background_callback_manager,
        prevent_initial_call=True,
    )
    def regenerate_scatter2d_right_callback(
        unused_filter_trigger,
        unused_left_hide_trigger,
        unused_right_hide_trigger,
        unused_regenerate_trigger,
        right_sw,
        x_right,
        y_right,
        color_right,
        slider_arg,
        all_frame_sw,
        colormap,
        session_id,
        visible_list,
        file,
        file_list,
    ):
        """
        Background callback function to regenerate the right 2D scatter plot based on
        the input values.

        Parameters:
        - unused_filter_trigger (any): Unused input trigger for filtering data.
        - unused_left_hide_trigger (any): Unused input trigger for hiding left panel.
        - unused_regenerate_trigger (any): Input trigger to update the per-frame plot.
        - right_sw (bool): The value of the right switch.
        - x_right (str): The selected x-axis key for the right scatter plot.
        - y_right (str): The selected y-axis key for the right scatter plot.
        - color_right (str): The selected color key for the right scatter plot.
        - colormap (str): The selected colormap for the right scatter plot.
        - session_id (str): The ID of the current session.
        - visible_list (list): The list of visible items.
        - file (str): The selected file.
        - file_list (list): The list of selected files.

        Returns:
        - dict: A dictionary containing the updated right 2D scatter plot figure.

        Output Properties:
        - figure (dict): The updated right 2D scatter plot figure.
        """
        if not right_sw:
            right_fig = {
                "data": [{"mode": "markers", "type": "scattergl", "x": [], "y": []}],
                "layout": {},
            }

            return {
                "figure": right_fig,
            }

        config = cache_get(session_id, CACHE_KEYS["config"])
        keys_dict = config["keys"]

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]
        cat_values = filter_kwargs["cat_values"]
        num_values = filter_kwargs["num_values"]

        x_key = x_right
        y_key = y_right
        c_key = color_right
        x_label = keys_dict[x_right]["description"]
        y_label = keys_dict[y_right]["description"]
        c_label = keys_dict[color_right]["description"]

        if all_frame_sw == "all":
            data = load_data(file_list, file)
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

        right_fig = get_scatter2d(
            filtered_table,
            x_key,
            y_key,
            c_key,
            x_label,
            y_label,
            c_label,
            colormap=colormap,
            c_type=keys_dict[c_key].get("type", KEY_TYPES["NUM"]),
        )

        return {
            "figure": right_fig,
        }

    @app.callback(
        output={
            "figure": Output("scatter2d-right", "figure", allow_duplicate=True),
        },
        inputs={
            "colormap": Input("colormap-scatter2d-right", "value"),
        },
        state={
            "fig_in": State("scatter2d-right", "figure"),
            "right_sw": State("right-switch", "value"),
        },
        prevent_initial_call=True,
    )
    def scatter2d_right_colormap_change_callback(
        colormap,
        fig_in,
        right_sw,
    ):
        """
        Callback function to update the colormap of the right 2D scatter plot.

        Parameters:
        - colormap (str): The selected colormap.
        - fig_in (dict): The current figure of the right 2D scatter plot.
        - right_sw (bool): The value of the right switch.

        Returns:
        - dict: A dictionary containing the updated figure of the right 2D scatter plot.

        Output Properties:
        - figure (dict): The updated figure of the right 2D scatter plot.
        """
        if not right_sw:
            right_fig = {
                "data": [{"mode": "markers", "type": "scattergl", "x": [], "y": []}],
                "layout": {},
            }

            return {
                "figure": right_fig,
            }

        for idx in range(0, len(fig_in["data"])):
            fig_in["data"][idx]["marker"]["colorscale"] = colormap

        return {
            "figure": fig_in,
        }

    @app.callback(
        output={
            "collapse": Output("collapse-right2d", "is_open"),
        },
        inputs={
            "right_sw": Input("right-switch", "value"),
        },
    )
    def enable_scatter2d_right_callback(
        right_sw,
    ):
        """
        Callback function to enable or disable the right 2D scatter plot collapse.

        Parameters:
        - right_sw (bool): The value of the right switch.

        Returns:
        - dict: A dictionary containing the updated value for the collapse property.

        Output Properties:
        - collapse (bool): Whether the right 2D scatter plot should be collapsed or not.
        """
        collapse = False
        if right_sw:
            collapse = True

        return {"collapse": collapse}

    @app.callback(
        output={"download": Output("download", "data", allow_duplicate=True)},
        inputs={"btn": Input("export-scatter2d-right", "n_clicks")},
        state={
            "fig": State("scatter2d-right", "figure"),
        },
        prevent_initial_call=True,
    )
    def export_right_2d_scatter(btn, fig):
        """
        Callback function to export the right 2D scatter plot as an image.

        Parameters:
        - btn (int): The number of times the export button has been clicked.
        - fig (dict): The right 2D scatter plot figure.

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

        file_name = "temp/" + timestamp + "_fig_right.png"

        temp_fig = go.Figure(fig)
        temp_fig.write_image(file_name, scale=2)

        return {"download": dcc.send_file(file_name)}

    @app.callback(
        output={"dummy": Output("selected-data-right", "data")},
        inputs={"selected_data": Input("scatter2d-right", "selectedData")},
        state={"session_id": State("session-id", "data")},
    )
    def select_right_figure(selected_data, session_id):
        """
        Callback function to store the selected data from the right 2D scatter plot.

        Parameters:
        - selectedData (dict): The selected data from the right 2D scatter plot.
        - session_id (str): The ID of the current session.

        Returns:
        - dict: A dictionary containing a dummy value for the output property.

        Output Properties:
        - dummy (int): A dummy value to trigger the update.
        """
        cache_set(selected_data, session_id, CACHE_KEYS["selected_data_right"])
        return {"dummy": 0}

    @app.callback(
        output={"output_trigger": Output("right-hide-trigger", "data")},
        inputs={"btn": Input("hide-right", "n_clicks")},
        state={
            "trigger_idx": State("right-hide-trigger", "data"),
            "session_id": State("session-id", "data"),
        },
    )
    def right_hide_button(btn, trigger_idx, session_id):
        """
        Callback function to handle the hide right button click event.

        Parameters:
        - btn (int): The number of times the hide right button has been clicked.
        - trigger_idx (int): The current value of the right hide trigger.
        - session_id (str): The ID of the current session.

        Returns:
        - dict: A dictionary containing the updated value for the output trigger.

        Output Properties:
        - output_trigger (int): The updated value for the right hide trigger.
        """
        if btn == 0:
            raise PreventUpdate

        selected_data = cache_get(session_id, CACHE_KEYS["selected_data_right"])

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
