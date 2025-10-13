"""SensorView 3D Scatter View Background Callbacks

This module provides background callback functions for managing the 3D scatter plot view
in the SensorView application. It specializes in computationally intensive operations
that run asynchronously to maintain responsive user interactions.

Background Processing Features:
------------------------------
1. Asynchronous Figure Generation:
   - Non-blocking 3D scatter plot regeneration
   - Frame-by-frame data processing with progress tracking
   - Real-time buffer status updates
   - Task cancellation support

2. Data Pipeline Management:
   - Multi-frame dataset loading and caching
   - Memory-efficient frame buffering
   - Background image processing and encoding
   - Filtered data preparation for visualization

3. Export Operations:
   - Asynchronous HTML animation export
   - Progress indication during long operations
   - File generation with timestamp naming
   - Background image compilation for animations

4. Performance Optimization:
   - Background task management with cancellation
   - Cache expiration and cleanup
   - Progressive loading with user feedback
   - Resource-efficient data handling

Core Callback Functions:
-----------------------
- regenerate_figure_background_callback(): Handles background figure regeneration
- export_3d_scatter_animation(): Manages asynchronous animation export

Dependencies:
------------
- dash: Web application framework and background callback management
- plotly: 3D visualization and graph objects
- numpy: Numerical computations and data processing
- app_config: Application configuration and cache management
- utils: Data loading, filtering, and utility functions
- viz: Visualization data preparation and layout management

Usage:
------
Register background callbacks with app instance:
    from view_callbacks.scatter_3d_view_background import get_scatter_3d_view_background_callbacks
    get_scatter_3d_view_background_callbacks(app)

Note: This module requires the background callback manager to be properly configured
in app_config for asynchronous task execution.

Author: Zhengyu Peng
Email: zpeng.me@gmail.com
Website: https://zpeng.me
License: GPL-3.0
"""

from typing import Callable
import json
import os
import datetime

import dash
from dash.dcc import send_file  # pyright: ignore[reportPrivateImportUsage]
from dash.dependencies import Input, Output, State, ALL
from dash.exceptions import PreventUpdate
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


def get_scatter_3d_view_background_callbacks(app: dash.Dash) -> None:
    """
    Register the background callback functions for the 3D scatter plot view.

    Args:
        app (dash.Dash): The Dash application instance

    Returns:
        None
    """

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
        set_progress: Callable,
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
        if config is None or "keys" not in config:
            raise PreventUpdate
        keys_dict = config["keys"]

        slider_label = keys_dict[config["slider"]]["description"]

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        if filter_kwargs is None:
            raise PreventUpdate
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]

        visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])

        dataset = load_data(file_list)
        dataset[config["slider"]] = dataset[config["slider"]].astype(int)
        frame_list = np.sort(dataset[config["slider"]].unique())
        cache_set(frame_list, session_id, CACHE_KEYS["frame_list"])

        frame_group = dataset.groupby(config["slider"])

        # prepare figure key word arguments
        fig_kwargs = prepare_figure_kwargs(
            config,
            num_keys,
            num_values,
            c_key,
            False,
            frame_list,
        )

        for slider_arg, frame_idx in enumerate(frame_list):
            file_dict = json.loads(file_list[0])
            img_path = os.path.join(
                file_dict["path"],
                file_dict["name"][0:-4],
                str(frame_list[slider_arg]) + ".jpg",
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

            result = get_scatter3d_data(filterd_frame, hover=keys_dict, **fig_kwargs)
            fig = result["scatter_data"]
            hover_strings = result["hover_strings"]

            if fig_kwargs["x_ref"] is not None and fig_kwargs["y_ref"] is not None:
                ref_fig = [
                    get_ref_scatter3d_data(
                        data_frame=filterd_frame,
                        x_key=fig_kwargs["x_ref"],
                        y_key=fig_kwargs["y_ref"],
                        z_key=fig_kwargs["z_ref"],
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
        background=True,
        output={"download": Output("download", "data", allow_duplicate=True)},
        inputs={"btn": Input("export-scatter3d", "n_clicks")},
        state={
            "case": State("test-case", "value"),
            "session_id": State("session-id", "data"),
            "c_key": State("c-picker-3d", "value"),
            "size_vary": State("size-vary-switch", "value"),
            "colormap": State("colormap-3d", "value"),
            "visible_list": State("visible-picker", "value"),
            "file": State("current-file", "data"),
            "file_list": State("file-add", "value"),
            "decay": State("decay-slider", "value"),
            "darkmode": State("darkmode-switch", "value"),
        },
        cancel=[Input("background-trigger", "data")],
        progress=[
            Output("export-spinner", "display"),
        ],
        manager=background_callback_manager,
        prevent_initial_call=True,
    )
    def export_3d_scatter_animation(
        set_progress: Callable,
        btn: int,
        case: str,
        session_id: str,
        c_key: str,
        size_vary: str,
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

        set_progress(["show"])

        if not os.path.exists("data/" + case + "/images"):
            os.makedirs("data/" + case + "/images")

        config = cache_get(session_id, CACHE_KEYS["config"])
        if config is None or "keys" not in config:
            raise PreventUpdate
        keys_dict = config["keys"]
        c_type = keys_dict[c_key].get("type", KEY_TYPES["NUM"])

        filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
        if filter_kwargs is None:
            raise PreventUpdate
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]
        num_values = filter_kwargs["num_values"]
        cat_values = filter_kwargs["cat_values"]

        frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])
        if frame_list is None:
            raise PreventUpdate

        fig_kwargs = prepare_figure_kwargs(
            config,
            num_keys,
            num_values,
            c_key,
            bool(size_vary),
            frame_list,
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

        file_dict = json.loads(file_list[0])
        for _, f_val in enumerate(frame_list):
            img_list.append(
                os.path.join(
                    file_dict["path"], file_dict["name"][0:-4], str(f_val) + ".jpg"
                )
            )

        fig_kwargs["title"] = file_dict["name"][0:-4]

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
                dark_mode=bool(darkmode),
                **fig_kwargs
            )
        )

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        file_name = "temp/" + timestamp + "_" + fig_kwargs["title"] + "_3dview.html"

        fig.write_html(file_name)

        set_progress(["hide"])

        return {"download": send_file(file_name)}
