"""SensorView 3D Scatter View Callbacks

This module provides callback functions for managing the 3D scatter plot view in the
SensorView application. It handles real-time visualization updates, user interactions,
and data export functionality.

Core Features:
-------------
1. View Management:
   - Real-time plot updates
   - Frame-by-frame navigation
   - Overlay mode support
   - Dark/light theme switching

2. Data Processing:
   - Frame buffering and caching
   - Background processing
   - Data filtering
   - Decay effect handling

3. User Interactions:
   - Click handling
   - Selection management
   - Export capabilities
   - Animation controls

Dependencies:
------------
- dash & plotly
- numpy & pandas
- app_config settings
- utils functions
- viz modules

Usage:
------
Register callbacks with app instance:
    from view_callbacks.scatter_3d_view import get_scatter_3d_view_callbacks
    get_scatter_3d_view_callbacks(app)

Author: Zhengyu Peng
Email: zpeng.me@gmail.com
Website: https://zpeng.me
License: GPL-3.0
"""

import json
import os
import datetime

import dash
from dash import dcc
from dash.dependencies import Input, Output, State, ALL
from dash.exceptions import PreventUpdate
import plotly.io as pio
import plotly.graph_objs as go

import numpy as np

from app_config import background_callback_manager
from app_config import CACHE_KEYS, KEY_TYPES

from utils import filter_all
from utils import cache_set, cache_get, cache_expire
from utils import load_data
from utils import load_image
from utils import prepare_figure_kwargs

from viz.viz import get_animation_data
from viz.graph_data import get_ref_scatter3d_data
from viz.graph_data import get_scatter3d_data
from viz.graph_layout import get_scatter3d_layout

from process_frame import process_overlay_frame
from process_frame import process_single_frame


