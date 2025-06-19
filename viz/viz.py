"""SensorView Visualization Module

Core visualization module providing high-level plotting functions for sensor data
visualization in the SensorView application.

Main Components:
--------------
1. Scatter Plot Generation:
   - 3D scatter plots with reference points
   - 2D scatter plots with color mapping
   - Animated scatter plots with decay effects

2. Heatmap Generation:
   - 2D density visualizations
   - Customizable color scales
   - Automatic range calculation

3. Animation Support:
   - Frame-by-frame animation
   - Decay trail effects
   - Image overlay support

Features:
--------
- Interactive 3D/2D visualizations
- Multiple color mapping modes
- Customizable hover information
- Animation frame management
- Reference point overlays
- Image integration

Dependencies:
------------
- numpy
- pandas
- plotly (implicit through layout/data modules)
- Base64 encoding for images

Usage:
------
from viz.viz import get_scatter3d, get_scatter2d, get_heatmap

Author: Zhengyu Peng
Email: zpeng.me@gmail.com
Website: https://zpeng.me
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import List, Dict, Any, Optional
import base64
import numpy as np
import pandas as pd

import plotly.io as pio

from .graph_data import get_scatter3d_data, get_ref_scatter3d_data
from .graph_layout import get_scatter3d_layout


def get_scatter3d(
    data_frame: pd.DataFrame,
    x_key: str,
    y_key: str,
    z_key: str,
    c_key: str,
    hover: Optional[Dict[str, Dict[str, Any]]] = None,
    x_ref: Optional[str] = None,
    y_ref: Optional[str] = None,
    z_ref: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Generate a 3D scatter plot with optional reference points.

    Args:
        data_frame: DataFrame containing the plot data.
        x_key: Column name for x-axis coordinates.
        y_key: Column name for y-axis coordinates.
        z_key: Column name for z-axis coordinates.
        c_key: Column name for color mapping.
        hover: Configuration for hover tooltips.
        x_ref: Optional column name for reference x coordinates.
        y_ref: Optional column name for reference y coordinates.
        z_ref: Optional column name for reference z coordinates.
        **kwargs: Additional parameters:
            - ref_name: Name for reference points
            - Other parameters passed to get_scatter3d_data

    Returns:
        Dictionary containing plot data and layout configuration.
    """
    ref_name = kwargs.get("ref_name", None)

    fig_dict = get_scatter3d_data(
        data_frame, x_key, y_key, z_key, c_key, hover=hover, **kwargs
    )

    if x_ref is None or y_ref is None or x_ref == "None" or y_ref == "None":
        data = fig_dict["scatter_data"]
    else:
        if z_ref == "None":
            z_ref = None
        data = fig_dict["scatter_data"] + [
            get_ref_scatter3d_data(
                data_frame=data_frame,
                x_key=x_ref,
                y_key=y_ref,
                z_key=z_ref,
                name=ref_name,
            )
        ]

    if fig_dict["hover_strings"]:
        for idx, hover_str in enumerate(fig_dict["hover_strings"]):
            data[idx]["text"] = hover_str
            data[idx]["hovertemplate"] = "%{text}"

    return {
        "data": data,
        "layout": get_scatter3d_layout(**kwargs),
    }


