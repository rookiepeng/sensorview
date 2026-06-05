"""SensorView Right 2D Scatter View Callbacks

Callback functions for right 2D scatter plot with real-time updates, frame-based
visualization, selection management, visibility toggling, and PNG export.

Usage:
    from view_callbacks.scatter_2d_right_view import get_scatter_2d_right_view_callbacks
    get_scatter_2d_right_view_callbacks(app)

Author: Zhengyu Peng
License: GPL-3.0
"""

import os

import datetime

import pandas as pd

import plotly.graph_objs as go

import dash
from dash.dcc import send_file  # pyright: ignore[reportPrivateImportUsage]
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
            "unused_play_stop_click": Input("play-stop-button", "n_clicks"),
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
        unused_play_stop_click,
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

        if trigger_id == "play-stop-button" and not ispaused:
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
            "x_min": State("x-min-2d-right", "value"),
            "x_max": State("x-max-2d-right", "value"),
            "y_min": State("y-min-2d-right", "value"),
            "y_max": State("y-max-2d-right", "value"),
        },
        manager=background_callback_manager,
        running=[
            (Output("loading_right", "display"), "show", "hide"),
        ],
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
        x_min,
        x_max,
        y_min,
        y_max,
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
        if config is None:
            raise PreventUpdate
        keys_dict = config["keys"]

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        if filter_kwargs is None:
            raise PreventUpdate
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

        if x_min is not None and x_max is not None:
            right_fig["layout"]["xaxis"]["range"] = [x_min, x_max]
            right_fig["layout"]["xaxis"]["autorange"] = False
        if y_min is not None and y_max is not None:
            right_fig["layout"]["yaxis"]["range"] = [y_min, y_max]
            right_fig["layout"]["yaxis"]["autorange"] = False

        return {
            "figure": right_fig,
        }

    @app.callback(
        output={
            "figure": Output("scatter2d-right", "figure", allow_duplicate=True),
        },
        inputs={
            "x_min": Input("x-min-2d-right", "value"),
            "x_max": Input("x-max-2d-right", "value"),
            "y_min": Input("y-min-2d-right", "value"),
            "y_max": Input("y-max-2d-right", "value"),
        },
        state={
            "fig_in": State("scatter2d-right", "figure"),
        },
        prevent_initial_call=True,
    )
    def update_right_axis_range(x_min, x_max, y_min, y_max, fig_in) -> dict:
        if x_min is None and x_max is None and y_min is None and y_max is None:
            raise PreventUpdate

        if x_min is not None and x_max is not None:
            fig_in["layout"]["xaxis"]["range"] = [x_min, x_max]
            fig_in["layout"]["xaxis"]["autorange"] = False
        else:
            fig_in["layout"]["xaxis"].pop("range", None)
            fig_in["layout"]["xaxis"]["autorange"] = True

        if y_min is not None and y_max is not None:
            fig_in["layout"]["yaxis"]["range"] = [y_min, y_max]
            fig_in["layout"]["yaxis"]["autorange"] = False
        else:
            fig_in["layout"]["yaxis"].pop("range", None)
            fig_in["layout"]["yaxis"]["autorange"] = True

        return {"figure": fig_in}

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

        for trace in fig_in["data"]:
            # Empty-frame placeholder traces have no "marker" key; skip them
            if "marker" in trace:
                trace["marker"]["colorscale"] = colormap

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
        output={
            "is_open": Output("range-config-collapse-right", "is_open"),
        },
        inputs={"_n_clicks": Input("range-config-button-right", "n_clicks")},
        state={"is_open": State("range-config-collapse-right", "is_open")},
        prevent_initial_call=True,
    )
    def toggle_right_range_collapse(_n_clicks, is_open):
        return {"is_open": not is_open}

    @app.callback(
        output={
            "x_min": Output("x-min-2d-right", "value"),
            "x_max": Output("x-max-2d-right", "value"),
            "y_min": Output("y-min-2d-right", "value"),
            "y_max": Output("y-max-2d-right", "value"),
        },
        inputs={
            "_x_right": Input("x-picker-2d-right", "value"),
            "_y_right": Input("y-picker-2d-right", "value"),
            "_file": Input("current-file", "data"),
            "_file_list": Input("file-add", "value"),
        },
        prevent_initial_call=True,
    )
    def reset_right_axis_range(_x_right, _y_right, _file, _file_list) -> dict:
        return {"x_min": None, "x_max": None, "y_min": None, "y_max": None}

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

        return {"download": send_file(file_name)}

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
        except (KeyError, ValueError, TypeError) as exc:
            raise PreventUpdate from exc

        # Toggle visibility for selected points efficiently
        mask = visible_table.index.isin(selected_ids)
        current_visibility = visible_table.loc[mask, "_VIS_"]

        # Toggle: visible -> hidden, hidden -> visible
        visible_table.loc[mask, "_VIS_"] = current_visibility.map(
            {"visible": "hidden", "hidden": "visible"}
        ).fillna(
            current_visibility
        )  # Keep original value if not visible/hidden

        cache_set(visible_table, session_id, CACHE_KEYS["visible_table"])

        return {"output_trigger": trigger_idx + 1}
