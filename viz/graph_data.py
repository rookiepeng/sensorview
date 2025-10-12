"""

SensorView Graph Data Generation Module

Module handling the generation and processing of plot data for various visualization
types in the SensorView application.

Core Components:
--------------
1. Data Processing:
   - Reference point generation
   - Scatter plot data creation
   - Hover text formatting
   - Color mapping

2. Plot Configuration:
   - Marker styling
   - Color scale management
   - Legend configuration
   - Hover template generation

3. Optimization Features:
   - Efficient data structure creation
   - Vectorized operations
   - Memory management
   - Cached calculations

Key Functions:
------------
- Reference scatter plot data generation
- Main scatter plot data creation
- Hover information formatting
- Color mapping configuration

Dependencies:
------------
- numpy for efficient array operations
- pandas for data manipulation
- Standard Python typing

Usage:
------
from viz.graph_data import get_scatter3d_data, get_ref_scatter3d_data

Author: Zhengyu Peng
Email: zpeng.me@gmail.com
Website: https://zpeng.me
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import List, Dict, Union, Any, Optional
import numpy as np
import pandas as pd


def get_ref_scatter3d_data(
    data_frame: pd.DataFrame,
    x_key: str,
    y_key: str,
    z_key: Optional[str] = None,
    name: Optional[str] = "Origin",
) -> Dict[str, Any]:
    """
    Generate reference data for a 3D scatter plot.

    Args:
        data_frame: DataFrame containing the source data.
        x_key: Column name for x-axis coordinates.
        y_key: Column name for y-axis coordinates.
        z_key: Optional column name for z-axis coordinates.
        name: Optional label for the reference point in the plot.

    Returns:
        Dictionary containing plot data with coordinates, styling, and hover information.
    """
    if data_frame.empty:
        return {"mode": "markers", "type": "scatter3d", "x": [], "y": [], "z": []}

    # Direct value access for first row
    x_val = float(data_frame[x_key].iloc[0])
    y_val = float(data_frame[y_key].iloc[0])
    z_val = 0 if z_key is None else float(data_frame[z_key].iloc[0])

    # Create marker configuration once
    marker_config = {
        "color": "rgb(255, 255, 255)",
        "size": 6,
        "opacity": 1,
        "symbol": "circle",
        "line": {
            "color": "#000000",
            "width": 2,
        },
    }

    # Construct the figure data directly
    fig_data = {
        "type": "scatter3d",
        "x": [x_val],
        "y": [y_val],
        "z": [z_val],
        "hovertemplate": "Lateral: %{x:.2f} m<br>Longitudinal: %{y:.2f} m<br>",
        "mode": "markers",
        "name": name,
        "marker": marker_config,
    }

    return fig_data


def get_scatter3d_data(
    data_frame: pd.DataFrame,
    x_key: str,
    y_key: str,
    z_key: str,
    c_key: str,
    hover: Optional[Dict[str, Dict[str, Any]]] = None,
    **kwargs: Any,
) -> Dict[str, Union[List[Dict[str, Any]], List[List[str]]]]:
    """
    Generate data for a 3D scatter plot with hover information.

    Args:
        data_frame: DataFrame containing the source data.
        x_key: Column name for x-axis coordinates.
        y_key: Column name for y-axis coordinates.
        z_key: Column name for z-axis coordinates.
        c_key: Column name for color mapping.
        hover: Configuration for hover tooltips. Dictionary mapping column names
              to display settings (description, format, decimal places).
        **kwargs: Additional plot configuration parameters including:
            - name: Plot name
            - c_type: Color mapping type ('numerical' or 'categorical')
            - opacity: Marker opacity (default: 0.8)
            - showlegend: Show legend (default: True)
            - c_range: Color range [min, max]

    Returns:
        Dictionary containing:
            - scatter_data: List of scatter plot traces
            - hover_strings: List of hover text arrays for each trace
    """
    if data_frame.empty:
        return {
            "scatter_data": [
                {"mode": "markers", "type": "scatter3d", "x": [], "y": [], "z": []}
            ],
            "hover_strings": [],
        }

    plot_config = {
        "c_label": hover[c_key]["description"] if hover and c_key in hover else c_key,
        "name": kwargs.get("name", None),
        "c_type": (
            hover[c_key]["type"]
            if hover and c_key in hover
            else kwargs.get("c_type", "numerical")
        ),
        "opacity": kwargs.get("opacity", 1.0),
        "showlegend": kwargs.get("showlegend", True),
        "marker_size": 3,
        "line_color": "#757575",
        "line_width": 0,
    }

    enable_size_vary = kwargs.get("size_vary", False)

    def format_hover(series: pd.Series, config: Dict[str, Any]) -> pd.Series:
        """
        Format series values for hover display according to configuration.

        Args:
            series: Data series to format.
            config: Formatting configuration containing either 'format' or 'decimal' key.

        Returns:
            Formatted series as strings.
        """
        if "format" in config:
            return series.map(config["format"].format)
        if "decimal" in config:
            format_str = "{:,." + str(config["decimal"]) + "f}"
            return series.map(format_str.format)
        return series.astype(str)

    def process_hover(df: pd.DataFrame) -> np.ndarray:
        """
        Process DataFrame columns to generate hover text.

        Args:
            df: Source DataFrame.

        Returns:
            Array of formatted hover strings for each row.
        """
        if not hover:
            return np.full(len(df), "")
        hover_parts = []
        for key, config in hover.items():
            if key in df.columns:
                formatted_values = format_hover(df[key], config)
                hover_parts.append(
                    config.get("description", key) + ": " + formatted_values + "<br>"
                )
        return np.sum(hover_parts, axis=0) if hover_parts else np.full(len(df), "")

    def create_scatter(
        df: pd.DataFrame,
        name: Optional[str] = None,
        color: Optional[Union[List[float], np.ndarray]] = None,
        size_offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Create a scatter plot trace configuration.

        Args:
            df: Source DataFrame.
            name: Trace name.
            color: Color values for markers.

        Returns:
            Scatter plot trace configuration dictionary.
        """
        scatter = {
            "type": "scatter3d",
            "ids": df.index.tolist(),
            "x": df[x_key].tolist(),
            "y": df[y_key].tolist(),
            "z": df[z_key].tolist(),
            "mode": "markers",
            "name": name,
            "showlegend": plot_config["showlegend"],
        }

        marker = {
            "size": plot_config["marker_size"] + size_offset,
            "opacity": plot_config["opacity"],
            "line": {
                "color": plot_config["line_color"],
                "width": plot_config["line_width"],
            },
        }

        if color is not None:
            marker.update(
                {
                    "color": color,
                    "colorbar": {
                        "title": {"text": plot_config["c_label"], "side": "right"}
                    },
                    "cmin": kwargs.get("c_range", [np.min(color), np.max(color)])[0],
                    "cmax": kwargs.get("c_range", [np.min(color), np.max(color)])[1],
                }
            )

        scatter["marker"] = marker
        return scatter

    result = {"scatter_data": [], "hover_strings": []}

    if plot_config["c_type"] == "numerical":
        hover_text = process_hover(data_frame)
        color_values = data_frame[c_key].tolist()
        result["scatter_data"] = [
            create_scatter(data_frame, plot_config["name"], color_values)
        ]
        result["hover_strings"] = [hover_text.tolist()]
    else:
        grouped = data_frame.groupby(c_key)
        sorted_groups = sorted(grouped)
        num_groups = len(sorted_groups) if enable_size_vary else 0

        for i, (name, group) in enumerate(sorted_groups):
            hover_text = process_hover(group)
            size_offset = (num_groups - 1 - i) if enable_size_vary else 0

            result["scatter_data"].append(
                create_scatter(group, str(name), size_offset=size_offset)
            )
            result["hover_strings"].append(hover_text.tolist())

    return result
