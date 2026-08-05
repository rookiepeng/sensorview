"""SensorView Graph Data Generation Module

Handles generation and processing of plot data for various visualization types
including reference point generation, scatter plot data creation, hover text
formatting, and color mapping.

Key functions: get_scatter3d_data(), get_reference_traces()

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import List, Dict, Tuple, Union, Any, Optional
import numpy as np
import pandas as pd


REF_HOVER = "Lateral: %{x:.2f} m<br>Longitudinal: %{y:.2f} m<br>"

# Unit-cube corners, in the vertex order Plotly's mesh3d cube triangulation
# below is written against. Corners 0-3 are the bottom face, 4-7 the top.
_BOX_CORNERS = (
    (-1, -1, -1),
    (-1, +1, -1),
    (+1, +1, -1),
    (+1, -1, -1),
    (-1, -1, +1),
    (-1, +1, +1),
    (+1, +1, +1),
    (+1, -1, +1),
)

# The 6 faces, each as its four corners in cyclic order.
_BOX_QUADS = (
    (0, 1, 2, 3),  # z low
    (4, 5, 6, 7),  # z high
    (0, 3, 7, 4),  # y low
    (1, 2, 6, 5),  # y high
    (0, 1, 5, 4),  # x low
    (3, 2, 6, 7),  # x high
)

# Two triangles per face, fanned from its first corner. Derived rather than
# tabulated: a quad only tiles when its triangles meet along the diagonal, and
# an index table transposed by one digit still looks plausible -- it fails as a
# face that overlaps itself on one half and is missing on the other.
_BOX_FACES = tuple(
    triangle
    for corner_a, corner_b, corner_c, corner_d in _BOX_QUADS
    for triangle in (
        (corner_a, corner_b, corner_c),
        (corner_a, corner_c, corner_d),
    )
)

# The 12 edges, as corner pairs: bottom face, top face, then the uprights.
_BOX_EDGES = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 0),
    (4, 5),
    (5, 6),
    (6, 7),
    (7, 4),
    (0, 4),
    (1, 5),
    (2, 6),
    (3, 7),
)


def _ref_point(
    data_frame: pd.DataFrame,
    x_key: str,
    y_key: str,
    z_key: Optional[str],
) -> Tuple[float, float, float]:
    """
    Read the reference position out of a frame.

    Args:
        data_frame: Source data for the frame.
        x_key: Column holding the reference x coordinate.
        y_key: Column holding the reference y coordinate.
        z_key: Optional column holding the reference z coordinate.

    Returns:
        ``(x, y, z)`` from the first row; z is 0 when no column is given.
    """
    return (
        float(data_frame[x_key].iloc[0]),
        float(data_frame[y_key].iloc[0]),
        0.0 if z_key is None else float(data_frame[z_key].iloc[0]),
    )


def get_ref_scatter3d_data(
    data_frame: pd.DataFrame,
    x_key: str,
    y_key: str,
    z_key: Optional[str] = None,
    name: Optional[str] = "Origin",
    display: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate reference data for a 3D scatter plot.

    Args:
        data_frame: DataFrame containing the source data.
        x_key: Column name for x-axis coordinates.
        y_key: Column name for y-axis coordinates.
        z_key: Optional column name for z-axis coordinates.
        name: Optional label for the reference point in the plot.
        display: Optional manifest styling (``color``, ``size``, ``opacity``,
            ``symbol``, ``line_color``, ``line_width``).

    Returns:
        Dictionary containing plot data with coordinates, styling, and hover information.
    """
    if data_frame.empty:
        return {"mode": "markers", "type": "scatter3d", "x": [], "y": [], "z": []}

    display = display or {}
    x_val, y_val, z_val = _ref_point(data_frame, x_key, y_key, z_key)

    # Create marker configuration once
    marker_config = {
        "color": display.get("color", "rgb(255, 255, 255)"),
        "size": display.get("size", 6),
        "opacity": display.get("opacity", 1),
        "symbol": display.get("symbol", "circle"),
        "line": {
            "color": display.get("line_color", "#000000"),
            "width": display.get("line_width", 2),
        },
    }

    # Construct the figure data directly
    fig_data = {
        "type": "scatter3d",
        "x": [x_val],
        "y": [y_val],
        "z": [z_val],
        "hovertemplate": REF_HOVER,
        "mode": "markers",
        "name": name,
        "marker": marker_config,
    }

    return fig_data


