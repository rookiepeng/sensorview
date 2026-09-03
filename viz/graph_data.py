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

from dataio.calibration import rotation_matrix

REF_HOVER = "Lateral: %{x:.2f} m<br>Longitudinal: %{y:.2f} m<br>"

# Where a reference goes when the dataset declares one but has no pose to place
# it by. Drawing it there says the `reference` block was read and the poses were
# not, which is a far easier thing to diagnose than an overlay that never
# appears. Whether an unplaced reference is drawn at all is the caller's call --
# see :func:`utils.prepare_figure_kwargs`, which is where the sources are known.
DEFAULT_REFERENCE_ORIGIN = (0.0, 0.0, 0.0)


def _pose_point(pose: Dict[str, float]) -> Tuple[float, float, float]:
    """
    Read the position out of a reference pose.

    Args:
        pose: Pose dict from the reference sidecar.

    Returns:
        ``(x, y, z)`` in meters; a field the sidecar does not carry reads 0.
    """
    return (
        float(pose.get("x", 0.0)),
        float(pose.get("y", 0.0)),
        float(pose.get("z", 0.0)),
    )


def _place_vertices(
    vertices: List[List[float]],
    origin: Tuple[float, float, float],
    rotation: Optional[np.ndarray],
) -> List[List[float]]:
    """
    Put a mesh's vertices where the reference is.

    Args:
        vertices: Mesh vertices in the reference's own frame, in meters.
        origin: Reference position in plot coordinates.
        rotation: Pose rotation, or None for an unrotated placement.

    Returns:
        Vertices in plot coordinates.
    """
    if rotation is None:
        return [
            [vertex[axis] + origin[axis] for axis in range(3)] for vertex in vertices
        ]

    return (np.asarray(vertices) @ rotation.T + np.asarray(origin)).tolist()


def _edge_trace(
    vertices: List[List[float]],
    edges: List[List[int]],
    color: str,
    width: float,
    name: Optional[str],
) -> Dict[str, Any]:
    """
    Draw a mesh's edges as one polyline trace.

    Args:
        vertices: Placed mesh vertices.
        edges: Vertex-index pairs to draw.
        color: Line color.
        width: Line width.
        name: Label the trace shares with the rest of the reference.

    Returns:
        Scatter3d line trace, with a None between segments to lift the pen --
        so the whole wireframe costs one trace instead of one per edge.
    """
    path: List[Optional[List[float]]] = []
    for start, end in edges:
        path.extend([vertices[start], vertices[end], None])

    return {
        "type": "scatter3d",
        "x": [None if point is None else point[0] for point in path],
        "y": [None if point is None else point[1] for point in path],
        "z": [None if point is None else point[2] for point in path],
        "mode": "lines",
        "line": {"color": color, "width": width},
        "hovertemplate": REF_HOVER,
        "name": name,
        # The outline is part of the mesh, not a second thing to toggle.
        "showlegend": False,
        "legendgroup": "reference",
    }


def _pose_rotation(pose: Optional[Dict[str, float]]) -> Optional[np.ndarray]:
    """
    Build the rotation matrix for a reference pose.

    Args:
        pose: Pose dict from the reference sidecar, or None.

    Returns:
        3x3 rotation matrix, or None when the pose is absent or level -- an
        unrotated mesh is placed by translation alone, which is both cheaper and
        exactly what the table-column path has always produced.
    """
    if pose is None:
        return None

    yaw = float(pose.get("yaw", 0.0) or 0.0)
    pitch = float(pose.get("pitch", 0.0) or 0.0)
    roll = float(pose.get("roll", 0.0) or 0.0)
    if yaw == 0.0 and pitch == 0.0 and roll == 0.0:
        return None

    return rotation_matrix(roll, pitch, yaw)