def get_heatmap(
    data_frame: pd.DataFrame,
    x_key: str,
    y_key: str,
    x_label: Optional[str] = None,
    y_label: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a 2D heatmap visualization.

    Args:
        data_frame: DataFrame containing the plot data.
        x_key: Column name for x-axis values.
        y_key: Column name for y-axis values.
        x_label: Optional custom label for x-axis. Defaults to x_key.
        y_label: Optional custom label for y-axis. Defaults to y_key.

    Returns:
        Dictionary containing heatmap data and layout configuration.
    """
    if x_label is None:
        x_label = x_key

    if y_label is None:
        y_label = y_key

    return {
        "data": [
            {
                "type": "histogram2dcontour",
                "x": data_frame[x_key],
                "y": data_frame[y_key],
                "colorscale": "Jet",
            }
        ],
        "layout": {
            "xaxis": {"title": x_label},
            "yaxis": {"title": y_label},
        },
    }


def get_scatter2d(
    data_frame: pd.DataFrame,
    x_key: str,
    y_key: str,
    c_key: str,
    x_label: Optional[str] = None,
    y_label: Optional[str] = None,
    uirevision: str = "no_change",
    colormap: str = "Jet",
    margin: Optional[Dict[str, int]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Generate a 2D scatter plot with color mapping.

    Args:
        data_frame: DataFrame containing the plot data.
        x_key: Column name for x-axis coordinates.
        y_key: Column name for y-axis coordinates.
        c_key: Column name for color mapping.
        x_label: Optional custom label for x-axis. Defaults to x_key.
        y_label: Optional custom label for y-axis. Defaults to y_key.
        uirevision: Plotly UI revision identifier.
        colormap: Name of the colormap to use.
        margin: Plot margins in pixels.
        **kwargs: Additional parameters:
            - linewidth: Width of marker borders (default: 0)
            - c_label: Custom label for color scale
            - c_type: Color mapping type ('numerical' or 'categorical')

    Returns:
        Dictionary containing scatter plot data and layout configuration.
    """
    linewidth = kwargs.get("linewidth", 0)

    if margin is None:
        margin = {"l": 40, "r": 40, "b": 40, "t": 60}

    if x_label is None:
        x_label = x_key

    if y_label is None:
        y_label = y_key

    c_label = kwargs.get("c_label", c_key)
    c_type = kwargs.get("c_type", "numerical")

    if c_type == "numerical":
        return {
            "data": [
                {
                    "type": "scattergl",
                    "ids": data_frame.index,
                    "x": data_frame[x_key],
                    "y": data_frame[y_key],
                    "mode": "markers",
                    "marker": {
                        "size": 6,
                        "color": data_frame[c_key],
                        "colorscale": colormap,
                        "opacity": 0.8,
                        "colorbar": {
                            "title": c_label,
                        },
                        "line": {
                            "color": "#FFFFFF",
                            "width": linewidth,
                        },
                    },
                }
            ],
            "layout": {
                "xaxis": {"title": x_label},
                "yaxis": {"title": y_label},
                "margin": margin,
                "uirevision": uirevision,
            },
        }

    if c_type == "categorical":
        data = []
        color_list = pd.unique(data_frame[c_key])
        for c_item in color_list:
            new_list = data_frame[data_frame[c_key] == c_item]
            data.append(
                {
                    "type": "scattergl",
                    "ids": new_list.index,
                    "x": new_list[x_key],
                    "y": new_list[y_key],
                    "mode": "markers",
                    "marker": {
                        "size": 6,
                        "opacity": 0.8,
                        "line": {
                            "color": "#FFFFFF",
                            "width": linewidth,
                        },
                    },
                    "name": c_item,
                }
            )
        return {
            "data": data,
            "layout": {
                "xaxis": {"title": x_label},
                "yaxis": {"title": y_label},
                "margin": margin,
                "uirevision": uirevision,
            },
        }


def frame_args(duration: int) -> Dict[str, Any]:
    """
    Generate animation frame configuration.

    Args:
        duration: Frame duration in milliseconds.

    Returns:
        Dictionary containing animation timing and transition settings.
    """
    return {
        "frame": {"duration": duration},
        "mode": "immediate",
        "fromcurrent": True,
        "transition": {"duration": duration, "easing": "quadratic-in-out"},
    }


def process_image(img_path: str) -> Optional[str]:
    """
    Process and encode an image file to base64 format.

    Args:
        img_path: Path to the image file.

    Returns:
        Base64 encoded image string with data URI scheme prefix, or None if processing fails.
    """
    try:
        with open(img_path, "rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode()
            return f"data:image/jpeg;base64,{encoded}"
    except (FileNotFoundError, NotADirectoryError, IOError):
        return None


def get_animation_data(
    data_frame: pd.DataFrame,
    x_key: str,
    y_key: str,
    z_key: str,
    x_ref: Optional[str] = None,
    y_ref: Optional[str] = None,
    z_ref: Optional[str] = None,
    frame_key: str = "Frame",
    img_list: Optional[List[str]] = None,
    colormap: Optional[str] = None,
    decay: int = 0,
    dark_mode: bool = True,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Generate animated 3D scatter plot configuration.

    Args:
        data_frame: DataFrame containing animation data.
        x_key: Column name for x-axis coordinates.
        y_key: Column name for y-axis coordinates.
        z_key: Column name for z-axis coordinates.
        x_ref: Optional column name for reference x coordinates.
        y_ref: Optional column name for reference y coordinates.
        frame_key: Column name containing frame indices.
        img_list: Optional list of image paths for each frame.
        colormap: Optional custom colormap name.
        decay: Number of trailing frames to show with decreasing opacity.
        **kwargs: Additional parameters:
            - keys_dict: Dictionary of column descriptions
            - Other parameters passed to get_scatter3d_layout

    Returns:
        Dictionary containing:
            - data: Initial frame plot data
            - frames: List of animation frames
            - layout: Plot layout configuration
    """
    # Pre-calculate frame data
    frame_list = data_frame[frame_key].unique()
    if len(frame_list) == 0:
        return {"data": [], "frames": [], "layout": get_scatter3d_layout(**kwargs)}

    # Pre-calculate opacity values
    opacity_values = np.linspace(1, 0.2, decay + 1)

    # Cache base configuration
    base_kwargs = {
        "keys_dict": kwargs.get("keys_dict", {}),
        "opacity": opacity_values[0],
        **kwargs,
    }

    def create_frame_data(frame_idx: int, current_idx: int) -> Dict[str, Any]:
        """Helper function to create single frame data"""
        filtered_df = data_frame[data_frame[frame_key] == frame_idx].reset_index()

        # Update frame-specific kwargs
        frame_kwargs = base_kwargs.copy()
        frame_kwargs["name"] = f"Frame: {frame_idx}"

        # Process image if available
        if img_list and current_idx < len(img_list):
            frame_kwargs["image"] = process_image(img_list[current_idx])

        # Get scatter data
        fig_dict = get_scatter3d_data(
            filtered_df,
            x_key,
            y_key,
            z_key,
            hover=frame_kwargs["keys_dict"],
            **frame_kwargs,
        )

        fig = fig_dict["scatter_data"]
        hover_list = fig_dict["hover_strings"]

        # Apply hover strings and colormap
        if hover_list:
            for scatter, hover_str in zip(fig, hover_list):
                scatter["text"] = hover_str
                scatter["hovertemplate"] = "%{text}"

        if colormap and fig and "marker" in fig[0]:
            fig[0]["marker"]["colorscale"] = colormap

        # Add reference data if needed
        if x_ref is not None and y_ref is not None:
            ref_data = [
                get_ref_scatter3d_data(
                    data_frame=filtered_df,
                    x_key=x_ref,
                    y_key=y_ref,
                    z_key=z_ref,
                    name="Host Vehicle",
                )
            ]
            fig = ref_data + fig

        return {
            "data": fig,
            "layout": get_scatter3d_layout(**frame_kwargs),
            "name": str(frame_idx),
        }

    # Generate frames with decay
    ani_frames = []
    for idx, frame_idx in enumerate(frame_list[decay:], decay):
        current_frame = create_frame_data(frame_idx, idx)

        # Handle decay frames
        if decay > 0:
            decay_data = []
            for d_idx, opacity in enumerate(opacity_values[1:], 1):
                if idx - d_idx >= 0:
                    decay_kwargs = base_kwargs.copy()
                    decay_kwargs.update(
                        {
                            "name": f"Frame: {frame_list[idx - d_idx]}",
                            "opacity": opacity,
                        }
                    )

                    decay_results = get_scatter3d_data(
                        data_frame[
                            data_frame[frame_key] == frame_list[idx - d_idx]
                        ].reset_index(),
                        x_key,
                        y_key,
                        z_key,
                        hover=decay_kwargs["keys_dict"],
                        **decay_kwargs,
                    )

                    decay_fig = decay_results["scatter_data"]
                    if colormap and decay_fig and "marker" in decay_fig[0]:
                        decay_fig[0]["marker"]["colorscale"] = colormap

                    decay_data.extend(decay_fig)

        ani_frames.append(current_frame)

    # Create slider configuration
    sliders = [
        {
            "pad": {"b": 10, "t": 10},
            "len": 0.9,
            "x": 0.1,
            "y": 0,
            "steps": [
                {
                    "args": [[f["name"]], frame_args(0)],
                    "label": str(k),
                    "method": "animate",
                }
                for k, f in enumerate(ani_frames)
            ],
        }
    ]

    # Create final layout
    layout_kwargs = kwargs.copy()
    if img_list:
        layout_kwargs["image"] = process_image(img_list[0])

    figure_layout = get_scatter3d_layout(**layout_kwargs)

    if dark_mode:
        figure_layout["template"] = pio.templates["plotly_dark"]
    else:
        figure_layout["template"] = pio.templates["plotly"]

    figure_layout.update(
        {
            "updatemenus": [
                {
                    "bgcolor": "#9E9E9E",
                    "font": {"size": 10, "color": "#455A64"},
                    "buttons": [
                        {
                            "args": [None, frame_args(50)],
                            "label": "Play",
                            "method": "animate",
                        },
                        {
                            "args": [[None], frame_args(0)],
                            "label": "Stop",
                            "method": "animate",
                        },
                    ],
                    "direction": "left",
                    "pad": {"r": 10, "t": 30, "l": 20, "b": 10},
                    "type": "buttons",
                    "x": 0.1,
                    "xanchor": "right",
                    "y": 0,
                    "yanchor": "top",
                }
            ],
            "sliders": sliders,
        }
    )

    return {
        "data": ani_frames[0]["data"] if ani_frames else [],
        "frames": ani_frames,
        "layout": figure_layout,
    }
