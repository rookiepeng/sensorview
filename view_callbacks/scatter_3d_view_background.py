"""SensorView 3D Scatter View Background Callbacks

Background callback functions for computationally intensive 3D scatter plot operations
including asynchronous figure generation, frame processing, animation export, and
background task management with progress tracking.

Usage:
    from view_callbacks.scatter_3d_view_background import get_scatter_3d_view_background_callbacks
    get_scatter_3d_view_background_callbacks(app)

Note: Requires background callback manager configuration in app_config.

Author: Zhengyu Peng
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

from frame_sources import (
    get_combined_reference_bounds,
    get_frame_stem,
    get_log_stems,
    get_manifest,
    get_reference_pose,
)

from viz.viz import get_animation_data
from viz.graph_data import get_reference_traces
from viz.graph_data import get_scatter3d_data
from viz.graph_layout import get_scatter3d_layout


def get_scatter_3d_view_background_callbacks(app: dash.Dash) -> None:
    """
    Register the background callback functions for the 3D scatter plot view.

    Args:
        app: The Dash application instance to register callbacks with.

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
        # Selecting another log ends this buffer, rather than letting it run to
        # completion against the dataset it was started for. Its own frame loop
        # only notices a *newer buffer* claiming the session, and a new buffer
        # starts no earlier than the load it is waiting on -- so without this the
        # outgoing dataset keeps writing bundles and advancing figure_idx while
        # the incoming one is read, and the viewer is served the old log's frames
        # under the new one's session.
        cancel=[
            Input("current-file", "data"),
            Input("file-add", "value"),
        ],
        progress=[
            Output("buffer", "value"),
            Output("buffer-tooltip", "children"),
            Output("buffer", "color"),
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
        Background task for regenerating the 3D scatter plot with progress tracking.

        Args:
            set_progress: Function to update progress indicators during processing.
            trigger_idx: Unique task trigger index for cancellation tracking.
            cat_values: List of selected categorical filter values.
            num_values: List of selected numerical filter ranges.
            visible_list: List of visibility filter values.
            c_key: Column name for color mapping.
            session_id: Unique session identifier for cache access.
            file: Current file path as JSON string.
            file_list: List of additional file paths as JSON strings.

        Returns:
            Dictionary with dummy output indicating task completion.

        Raises:
            PreventUpdate: If configuration data is missing or invalid.
        """
        print("start new task (" + str(trigger_idx) + ")")

        set_progress([0, "Buffering ... (0 %)", "warning"])

        cache_expire()

        # --- Cooperative cancellation ---
        # Claim ownership of this session's buffer generation. If an older task
        # is still running (OS-level termination is not instantaneous on Windows),
        # it will detect the mismatch inside its frame loop and abort itself.
        cache_set(trigger_idx, session_id, CACHE_KEYS["active_task_id"])

        if file not in file_list:
            file_list.append(file)

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

        # Use cached frame data instead of re-reading CSV from disk
        frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])
        if frame_list is None:
            # Fallback: load from disk if cache miss
            dataset = load_data(file_list)
            dataset[config["slider"]] = dataset[config["slider"]].astype(int)
            frame_list = np.sort(dataset[config["slider"]].unique())
            cache_set(frame_list, session_id, CACHE_KEYS["frame_list"])
            frame_group = dataset.groupby(config["slider"])
            use_cached_frames = False
        else:
            frame_group = None
            use_cached_frames = True

        manifest = get_manifest(session_id)

        # prepare figure key word arguments
        fig_kwargs = prepare_figure_kwargs(
            config,
            num_keys,
            num_values,
            c_key,
            False,
            frame_list,
            # Axis ranges are fixed for the whole buffer, so they have to cover
            # every combined log's reference rather than just the primary one's.
            ref_bounds=get_combined_reference_bounds(
                manifest, get_log_stems(session_id)
            ),
        )

        # Move loop-invariant operations outside the loop
        file_dict = json.loads(file_list[0])
        img_root = file_dict["path"]

        # Pre-compute base layout (only image changes per frame)
        fig_kwargs["image"] = None
        base_layout = get_scatter3d_layout(**fig_kwargs)
        has_ref = fig_kwargs["x_ref"] is not None and fig_kwargs["y_ref"] is not None
        ref_from_sidecar = bool(fig_kwargs.get("ref_from_sidecar"))

        for slider_arg, frame_idx in enumerate(frame_list):
            # --- Cooperative cancellation check ---
            # Abort immediately if a newer task has started and claimed ownership.
            # This prevents a stale task from overwriting figure_bundle / figure_idx
            # entries that the new task is already populating.
            if cache_get(session_id, CACHE_KEYS["active_task_id"]) != trigger_idx:
                print(
                    "task ("
                    + str(trigger_idx)
                    + ") superseded by newer task, aborting"
                )
                return {"dummy": 0}

            # Sidecars belong to the log that recorded this frame, which with
            # logs combined is not necessarily the primary one.
            stem = get_frame_stem(session_id, slider_arg)

            img_path = os.path.join(
                img_root,
                stem or file_dict["name"][0:-4],
                str(frame_list[slider_arg]) + ".jpg",
            )

            # encode image frame
            img = load_image(img_path)
            fig_kwargs["image"] = img

            fig_kwargs["name"] = (
                "Index: "
                + str(slider_arg)
                + " ("
                + slider_label
                + ": "
                + str(frame_idx)
                + ")"
            )

            data = (
                cache_get(session_id, CACHE_KEYS["frame_data"], str(frame_idx))
                if use_cached_frames
                else frame_group.get_group(frame_idx)
            )
            if data is None:
                continue

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

            if ref_from_sidecar:
                pose = get_reference_pose(manifest, stem, frame_idx)
                ref_fig = (
                    get_reference_traces(
                        data_frame=filterd_frame,
                        name=fig_kwargs.get("ref_name", None),
                        display=fig_kwargs.get("ref_display"),
                        pose=pose,
                    )
                    if pose is not None
                    else []
                )
            elif has_ref:
                ref_fig = get_reference_traces(
                    data_frame=filterd_frame,
                    x_key=fig_kwargs["x_ref"],
                    y_key=fig_kwargs["y_ref"],
                    z_key=fig_kwargs["z_ref"],
                    name=fig_kwargs.get("ref_name", None),
                    display=fig_kwargs.get("ref_display"),
                )
            else:
                ref_fig = []

            # Reuse base layout, only update image
            if img is not None:
                fig_layout = dict(base_layout)
                fig_layout["images"] = [
                    {
                        "source": img,
                        "xref": "x domain",
                        "yref": "y domain",
                        "x": 0,
                        "y": 1,
                        "xanchor": "left",
                        "yanchor": "top",
                        "sizex": 0.3,
                        "sizey": 0.3,
                    }
                ]
            else:
                fig_layout = base_layout

            # Bundle all per-frame data into a single cache entry
            frame_bundle = {
                "fig": fig,
                "hover_strings": hover_strings,
                "ref_fig": ref_fig,
                "fig_layout": fig_layout,
            }
            cache_set(frame_bundle, session_id, CACHE_KEYS["figure_bundle"], str(slider_arg))
            cache_set(slider_arg, session_id, CACHE_KEYS["figure_idx"])

            percent = slider_arg / len(frame_list) * 100
            set_progress(
                [
                    percent,
                    "Buffering ... (" + str(round(percent, 2)) + " %)",
                    "warning"
                ]
            )

        set_progress([100, "Buffer ready (100 %)", "success"])

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
        Export 3D scatter plot animation to HTML file with progress tracking.

        Args:
            set_progress: Function to control export progress spinner visibility.
            btn: Number of button clicks (must be > 0 to proceed).
            case: Test case name for file organization.
            session_id: Unique session identifier for cache access.
            c_key: Column name for color mapping.
            size_vary: String indicating whether to vary marker sizes.
            colormap: Name of the colormap to apply.
            visible_list: List of visibility filter values.
            file: Current file path as JSON string.
            file_list: List of additional file paths as JSON strings.
            decay: Number of past frames to show with decreasing opacity.
            darkmode: List indicating dark mode state (non-empty = enabled).

        Returns:
            Dictionary containing file download data for the generated HTML animation.

        Raises:
            PreventUpdate: If button has not been clicked or configuration data is missing.
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

        export_manifest = get_manifest(session_id)
        export_stems = get_log_stems(session_id)

        fig_kwargs = prepare_figure_kwargs(
            config,
            num_keys,
            num_values,
            c_key,
            bool(size_vary),
            frame_list,
            ref_bounds=get_combined_reference_bounds(export_manifest, export_stems),
        )

        if fig_kwargs.get("ref_from_sidecar"):
            # The export is a standalone HTML file with every frame baked in, so
            # the poses have to travel with it rather than be looked up per frame.
            fig_kwargs["ref_poses"] = {
                frame_id: get_reference_pose(
                    export_manifest, get_frame_stem(session_id, slider_arg), frame_id
                )
                for slider_arg, frame_id in enumerate(frame_list)
            }

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
        for slider_arg, f_val in enumerate(frame_list):
            img_list.append(
                os.path.join(
                    file_dict["path"],
                    get_frame_stem(session_id, slider_arg) or file_dict["name"][0:-4],
                    str(f_val) + ".jpg",
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