def get_ref_box3d_data(
    data_frame: pd.DataFrame,
    x_key: str,
    y_key: str,
    z_key: Optional[str] = None,
    name: Optional[str] = "Origin",
    display: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Draw the reference as a box scaled to the thing it stands for.

    A dot marks a position; a box also carries extent, which is what makes a
    host vehicle legible against its own returns -- you can see which
    detections fall on the body and which are past it.

    The box is axis-aligned. Its dimensions are given per plot axis rather than
    as length/width/height because the 3D view's axes are user-assigned
    columns, so the manifest cannot know which one runs along the vehicle.

    Args:
        data_frame: DataFrame containing the source data.
        x_key: Column name for x-axis coordinates.
        y_key: Column name for y-axis coordinates.
        z_key: Optional column name for z-axis coordinates.
        name: Optional label for the reference in the plot.
        display: Manifest styling, normalized by
            :func:`dataio.manifest.normalize_reference_display`.

    Returns:
        The mesh trace, followed by the wireframe trace when edges are on.
        Empty when there is no frame to place the box against.
    """
    if data_frame.empty:
        return []

    display = display or {}
    x_val, y_val, z_val = _ref_point(data_frame, x_key, y_key, z_key)

    dimensions = display.get("dimensions", [1.9, 4.7, 1.5])
    offset = display.get("offset", [0.0, 0.0, 0.0])
    center = (x_val + offset[0], y_val + offset[1], z_val + offset[2])
    half = [size / 2.0 for size in dimensions]

    corners = [
        [center[axis] + signs[axis] * half[axis] for axis in range(3)]
        for signs in _BOX_CORNERS
    ]

    color = display.get("color", "#ffffff")
    traces: List[Dict[str, Any]] = [
        {
            "type": "mesh3d",
            "x": [corner[0] for corner in corners],
            "y": [corner[1] for corner in corners],
            "z": [corner[2] for corner in corners],
            "i": [face[0] for face in _BOX_FACES],
            "j": [face[1] for face in _BOX_FACES],
            "k": [face[2] for face in _BOX_FACES],
            "color": color,
            "opacity": display.get("opacity", 0.35),
            "flatshading": True,
            "hoverinfo": "skip",
            "name": name,
            "showlegend": True,
            "legendgroup": "reference",
        }
    ]

    if display.get("edges", True):
        # One trace for all 12 edges: a None between segments lifts the pen, so
        # the wireframe costs one trace instead of twelve.
        path: List[Optional[List[float]]] = []
        for start, end in _BOX_EDGES:
            path.extend([corners[start], corners[end], None])

        traces.append(
            {
                "type": "scatter3d",
                "x": [None if point is None else point[0] for point in path],
                "y": [None if point is None else point[1] for point in path],
                "z": [None if point is None else point[2] for point in path],
                "mode": "lines",
                "line": {
                    "color": display.get("edge_color", color),
                    "width": display.get("edge_width", 2),
                },
                "hovertemplate": REF_HOVER,
                "name": name,
                # The outline is part of the box, not a second thing to toggle.
                "showlegend": False,
                "legendgroup": "reference",
            }
        )

    return traces


def get_reference_traces(
    data_frame: pd.DataFrame,
    x_key: str,
    y_key: str,
    z_key: Optional[str] = None,
    name: Optional[str] = "Origin",
    display: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Build the reference overlay in whichever shape the manifest asked for.

    Args:
        data_frame: DataFrame containing the source data.
        x_key: Column name for x-axis coordinates.
        y_key: Column name for y-axis coordinates.
        z_key: Optional column name for z-axis coordinates.
        name: Optional label for the reference in the plot.
        display: Manifest styling, normalized by
            :func:`dataio.manifest.normalize_reference_display`. Absent or
            shapeless, the reference stays the plain marker it has always been.

    Returns:
        List of traces to append to the figure.
    """
    display = display or {}

    if display.get("shape") == "box":
        return get_ref_box3d_data(data_frame, x_key, y_key, z_key, name, display)

    return [get_ref_scatter3d_data(data_frame, x_key, y_key, z_key, name, display)]


def get_cloud_scatter3d_data(
    points: Optional[np.ndarray],
    display: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Build the point-cloud backdrop trace.

    The cloud is display-only: it carries no filter state and has no runtime
    controls, so styling is fixed by the manifest rather than wired to any UI
    input. Hover is disabled outright -- the backdrop is context, not something
    to interrogate, and skipping hover text keeps 60k points off the wire.

    Args:
        points: (N, 3+) array of already-decimated xyz points in the reference
            frame. Extra columns beyond xyz are ignored.
        display: Fixed styling with ``color``, ``size``, ``opacity``, ``name``.

    Returns:
        Scatter3d trace dictionary, or None when there is nothing to draw.
    """
    if points is None or len(points) == 0:
        return None

    display = display or {}
    points = np.asarray(points)

    # Column slices of a 2D array are strided views, which orjson refuses to
    # serialize ("numpy array is not C contiguous"). Copy each axis into its own
    # contiguous buffer -- still far cheaper than materializing Python lists.
    x_vals = np.ascontiguousarray(points[:, 0])
    y_vals = np.ascontiguousarray(points[:, 1])
    z_vals = np.ascontiguousarray(points[:, 2])

    return {
        "type": "scatter3d",
        "x": x_vals,
        "y": y_vals,
        "z": z_vals,
        "mode": "markers",
        "name": display.get("name", "Point Cloud"),
        "showlegend": True,
        "hoverinfo": "skip",
        "marker": {
            "color": display.get("color", "#8d99ae"),
            "size": display.get("size", 1.2),
            "opacity": display.get("opacity", 0.35),
        },
    }


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
            "ids": df.index.to_numpy(),
            "x": df[x_key].to_numpy(),
            "y": df[y_key].to_numpy(),
            "z": df[z_key].to_numpy(),
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
                    "cmin": kwargs.get(
                        "c_range", [np.nanmin(color), np.nanmax(color)]
                    )[0],
                    "cmax": kwargs.get(
                        "c_range", [np.nanmin(color), np.nanmax(color)]
                    )[1],
                }
            )

        scatter["marker"] = marker
        return scatter

    result = {"scatter_data": [], "hover_strings": []}

    if plot_config["c_type"] == "numerical":
        hover_text = process_hover(data_frame)
        color_values = data_frame[c_key].to_numpy()
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
