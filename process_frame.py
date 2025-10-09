"""Frame Processing Module for SensorView

This module handles the processing and visualization of individual data frames
in the SensorView application.

Core Functions:
--------------
1. Single Frame Processing:
   - Data filtering and preparation
   - 3D scatter plot generation
   - Reference frame overlay
   - Decay effect implementation

2. Overlay Frame Processing:
   - Multi-file data combination
   - Unified visualization generation
   - Data filtering across sources

Features:
---------
- Frame-by-frame processing
- Multi-file data integration
- Customizable visualization parameters
- Cache-aware data handling
- Reference frame support
- Decay effect for temporal visualization

Dependencies:
------------
- numpy
- pandas
- plotly
- custom visualization modules (viz.*)
- utility functions (utils.py)

Usage:
------
Primarily used by the main application server (app.py) for:
- Real-time frame processing
- Data visualization generation
- Multi-frame overlay effects

Author: Zhengyu Peng
Email: zpeng.me@gmail.com
Website: https://zpeng.me
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Dict, List, Union, Any
import json
import os

import numpy as np

from utils import filter_all
from utils import cache_get
from utils import load_data
from utils import load_image
from utils import prepare_figure_kwargs

from viz.viz import get_scatter3d
from viz.graph_data import get_ref_scatter3d_data
from viz.graph_data import get_scatter3d_data
from viz.graph_layout import get_scatter3d_layout

from app_config import CACHE_KEYS


def process_single_frame(
    config: Dict[str, Any],
    cat_values: Dict[str, List[str]],
    num_values: List[Union[float, int]],
    colormap: str,
    visible_list: List[str],
    c_key: str,
    size_vary: str,
    decay: int,
    session_id: str,
    file: str,
    frame_idx: int = 0,
    load_hover: bool = False,
) -> Dict[str, Any]:
    """
    Process a single frame of data and generate a 3D scatter plot figure with optional decay effect.

    Args:
        config: Configuration dictionary containing plot settings and key definitions.
        cat_values: Dictionary mapping categorical column names to lists of
                    selected values for filtering.
        num_values: List of numerical values for filtering (min/max ranges).
        colormap: Name of the colormap to apply to the scatter plot.
        visible_list: List of visibility filter values.
        c_key: Column name for color mapping.
        decay: Number of previous frames to include with decreasing opacity.
        session_id: Unique session identifier for cache access.
        file: JSON string containing file path and name information.
        frame_idx: Index of the current frame to process.
        load_hover: Whether to include hover text in the plot data.

    Returns:
        Dictionary containing the complete 3D scatter plot figure with data and layout.
    """
    keys_dict = config["keys"]

    opacity = np.linspace(1, 0.2, decay + 1)

    # save filter key word arguments to Redis
    filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
    cat_keys = filter_kwargs["cat_keys"]
    num_keys = filter_kwargs["num_keys"]

    # get visibility table from Redis
    visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])

    # get frame list from Redis
    frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])

    # prepare figure key word arguments
    fig_kwargs = prepare_figure_kwargs(
        config,
        frame_list,
        c_key,
        bool(size_vary),
        num_keys,
        num_values,
        frame_idx,
    )

    file = json.loads(file)
    img_path = os.path.join(
        file["path"], file["name"][0:-4], str(frame_list[frame_idx]) + ".jpg"
    )

    # encode image frame
    fig_kwargs["image"] = load_image(img_path)

    # get a single frame data from Redis
    data = cache_get(session_id, CACHE_KEYS["frame_data"], str(frame_list[frame_idx]))

    filterd_frame = filter_all(
        data, num_keys, num_values, cat_keys, cat_values, visible_table, visible_list
    )

    result = get_scatter3d_data(filterd_frame, hover=keys_dict, **fig_kwargs)
    fig = result["scatter_data"]
    hover_list = result["hover_strings"]

    if load_hover and hover_list:
        for idx, hover_str in enumerate(hover_list):
            fig[idx]["text"] = hover_str
            fig[idx]["hovertemplate"] = "%{text}"

    if fig_kwargs["c_type"] == "numerical":
        if "marker" in fig[0]:
            fig[0]["marker"]["colorscale"] = colormap

    if decay > 0:
        for val in range(1, decay + 1):
            if (frame_idx - val) >= 0:
                # filter the data
                frame_temp = filter_all(
                    cache_get(
                        session_id,
                        CACHE_KEYS["frame_data"],
                        str(frame_list[frame_idx - val]),
                    ),
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
                        new_fig[idx]["text"] = hover_str
                        new_fig[idx]["hovertemplate"] = "%{text}"

                if fig_kwargs["c_type"] == "numerical":
                    if "marker" in new_fig[0]:
                        new_fig[0]["marker"]["colorscale"] = colormap

                fig = fig + new_fig

            else:
                break

    if fig_kwargs["x_ref"] is not None and fig_kwargs["y_ref"] is not None:
        fig_ref = [
            get_ref_scatter3d_data(
                data_frame=filterd_frame,
                x_key=fig_kwargs["x_ref"],
                y_key=fig_kwargs["y_ref"],
                z_key=fig_kwargs["z_ref"],
                name=fig_kwargs.get("ref_name", None),
            )
        ]
    else:
        fig_ref = []

    layout = get_scatter3d_layout(**fig_kwargs)

    fig = {"data": fig + fig_ref, "layout": layout}

    return fig


def process_overlay_frame(
    frame_idx: int,
    config: Dict[str, Any],
    cat_values: Dict[str, List[str]],
    num_values: List[Union[float, int]],
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
        cat_values: Dictionary mapping categorical column names to lists of
                    selected values for filtering.
        num_values: List of numerical values for filtering (min/max ranges).
        colormap: Name of the colormap to apply to the scatter plot.
        visible_list: List of visibility filter values.
        c_key: Column name for color mapping.
        session_id: Unique session identifier for cache access.
        file: JSON string containing primary file path and name information.
        file_list: List of JSON strings representing additional files to overlay.

    Returns:
        Dictionary containing the complete 3D scatter plot figure with overlaid data and layout.
    """
    # save filter key word arguments to Redis
    filter_kwargs = cache_get(session_id, CACHE_KEYS["filter_kwargs"])
    cat_keys = filter_kwargs["cat_keys"]
    num_keys = filter_kwargs["num_keys"]

    # get visibility table from Redis
    visible_table = cache_get(session_id, CACHE_KEYS["visible_table"])

    # get frame list from Redis
    frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])

    # prepare figure key word arguments
    fig_kwargs = prepare_figure_kwargs(
        config,
        frame_list,
        c_key,
        bool(size_vary),
        num_keys,
        num_values,
        frame_idx,
    )

    # overlay all the frames
    # get data from .feather file on the disk
    data = load_data(file_list, file)
    filterd_frame = filter_all(
        data, num_keys, num_values, cat_keys, cat_values, visible_table, visible_list
    )
    fig_kwargs["image"] = None

    # generate the graph
    fig = get_scatter3d(filterd_frame, hover=config["keys"], **fig_kwargs)

    if fig_kwargs["c_type"] == "numerical":
        if "marker" in fig["data"][0]:
            fig["data"][0]["marker"]["colorscale"] = colormap

    return fig