def get_scatter_3d_view_callbacks(app: dash.Dash) -> None:
    """
    Register the callback functions for the 3D scatter plot view.

    Args:
        app (dash.Dash): The Dash application instance

    Returns:
        None
    """

    @app.callback(
        output={
            "is_open": Output("3d-config-collapse", "is_open"),
        },
        inputs={
            "n_clicks": Input("3d-config-more-button", "n_clicks"),
        },
        state={
            "is_open": State("3d-config-collapse", "is_open"),
        },
    )
    def toggle_3d_config_collapse(n_clicks: int, is_open: bool) -> dict:
        """
        Toggle the visibility of the 3D configuration collapse panel.

        Args:
            n_clicks (int): Number of times the more button has been clicked
            is_open (bool): Current state of the collapse panel

        Returns:
            dict: Updated collapse panel state

        Raises:
            PreventUpdate: If button has not been clicked
        """
        if n_clicks == 0:
            raise PreventUpdate

        return {"is_open": not is_open}

    @app.callback(
        output={
            "scatter3d": Output("scatter3d", "figure", allow_duplicate=True),
        },
        inputs={
            "unused_remote_trigger": Input("trigger-remote-figure", "data"),
            "overlay_enable": Input("overlay-switch", "value"),
        },
        state={
            "decay": State("decay-slider", "value"),
            "slider_arg": State("slider-frame", "value"),
            "ispaused": State("interval-component", "disabled"),
            "cat_values": State({"type": "filter-dropdown", "index": ALL}, "value"),
            "num_values": State({"type": "filter-slider", "index": ALL}, "value"),
            "colormap": State("colormap-3d", "value"),
            "visible_list": State("visible-picker", "value"),
            "c_key": State("c-picker-3d", "value"),
            "darkmode": State("darkmode-switch", "value"),
            "session_id": State("session-id", "data"),
            "file": State("current-file", "data"),
            "file_list": State("file-add", "value"),
        },
        prevent_initial_call=True,
    )
    def slider_change_callback(
        unused_remote_trigger: int,
        slider_arg: int,
        cat_values: list,
        num_values: list,
        ispaused: bool,
        colormap: str,
        visible_list: list,
        c_key: str,
        overlay_enable: list,
        decay: int,
        darkmode: list,
        session_id: str,
        file: str,
        file_list: list,
    ) -> dict:
        """
        Update the 3D scatter plot when slider position changes.

        Args:
            unused_remote_trigger (int): Remote figure trigger count
            slider_arg (int): Current slider position
            cat_values (list): Selected categorical filter values
            num_values (list): Selected numerical filter values
            ispaused (bool): Animation pause state
            colormap (str): Selected colormap name
            visible_list (list): List of visible elements
            c_key (str): Selected color key
            overlay_enable (list): Overlay mode enable state
            decay (int): Number of past frames to show
            darkmode (list): Dark mode enable state
            session_id (str): Session identifier
            file (str): Current file path
            file_list (list): List of all file paths

        Returns:
            dict: Updated scatter plot figure data
        """
        config = cache_get(session_id, CACHE_KEYS["config"])

        if overlay_enable:
            fig = process_overlay_frame(
                slider_arg,
                config,
                cat_values,
                num_values,
                colormap,
                visible_list,
                c_key,
                session_id,
                file,
                file_list,
            )
        else:
            fig = process_single_frame(
                config,
                cat_values,
                num_values,
                colormap,
                visible_list,
                c_key,
                decay,
                session_id,
                file,
                slider_arg,
                ispaused,
            )

        if darkmode:
            fig["layout"]["template"] = pio.templates["plotly_dark"]
        else:
            fig["layout"]["template"] = pio.templates["plotly"]

        return {"scatter3d": fig}

    @app.callback(
        output={
            "scatter3d": Output("scatter3d", "figure", allow_duplicate=True),
        },
        inputs={
            "colormap": Input("colormap-3d", "value"),
        },
        state={
            "fig": State("scatter3d", "figure"),
        },
        prevent_initial_call=True,
    )
    def colormap_change_callback(colormap: str, fig: dict) -> dict:
        """
        Update the colormap of the 3D scatter plot.

        Args:
            colormap (str): Name of the selected colormap
            fig (dict): Current figure dictionary

        Returns:
            dict: Updated figure with new colormap
        """
        for idx in range(0, len(fig["data"])):
            fig["data"][idx]["marker"]["colorscale"] = colormap

        return {"scatter3d": fig}

    @app.callback(
        output={
            "scatter3d": Output("scatter3d", "figure", allow_duplicate=True),
        },
        inputs={
            "darkmode": Input("darkmode-switch", "value"),
        },
        state={
            "fig": State("scatter3d", "figure"),
        },
        prevent_initial_call=True,
    )
    def darkmode_change_callback(darkmode: list, fig: dict) -> dict:
        """
        Toggle dark mode for the 3D scatter plot.

        Args:
            darkmode (list): Dark mode enable state
            fig (dict): Current figure dictionary

        Returns:
            dict: Updated figure with new theme
        """
        if darkmode:
            fig["layout"]["template"] = pio.templates["plotly_dark"]
        else:
            fig["layout"]["template"] = pio.templates["plotly"]

        return {"scatter3d": fig}

    @app.callback(
        output={
            "trigger": Output("visible-table-change-trigger", "data"),
        },
        inputs={
            "click_data": Input("scatter3d", "clickData"),
        },
        state={
            "trigger_input": State("visible-table-change-trigger", "data"),
            "click_hide": State("click-hide-switch", "value"),
            "session_id": State("session-id", "data"),
        },
        prevent_initial_call=True,
    )
    def visible_table_change_callback(
        click_data: dict,
        trigger_input: int,
        click_hide: list,
        session_id: str,
    ) -> dict:
        """
        Handle visibility changes from click interactions.

        Args:
            click_data (dict): Data from click event
            trigger_input (int): Current trigger state
            click_hide (list): Click-to-hide feature state
            session_id (str): Session identifier

        Returns:
            dict: Updated trigger value

        Raises:
            PreventUpdate: If click-to-hide is not enabled
        """
        visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])
        if click_hide:
            if visible_table["_VIS_"][click_data["points"][0]["id"]] == "visible":
                visible_table.at[click_data["points"][0]["id"], "_VIS_"] = "hidden"
            else:
                visible_table.at[click_data["points"][0]["id"], "_VIS_"] = "visible"

            cache_set(visible_table, session_id, CACHE_KEYS["visible_table"])

            return {"trigger": trigger_input + 1}

        raise PreventUpdate

    @app.callback(
        output={
            "scatter3d": Output("scatter3d", "figure", allow_duplicate=True),
            "trigger": Output("background-trigger", "data"),
            "local_buffer_idx": Output(
                "local-buffer-index", "data", allow_duplicate=True
            ),
        },
        inputs={
            "cat_values": Input({"type": "filter-dropdown", "index": ALL}, "value"),
            "num_values": Input({"type": "filter-slider", "index": ALL}, "value"),
            "visible_list": Input("visible-picker", "value"),
            "unused_vistable_trigger": Input("visible-table-change-trigger", "data"),
            "c_key": Input("c-picker-3d", "value"),
            "unused_left_hide_trigger": Input("left-hide-trigger", "data"),
            "unused_right_hide_trigger": Input("right-hide-trigger", "data"),
            "unused_file_loaded": Input("file-loaded-trigger", "data"),
            "slider_picker_3d": Input("slider-picker-3d", "value"),
            "x_picker_3d": Input("x-picker-3d", "value"),
            "y_picker_3d": Input("y-picker-3d", "value"),
            "z_picker_3d": Input("z-picker-3d", "value"),
            "x_ref_picker_3d": Input("x-ref-picker-3d", "value"),
            "y_ref_picker_3d": Input("y-ref-picker-3d", "value"),
            "z_ref_picker_3d": Input("z-ref-picker-3d", "value"),
        },
        state={
            "ispaused": State("interval-component", "disabled"),
            "slider_arg": State("slider-frame", "value"),
            "overlay_enable": State("overlay-switch", "value"),
            "decay": State("decay-slider", "value"),
            "colormap": State("colormap-3d", "value"),
            "darkmode": State("darkmode-switch", "value"),
            "session_id": State("session-id", "data"),
            "file": State("current-file", "data"),
            "file_list": State("file-add", "value"),
            "trigger_val": State("background-trigger", "data"),
            "data_path": State("data-path", "value"),
            "case": State("test-case", "value"),
        },
        prevent_initial_call=True,
    )
    def regenerate_figure_callback(
        cat_values: list,
        num_values: list,
        visible_list: list,
        unused_vistable_trigger: int,
        ispaused: bool,
        slider_arg: int,
        c_key: str,
        overlay_enable: list,
        unused_left_hide_trigger: int,
        unused_right_hide_trigger: int,
        unused_file_loaded: int,
        slider_picker_3d: str,
        x_picker_3d: str,
        y_picker_3d: str,
        z_picker_3d: str,
        x_ref_picker_3d: str,
        y_ref_picker_3d: str,
        z_ref_picker_3d: str,
        decay: int,
        colormap: str,
        darkmode: list,
        session_id: str,
        file: str,
        file_list: list,
        trigger_val: int,
        data_path: str,
        case: str,
    ) -> dict:
        """
        Regenerate the 3D scatter plot figure.

        Args:
            cat_values (list): Selected categorical filter values
            num_values (list): Selected numerical filter values
            visible_list (list): List of visible elements
            unused_vistable_trigger (int): Visibility table trigger
            ispaused (bool): Animation pause state
            slider_arg (int): Current slider position
            c_key (str): Selected color key
            overlay_enable (list): Overlay mode enable state
            unused_left_hide_trigger (int): Left hide trigger
            unused_right_hide_trigger (int): Right hide trigger
            unused_file_loaded (int): File loaded trigger
            decay (int): Number of past frames to show
            colormap (str): Selected colormap name
            darkmode (list): Dark mode enable state
            session_id (str): Session identifier
            file (str): Current file path
            file_list (list): List of all file paths
            trigger_val (int): Current trigger value

        Returns:
            dict: Updated figure data and trigger values
        """
        # invoke task
        cache_set(-1, session_id, CACHE_KEYS["task_id"])
        cache_set(-1, session_id, CACHE_KEYS["figure_idx"])

        # save filter key word arguments to Redis
        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        filter_kwargs["num_values"] = num_values
        filter_kwargs["cat_values"] = cat_values
        cache_set(filter_kwargs, session_id, CACHE_KEYS["filter_kwargs"])

        if file not in file_list:
            file_list.append(file)

        # get config from Redis
        config = cache_get(session_id, CACHE_KEYS["config"])
        config["slider"] = slider_picker_3d
        config["x_3d"] = x_picker_3d
        config["y_3d"] = y_picker_3d
        config["z_3d"] = z_picker_3d
        config["x_ref"] = x_ref_picker_3d
        config["y_ref"] = y_ref_picker_3d
        config["z_ref"] = z_ref_picker_3d
        cache_set(config, session_id, CACHE_KEYS["config"])
        # save the config to os.path.join(data_path, case, "info.json"
        with open(
            os.path.join(data_path, case, "info.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(config, f, indent=4)

        if overlay_enable:
            fig = process_overlay_frame(
                slider_arg,
                config,
                cat_values,
                num_values,
                colormap,
                visible_list,
                c_key,
                session_id,
                file,
                file_list,
            )
        else:
            fig = process_single_frame(
                config,
                cat_values,
                num_values,
                colormap,
                visible_list,
                c_key,
                decay,
                session_id,
                file,
                slider_arg,
                ispaused,
            )

        if darkmode:
            fig["layout"]["template"] = pio.templates["plotly_dark"]
        else:
            fig["layout"]["template"] = pio.templates["plotly"]

        return {"scatter3d": fig, "trigger": trigger_val + 1, "local_buffer_idx": -1}

    @app.callback(
        background=True,
        output={
            "dummy": Output("dummy-background", "data"),
        },
        inputs={
            "trigger_idx": Input("background-trigger", "data"),
        },
        state={
            "cat_values": State({"type": "filter-dropdown", "index": ALL}, "value"),
            "num_values": State({"type": "filter-slider", "index": ALL}, "value"),
            "visible_list": State("visible-picker", "value"),
            "c_key": State("c-picker-3d", "value"),
            "session_id": State("session-id", "data"),
            "file": State("current-file", "data"),
            "file_list": State("file-add", "value"),
        },
        cancel=[Input("background-trigger", "data")],
        progress=[
            Output("buffer", "value"),
            Output("buffer-tooltip", "children"),
        ],
        manager=background_callback_manager,
        prevent_initial_call=True,
    )
    def regenerate_figure_background_callback(
        set_progress: callable,
        trigger_idx: int,
        cat_values: list,
        num_values: list,
        visible_list: list,
        c_key: str,
        session_id: str,
        file: str,
        file_list: list,
    ) -> dict:
        """
        Background task for regenerating the 3D scatter plot.

        Args:
            set_progress (callable): Progress update function
            trigger_idx (int): Task trigger index
            cat_values (list): Selected categorical filter values
            num_values (list): Selected numerical filter values
            visible_list (list): List of visible elements
            c_key (str): Selected color key
            session_id (str): Session identifier
            file (str): Current file path
            file_list (list): List of all file paths

        Returns:
            dict: Dummy output for completion
        """
        cache_set(trigger_idx, session_id, CACHE_KEYS["task_id"])
        print("start new task (" + str(trigger_idx) + ")")

        set_progress([0, "Buffering ... (0 %)"])

        cache_expire()

        if file not in file_list:
            file_list.append(file)

        # set figure index to -1 (no buffer is ready)
        cache_set(-1, session_id, CACHE_KEYS["figure_idx"])

        config = cache_get(session_id, CACHE_KEYS["config"])
        keys_dict = config["keys"]

        slider_label = keys_dict[config["slider"]]["description"]

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]

        visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])
        # frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])

        dataset = load_data(file_list)
        dataset[config["slider"]] = dataset[config["slider"]].astype(int)
        frame_list = np.sort(dataset[config["slider"]].unique())
        cache_set(frame_list, session_id, CACHE_KEYS["frame_list"])

        frame_group = dataset.groupby(config["slider"])

        # prepare figure key word arguments
        fig_kwargs = prepare_figure_kwargs(
            config,
            frame_list,
            c_key,
            num_keys,
            num_values,
        )

        for slider_arg, frame_idx in enumerate(frame_list):
            file = json.loads(file_list[0])
            img_path = os.path.join(
                file["path"], file["name"][0:-4], str(frame_list[slider_arg]) + ".jpg"
            )

            # encode image frame
            fig_kwargs["image"] = load_image(img_path)

            fig_kwargs["name"] = (
                "Index: "
                + str(slider_arg)
                + " ("
                + slider_label
                + ": "
                + str(frame_idx)
                + ")"
            )

            data = frame_group.get_group(frame_idx)
            filterd_frame = filter_all(
                data,
                num_keys,
                num_values,
                cat_keys,
                cat_values,
                visible_table,
                visible_list,
            )

            # fig = get_scatter3d_data(filterd_frame, **fig_kwargs)
            result = get_scatter3d_data(filterd_frame, hover=keys_dict, **fig_kwargs)
            fig = result["scatter_data"]
            hover_strings = result["hover_strings"]

            if fig_kwargs["x_ref"] is not None and fig_kwargs["y_ref"] is not None and fig_kwargs["x_ref"] != "None" and fig_kwargs["y_ref"] != "None":
                ref_fig = [
                    get_ref_scatter3d_data(
                        data_frame=filterd_frame,
                        x_key=fig_kwargs["x_ref"],
                        y_key=fig_kwargs["y_ref"],
                        z_key=None,
                        name=fig_kwargs.get("ref_name", None),
                    )
                ]
            else:
                ref_fig = []

            fig_layout = get_scatter3d_layout(**fig_kwargs)

            if trigger_idx != cache_get(session_id, CACHE_KEYS["task_id"]):
                print("task (" + str(trigger_idx) + ") cancelled")
                set_progress([0, "Buffering ... (0 %)"])
                return {"dummy": 0}

            cache_set(slider_arg, session_id, CACHE_KEYS["figure_idx"])
            cache_set(fig, session_id, CACHE_KEYS["figure"], str(slider_arg))
            cache_set(hover_strings, session_id, CACHE_KEYS["hover"], str(slider_arg))
            cache_set(ref_fig, session_id, CACHE_KEYS["figure_ref"], str(slider_arg))
            cache_set(
                fig_layout, session_id, CACHE_KEYS["figure_layout"], str(slider_arg)
            )

            percent = slider_arg / len(frame_list) * 100
            set_progress(
                [
                    percent,
                    "Buffering ... (" + str(round(percent, 2)) + " %)",
                ]
            )

        set_progress([100, "Buffer ready (100 %)"])

        print("task (" + str(trigger_idx) + ") completed")

        return {"dummy": 0}

    @app.callback(
        output={"filter_trigger": Output("filter-trigger", "data")},
        inputs={
            "unused_cat_values": Input(
                {"type": "filter-dropdown", "index": ALL}, "value"
            ),
            "unused_num_values": Input(
                {"type": "filter-slider", "index": ALL}, "value"
            ),
            "unused_visible_list": Input("visible-picker", "value"),
            "unused_vistable_trigger": Input("visible-table-change-trigger", "data"),
            "unused_file_loaded": Input("file-loaded-trigger", "data"),
        },
        state={
            "trigger_idx": State("filter-trigger", "data"),
        },
    )
    def invoke_filter_trigger(
        unused_cat_values: list,
        unused_num_values: list,
        unused_visible_list: list,
        unused_vistable_trigger: int,
        unused_file_loaded: int,
        trigger_idx: int,
    ) -> dict:
        """
        Increment the filter trigger counter.

        Args:
            unused_cat_values (list): Categorical filter values
            unused_num_values (list): Numerical filter values
            unused_visible_list (list): Visible elements list
            unused_vistable_trigger (int): Visibility table trigger
            unused_file_loaded (int): File loaded trigger
            trigger_idx (int): Current trigger value

        Returns:
            dict: Incremented trigger value
        """
        filter_trig = trigger_idx + 1

        return {"filter_trigger": filter_trig}

    @app.callback(
        background=True,
        output={"dummy": Output("hidden-scatter3d", "children")},
        inputs={"btn": Input("export-scatter3d", "n_clicks")},
        state={
            "case": State("test-case", "value"),
            "session_id": State("session-id", "data"),
            "c_key": State("c-picker-3d", "value"),
            "colormap": State("colormap-3d", "value"),
            "visible_list": State("visible-picker", "value"),
            "file": State("current-file", "data"),
            "file_list": State("file-add", "value"),
            "decay": State("decay-slider", "value"),
            "darkmode": State("darkmode-switch", "value"),
        },
        manager=background_callback_manager,
    )
    def export_3d_scatter_animation(
        btn: int,
        case: str,
        session_id: str,
        c_key: str,
        colormap: str,
        visible_list: list,
        file: str,
        file_list: list,
        decay: int,
        darkmode: list,
    ) -> dict:
        """
        Export 3D scatter plot animation to HTML file.

        Args:
            btn (int): Button click count
            case (str): Test case name
            session_id (str): Session identifier
            c_key (str): Selected color key
            colormap (str): Selected colormap name
            visible_list (list): List of visible elements
            file (str): Current file path
            file_list (list): List of all file paths
            decay (int): Number of past frames to show
            darkmode (list): Dark mode enable state

        Returns:
            dict: Dummy output for completion

        Raises:
            PreventUpdate: If button not clicked
        """
        if btn == 0:
            raise PreventUpdate

        if not os.path.exists("data/" + case + "/images"):
            os.makedirs("data/" + case + "/images")

        config = cache_get(session_id, CACHE_KEYS["config"])
        keys_dict = config["keys"]
        c_type = keys_dict[c_key].get("type", KEY_TYPES["NUM"])

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]
        num_values = filter_kwargs["num_values"]
        cat_values = filter_kwargs["cat_values"]

        frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])

        fig_kwargs = prepare_figure_kwargs(
            config,
            frame_list,
            c_key,
            num_keys,
            num_values,
        )

        if darkmode:
            fig_kwargs["template"] = "plotly_dark"
        else:
            fig_kwargs["template"] = "plotly"

        if file not in file_list:
            file_list.append(file)

        visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])

        dataset = load_data(file_list)
        filtered_table = filter_all(
            dataset,
            num_keys,
            num_values,
            cat_keys,
            cat_values,
            visible_table,
            visible_list,
        )

        img_list = []

        for _, f_val in enumerate(frame_list):
            file = json.loads(file_list[0])
            img_list.append(
                os.path.join(file["path"], file["name"][0:-4], str(f_val) + ".jpg")
            )

        fig_kwargs["title"] = file["name"][0:-4]

        fig_kwargs["height"] = 750

        fig_kwargs["decay"] = decay
        fig_kwargs["c_type"] = c_type
        fig_kwargs["keys_dict"] = keys_dict

        fig = go.Figure(
            get_animation_data(
                filtered_table,
                frame_key=config["slider"],
                img_list=img_list,
                colormap=colormap,
                **fig_kwargs
            )
        )

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        fig.write_html(
            "data/"
            + case
            + "/images/"
            + timestamp
            + "_"
            + file["name"][0:-4]
            + "_3dview.html"
        )

        return {"dummy": 0}

    @app.callback(
        output={"download": Output("download", "data", allow_duplicate=True)},
        inputs={"btn": Input("export-scatter3d-html", "n_clicks")},
        state={
            "fig": State("scatter3d", "figure"),
        },
        prevent_initial_call=True,
    )
    def export_3d_scatter_html(btn: int, fig: dict) -> dict:
        """
        Export current 3D scatter plot to HTML file.

        Args:
            btn (int): Button click count
            fig (dict): Current figure dictionary

        Returns:
            dict: Download data for file

        Raises:
            PreventUpdate: If button not clicked
        """
        if btn == 0:
            raise PreventUpdate

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        if not os.path.exists("temp"):
            os.mkdir("temp")

        file_name = "temp/" + timestamp + "_3dscatter.html"

        temp_fig = go.Figure(fig)
        temp_fig.write_html(file_name)

        return {"download": dcc.send_file(file_name)}

    @app.callback(
        output={"download": Output("download", "data", allow_duplicate=True)},
        inputs={"btn": Input("export-scatter3d-png", "n_clicks")},
        state={
            "fig": State("scatter3d", "figure"),
        },
        prevent_initial_call=True,
    )
    def export_3d_scatter_png(btn: int, fig: dict) -> dict:
        """
        Export current 3D scatter plot to PNG image.

        Args:
            btn (int): Button click count
            fig (dict): Current figure dictionary

        Returns:
            dict: Download data for file

        Raises:
            PreventUpdate: If button not clicked
        """
        if btn == 0:
            raise PreventUpdate

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        if not os.path.exists("temp"):
            os.mkdir("temp")

        file_name = "temp/" + timestamp + "_3dscatter.png"

        temp_fig = go.Figure(fig)
        temp_fig.write_image(file_name, scale=2)

        return {"download": dcc.send_file(file_name)}

    @app.callback(
        output={"download": Output("download", "data", allow_duplicate=True)},
        inputs={"btn": Input("export-data-all", "n_clicks")},
        state={
            "session_id": State("session-id", "data"),
            "visible_list": State("visible-picker", "value"),
            "file": State("current-file", "data"),
            "file_list": State("file-add", "value"),
        },
        prevent_initial_call=True,
    )
    def export_all_frame_data(
        btn: int, session_id: str, visible_list: list, file: str, file_list: list
    ) -> dict:
        """
        Export data from all frames to CSV file.

        Args:
            btn (int): Button click count
            session_id (str): Session identifier
            visible_list (list): List of visible elements
            file (str): Current file path
            file_list (list): List of all file paths

        Returns:
            dict: Download data for file

        Raises:
            PreventUpdate: If button not clicked
        """
        if btn == 0:
            raise PreventUpdate

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]
        cat_values = filter_kwargs["cat_values"]
        num_values = filter_kwargs["num_values"]

        # file = json.loads(file)
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
        file = json.loads(file)

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        file_name = "temp/" + file["name"][0:-4] + "_" + timestamp + ".csv"

        filtered_table.to_csv(
            file_name,
            index=False,
        )

        return {"download": dcc.send_file(file_name)}

    @app.callback(
        output={"download": Output("download", "data", allow_duplicate=True)},
        inputs={"btn": Input("export-data-current", "n_clicks")},
        state={
            "slider_arg": State("slider-frame", "value"),
            "session_id": State("session-id", "data"),
            "visible_list": State("visible-picker", "value"),
            "file": State("current-file", "data"),
        },
        prevent_initial_call=True,
    )
    def export_current_frame_data(
        btn: int, slider_arg: int, session_id: str, visible_list: list, file: str
    ) -> dict:
        """
        Export data from current frame to CSV file.

        Args:
            btn (int): Button click count
            slider_arg (int): Current slider position
            session_id (str): Session identifier
            visible_list (list): List of visible elements
            file (str): Current file path

        Returns:
            dict: Download data for file

        Raises:
            PreventUpdate: If button not clicked
        """
        if btn == 0:
            raise PreventUpdate

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]
        cat_values = filter_kwargs["cat_values"]
        num_values = filter_kwargs["num_values"]

        # file = json.loads(file)
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
        file = json.loads(file)

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        file_name = "temp/" + file["name"][0:-4] + "_" + timestamp + ".csv"

        filtered_table.to_csv(
            file_name,
            index=False,
        )

        return {"download": dcc.send_file(file_name)}