def get_ref_scatter3d_data(
    origin: Tuple[float, float, float],
    name: Optional[str] = "Origin",
    display: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate reference data for a 3D scatter plot.

    Args:
        origin: Reference position in plot coordinates -- the pose's, or
            :data:`DEFAULT_REFERENCE_ORIGIN` when there is no pose to place it.
        name: Optional label for the reference point in the plot.
        display: Optional manifest styling (``color``, ``size``, ``opacity``,
            ``symbol``, ``line_color``, ``line_width``).

    Returns:
        Dictionary containing plot data with coordinates, styling, and hover information.
    """
    display = display or {}
    x_val, y_val, z_val = origin

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


def get_ref_mesh3d_data(
    origin: Tuple[float, float, float],
    name: Optional[str] = "Origin",
    display: Optional[Dict[str, Any]] = None,
    pose: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """
    Draw the reference as the mesh the dataset declared for it.

    A dot marks a position; a body also carries extent, which is what makes a
    host vehicle legible against its own returns -- you can see which detections
    fall on it and which are past it.

    The geometry comes from the manifest whole: ``vertices`` in meters relative
    to the reference point, ``faces`` as vertex-index triangles. Nothing is
    generated here, so the shape is free to be a plain box or a silhouette whose
    nose is obvious from any angle -- which end is the front is answered by the
    mesh rather than by a setting, and there is no way for a generated shape to
    disagree with what the dataset meant.

    The vertices sit in the reference's own frame. Without a pose they are
    placed as authored, around whatever origin the caller passes. A ``pose``
    from the reference sidecar also carries orientation, and then the whole
    mesh turns with it.

    Args:
        origin: Reference position in plot coordinates -- the pose's, or
            :data:`DEFAULT_REFERENCE_ORIGIN` when there is no pose to place it.
        name: Optional label for the reference in the plot.
        display: Manifest styling and geometry, normalized by
            :func:`dataio.manifest.normalize_reference_display`.
        pose: Pose from the reference sidecar, carrying position in meters and
            yaw/pitch/roll in radians. Read here for its orientation only; the
            position it carries has already gone into ``origin``.

    Returns:
        The mesh trace, followed by the wireframe trace when the manifest asks
        for edges. Empty when there is no geometry to place.
    """
    display = display or {}
    faces = display.get("faces") or []
    if not faces:
        return []

    vertices = _place_vertices(
        display.get("vertices") or [], origin, _pose_rotation(pose)
    )

    color = display.get("color", "#ffffff")
    traces: List[Dict[str, Any]] = [
        {
            "type": "mesh3d",
            "x": [vertex[0] for vertex in vertices],
            "y": [vertex[1] for vertex in vertices],
            "z": [vertex[2] for vertex in vertices],
            "i": [face[0] for face in faces],
            "j": [face[1] for face in faces],
            "k": [face[2] for face in faces],
            "color": color,
            "opacity": display.get("opacity", 0.35),
            "flatshading": True,
            "hoverinfo": "skip",
            "name": name,
            "showlegend": True,
            "legendgroup": "reference",
        }
    ]

    edges = display.get("edges") or []
    if edges:
        traces.append(
            _edge_trace(
                vertices,
                edges,
                display.get("edge_color") or color,
                display.get("edge_width", 2),
                name,
            )
        )

    return traces


def get_reference_traces(
    name: Optional[str] = "Origin",
    display: Optional[Dict[str, Any]] = None,
    pose: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """
    Build the reference overlay in whichever shape the manifest asked for.

    Draws the reference wherever the pose puts it, or -- with no pose --  at
    :data:`DEFAULT_REFERENCE_ORIGIN`. It does not decide *whether* a reference
    belongs on this figure: a caller that hands over no pose is saying it wants
    the reference drawn unplaced, and one that wants none does not call at all.
    That decision needs to know which logs have sidecars and whether they pair
    with the table, which is :func:`utils.prepare_figure_kwargs`'s job.

    Args:
        name: Optional label for the reference in the plot.
        display: Manifest styling, normalized by
            :func:`dataio.manifest.normalize_reference_display`. Absent or
            shapeless, the reference stays the plain marker it has always been.
        pose: Pose read from the log's reference sidecar, carrying position in
            meters and yaw/pitch/roll in radians.

    Returns:
        List of traces to append to the figure.
    """
    display = display or {}
    origin = _pose_point(pose) if pose is not None else DEFAULT_REFERENCE_ORIGIN

    if display.get("shape") == "mesh":
        return get_ref_mesh3d_data(origin, name, display, pose)

    return [get_ref_scatter3d_data(origin, name, display)]


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
                    "cmin": kwargs.get("c_range", [np.nanmin(color), np.nanmax(color)])[
                        0
                    ],
                    "cmax": kwargs.get("c_range", [np.nanmin(color), np.nanmax(color)])[
                        1
                    ],
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
