"""Frame Processing Module for SensorView

Handles processing and visualization of individual data frames with single frame
processing, overlay frame processing, decay effects, and multi-file data integration.

Key functions: process_single_frame() and process_overlay_frame() for 3D scatter
plot generation with filtering, reference overlays, and temporal effects.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Dict, List, Tuple, Any

import numpy as np

from dash.exceptions import PreventUpdate

from utils import clamp_frame_index
from utils import filter_all
from utils import cache_get
from utils import load_data
from utils import prepare_figure_kwargs

from frame_sources import (
    get_cloud_trace,
    get_combined_reference_bounds,
    get_frame_stem,
    get_log_stems,
    get_manifest,
    get_reference_pose,
)

from viz.viz import get_scatter3d
from viz.graph_data import get_reference_traces
from viz.graph_data import get_scatter3d_data
from viz.graph_layout import get_scatter3d_layout

from app_config import CACHE_KEYS


def process_single_frame(
    config: Dict[str, Any],
    cat_values: List[List[str]],
    num_values: List[Tuple[float, float]],
    colormap: str,
    visible_list: List[str],
    c_key: str,
    size_vary: str,
    decay: int,
    session_id: str,
    frame_idx: int = 0,
    load_hover: bool = False,
) -> Dict[str, Any]:
    """
    Process a single frame of data and generate a 3D scatter plot figure with optional decay effect.

    Args:
        config: Configuration dictionary containing plot settings and key definitions.
        cat_values: List of lists containing selected categorical values for filtering.
        num_values: List of (min, max) tuples for numerical value filtering.
        colormap: Name of the colormap to apply to the scatter plot.
        visible_list: List of visibility filter values.
        c_key: Column name for color mapping.
        size_vary: String indicating whether to vary marker sizes.
        decay: Number of previous frames to include with decreasing opacity.
        session_id: Unique session identifier for cache access.
        frame_idx: Index of the current frame to process. Defaults to 0.
        load_hover: Whether to include hover text in the plot data. Defaults to False.

    Returns:
        Dictionary containing the complete 3D scatter plot figure with data and layout.
    """
    keys_dict = config["keys"]

    opacity = np.linspace(1, 0.2, decay + 1)

    # save filter key word arguments to Redis
    filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
    if filter_kwargs is None:
        cat_keys = []
        num_keys = []
    else:
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]

    # get visibility table from Redis
    visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])

    # get frame list from Redis
    frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])
    if frame_list is None:
        frame_list = []

    # The slider position arrives as callback state, so it can still be the one
    # the previous dataset left behind. Nothing below survives it pointing past
    # the end of this dataset's frames.
    clamped_idx = clamp_frame_index(frame_list, frame_idx)
    if clamped_idx is None:
        raise PreventUpdate
    frame_idx = clamped_idx

    manifest = get_manifest(session_id)
    # Sidecars belong to the log that recorded this frame, which with logs
    # combined is not necessarily the primary one.
    stem = get_frame_stem(session_id, frame_idx)

    # prepare figure key word arguments
    fig_kwargs = prepare_figure_kwargs(
        config,
        num_keys,
        num_values,
        c_key,
        bool(size_vary),
        frame_list,
        frame_idx,
        # Axis ranges are fixed for the whole session, so they have to cover
        # every combined log's reference rather than just this frame's.
        ref_bounds=get_combined_reference_bounds(manifest, get_log_stems(session_id)),
    )

    # get a single frame data from Redis
    data = cache_get(session_id, CACHE_KEYS["frame_data"], str(frame_list[frame_idx]))

    if data is None:
        raise ValueError(f"No data found for frame {frame_list[frame_idx]}")

    filterd_frame = filter_all(
        data, num_keys, num_values, cat_keys, cat_values, visible_table, visible_list
    )

    result = get_scatter3d_data(filterd_frame, hover=keys_dict, **fig_kwargs)
    fig = result["scatter_data"]
    hover_list = result["hover_strings"]

    if load_hover and hover_list:
        for idx, hover_str in enumerate(hover_list):
            fig[idx]["text"] = hover_str  # type: ignore
            fig[idx]["hovertemplate"] = "%{text}"  # type: ignore

    if fig_kwargs["c_type"] == "numerical":
        if "marker" in fig[0]:
            fig[0]["marker"]["colorscale"] = colormap  # type: ignore

    if decay > 0:
        for val in range(1, decay + 1):
            if (frame_idx - val) >= 0:
                # get cached frame data
                cached_data = cache_get(
                    session_id,
                    CACHE_KEYS["frame_data"],
                    str(frame_list[frame_idx - val]),
                )
                if cached_data is None:
                    raise ValueError(
                        f"No cached data found for decay frame "
                        f"{frame_list[frame_idx - val]} (session: {session_id})"
                    )

                # filter the data
                frame_temp = filter_all(
                    cached_data,
                    num_keys,
                    num_values,
                    cat_keys,
                    cat_values,
                    visible_table,
                    visible_list,
                )
                fig_kwargs["opacity"] = opacity[val]
                fig_kwargs["name"] = (
                    "Index: "
                    + str(frame_idx - val)
                    + " ("
                    + keys_dict[config["slider"]]["description"]
                    + ": "
                    + str(frame_list[frame_idx - val])
                    + ")"
                )

                result = get_scatter3d_data(frame_temp, hover=keys_dict, **fig_kwargs)
                new_fig = result["scatter_data"]
                hover_list = result["hover_strings"]
                if load_hover and hover_list:
                    for idx, hover_str in enumerate(hover_list):
                        new_fig[idx]["text"] = hover_str  # type: ignore
                        new_fig[idx]["hovertemplate"] = "%{text}"  # type: ignore

                if fig_kwargs["c_type"] == "numerical":
                    if "marker" in new_fig[0]:
                        new_fig[0]["marker"]["colorscale"] = colormap  # type: ignore

                fig = fig + new_fig

            else:
                break

    if fig_kwargs.get("ref_from_sidecar"):
        # The pose is per frame, so it is read from the sidecar rather than from
        # the filtered frame -- filtering out every detection does not move the
        # host vehicle.
        pose = get_reference_pose(manifest, stem, frame_list[frame_idx])
        fig_ref = (
            get_reference_traces(
                data_frame=filterd_frame,
                name=fig_kwargs.get("ref_name", None),
                display=fig_kwargs.get("ref_display"),
                pose=pose,
            )
            if pose is not None
            else []
        )
    elif fig_kwargs["x_ref"] is not None and fig_kwargs["y_ref"] is not None:
        fig_ref = get_reference_traces(
            data_frame=filterd_frame,
            x_key=fig_kwargs["x_ref"],
            y_key=fig_kwargs["y_ref"],
            z_key=fig_kwargs["z_ref"],
            name=fig_kwargs.get("ref_name", None),
            display=fig_kwargs.get("ref_display"),
        )
    else:
        # No sidecar and no ref columns: nothing here places the reference.
        # A reference the manifest declared still draws, at the origin; a
        # dataset that declared none draws nothing.
        fig_ref = get_reference_traces(
            data_frame=filterd_frame,
            name=fig_kwargs.get("ref_name", None),
            display=fig_kwargs.get("ref_display"),
        )

    # The cloud is a display-only backdrop: read once per frame, never refiltered,
    # and drawn first so the radar detections render on top of it.
    cloud_trace = get_cloud_trace(manifest, stem, frame_list[frame_idx])
    fig_cloud = [cloud_trace] if cloud_trace is not None else []

    layout = get_scatter3d_layout(**fig_kwargs)

    fig = {"data": fig_cloud + fig + fig_ref, "layout": layout}

    return fig


def process_overlay_frame(
    frame_idx: int,
    config: Dict[str, Any],
    cat_values: List[List[str]],
    num_values: List[Tuple[float, float]],
    colormap: str,
    visible_list: List[str],
    c_key: str,
    size_vary: str,
    session_id: str,
    file: str,
    file_list: List[str],
) -> Dict[str, Any]:
    """
    Process an overlay frame combining data from multiple files into a single 3D scatter plot.

    Args:
        frame_idx: Index of the frame to process.
        config: Configuration dictionary containing plot settings and key definitions.
        cat_values: List of lists containing selected categorical values for filtering.
        num_values: List of (min, max) tuples for numerical value filtering.
        colormap: Name of the colormap to apply to the scatter plot.
        visible_list: List of visibility filter values.
        c_key: Column name for color mapping.
        size_vary: String indicating whether to vary marker sizes.
        session_id: Unique session identifier for cache access.
        file: JSON string containing primary file path and name information.
        file_list: List of JSON strings representing additional files to overlay.

    Returns:
        Dictionary containing the complete 3D scatter plot figure with overlaid data and layout.
    """
    # save filter key word arguments to Redis
    filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
    if filter_kwargs is None:
        cat_keys = []
        num_keys = []
    else:
        cat_keys = filter_kwargs["cat_keys"]
        num_keys = filter_kwargs["num_keys"]

    # get visibility table from Redis
    visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])

    # get frame list from Redis
    frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])
    if frame_list is None:
        frame_list = []

    clamped_idx = clamp_frame_index(frame_list, frame_idx)
    if clamped_idx is None:
        raise PreventUpdate
    frame_idx = clamped_idx

    # prepare figure key word arguments. Overlaying every frame at once leaves
    # no single frame for a per-frame pose to belong to, so the sidecar draws
    # nothing here -- but it still owns the reference, so the table's ref
    # columns stay suppressed rather than standing in for it.
    fig_kwargs = prepare_figure_kwargs(
        config,
        num_keys,
        num_values,
        c_key,
        bool(size_vary),
        frame_list,
        frame_idx,
        ref_bounds=get_combined_reference_bounds(
            get_manifest(session_id), get_log_stems(session_id)
        ),
    )

    # overlay all the frames
    data = load_data(file_list, file)
    filterd_frame = filter_all(
        data, num_keys, num_values, cat_keys, cat_values, visible_table, visible_list
    )

    # generate the graph
    fig = get_scatter3d(filterd_frame, hover=config["keys"], **fig_kwargs)

    if fig_kwargs["c_type"] == "numerical":
        if "marker" in fig["data"][0]:
            fig["data"][0]["marker"]["colorscale"] = colormap

    return fig
