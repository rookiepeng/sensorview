"""3D Canvas Layout Module

The primary stage: the 3D point cloud plus the transport bar that scrubs it.

The canvas is the only region that grows -- every other panel has a fixed or
user-set size, so whatever they give up the point cloud takes. View settings
float over the plot rather than docking above it: they are touched a handful of
times a session and would otherwise cost their height on every frame.

Usage:
    from layouts.canvas_layout import get_canvas_layout

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc

import plotly.io as pio

from layouts.layout_constants import colorscales


def _select(component_id, label, tooltip, class_name="", **kwargs):
    """
    Build a compact labelled select with its tooltip.

    Args:
        component_id (str): Component id, also the tooltip target.
        label (str): Prefix shown in the input group.
        tooltip (str): Explanatory text.
        class_name (str): Extra classes for the wrapper, e.g. ``sv-field-wide``
            to span a mapping grid.
        **kwargs: Extra props forwarded to ``dbc.Select``.

    Returns:
        html.Div: The input group and its tooltip.
    """
    return html.Div(
        [
            dbc.InputGroup(
                [dbc.InputGroupText(label), dbc.Select(id=component_id, **kwargs)],
                size="sm",
            ),
            dbc.Tooltip(tooltip, target=component_id, placement="bottom"),
        ],
        className=f"sv-grow {class_name}".strip(),
    )


def _canvas_tools():
    """
    Build the floating control cluster over the plot.

    Returns:
        html.Div: Color axis, colormap, and the axis-configuration trigger.
    """
    return html.Div(
        [
            _select("c-picker-3d", "Color", "Column mapped to marker color"),
            _select(
                "colormap-3d",
                "Map",
                "Colormap applied to the color axis",
                options=[{"value": x, "label": x} for x in colorscales],
                value="Portland",
            ),
            dbc.Button(
                html.I(className="bi bi-sliders"),
                id="3d-config-more-button",
                color="transparent",
                n_clicks=0,
                className="sv-icon-btn",
            ),
            dbc.Tooltip(
                "Axis mapping and reference columns",
                target="3d-config-more-button",
                placement="bottom",
            ),
        ],
        className="sv-canvas-tools",
    )


def _axis_config_panel():
    """
    Build the axis mapping panel that drops out of the tool cluster.

    Three sections, each a grid of the same three columns so a field lines up
    with the one above it: which column drives the slider, which drive the
    axes, and -- for a log with a pose sidecar -- which of that file's columns
    carry the reference.

    The reference section is the sidecar's editor and nothing else's, so a log
    without one hides it rather than showing seven selects with nothing to
    offer.

    Returns:
        dbc.Collapse: The frame, axis, and reference selectors.
    """
    axes = [
        ("x-picker-3d", "x", "Column plotted on the x axis"),
        ("y-picker-3d", "y", "Column plotted on the y axis"),
        ("z-picker-3d", "z", "Column plotted on the z axis"),
    ]
    # Position and orientation, in the order the pose is read. Both come from
    # the sidecar: a table column carries a position and nothing else.
    reference = [
        ("x-ref-picker-3d", "x", "Sidecar column for the reference x position"),
        ("y-ref-picker-3d", "y", "Sidecar column for the reference y position"),
        ("z-ref-picker-3d", "z", "Sidecar column for the reference z position"),
        ("yaw-ref-picker-3d", "yaw", "Sidecar column for yaw, in radians"),
        ("pitch-ref-picker-3d", "pitch", "Sidecar column for pitch, in radians"),
        ("roll-ref-picker-3d", "roll", "Sidecar column for roll, in radians"),
    ]

    return dbc.Collapse(
        html.Div(
            [
                html.Span("Frame index", className="sv-section-label"),
                html.Div(
                    [
                        _select(
                            "slider-picker-3d",
                            "slider",
                            "Integer column used as the temporal axis for the "
                            "frame slider",
                            class_name="sv-field-wide",
                        )
                    ],
                    className="sv-field-grid",
                ),
                html.Div(className="sv-divider"),
                html.Span("Axes", className="sv-section-label"),
                html.Div(
                    [_select(cid, label, tip) for cid, label, tip in axes],
                    className="sv-field-grid",
                ),
                html.Div(
                    [
                        html.Div(className="sv-divider"),
                        html.Span("Reference", className="sv-section-label"),
                        html.Span("", id="ref-source-note", className="sv-source-note"),
                        html.Div(
                            [
                                # The frame key spans the row: it is what pairs
                                # a sidecar row with a table frame, so every
                                # column under it is read through this one.
                                _select(
                                    "frame-ref-picker-3d",
                                    "frame",
                                    "Sidecar column holding the frame id, paired "
                                    "with the table's own frame column",
                                    class_name="sv-field-wide",
                                ),
                                *[
                                    _select(cid, label, tip)
                                    for cid, label, tip in reference
                                ],
                            ],
                            className="sv-field-grid",
                        ),
                    ],
                    id="ref-controls",
                    style={"display": "none"},
                ),
            ],
            className="sv-canvas-popover-inner",
        ),
        id="3d-config-collapse",
        is_open=False,
        className="sv-canvas-popover",
    )


def get_transport_layout():
    """
    Build the playback transport.

    Buffer progress rides as two hairlines on the bar's top edge: visible when
    looked for, invisible otherwise, and costing no extra height either way.

    Returns:
        html.Div: Buffer bars, transport buttons, frame slider, frame readout.
    """
    return html.Div(
        [
            html.Div(
                [
                    dbc.Progress(id="buffer", value=0, color="warning"),
                    dbc.Progress(id="buffer-local", value=0, color="info"),
                ],
                className="sv-buffer-stack",
            ),
            dbc.Tooltip(
                "Server-side buffering progress",
                id="buffer-tooltip",
                target="buffer",
                placement="top",
            ),
            dbc.Tooltip(
                "Browser-side buffering progress",
                target="buffer-local",
                placement="top",
            ),
            dcc.Interval(
                id="interval-component",
                interval=200,  # in milliseconds
                disabled=True,
                n_intervals=0,
            ),
            dbc.ButtonGroup(
                [
                    dbc.Button(
                        html.I(className="bi bi-skip-backward-fill"),
                        id="previous-button",
                        color="secondary",
                        n_clicks=0,
                    ),
                    dbc.Button(
                        html.I(className="bi bi-play-fill"),
                        id="play-stop-button",
                        color="primary",
                        n_clicks=0,
                    ),
                    dbc.Button(
                        html.I(className="bi bi-skip-forward-fill"),
                        id="next-button",
                        color="secondary",
                        n_clicks=0,
                    ),
                ],
                className="sv-transport-buttons",
            ),
            dbc.Tooltip("Previous frame", target="previous-button", placement="top"),
            dbc.Tooltip("Play / pause", target="play-stop-button", placement="top"),
            dbc.Tooltip("Next frame", target="next-button", placement="top"),
            html.Div(
                dcc.Slider(
                    id="slider-frame",
                    step=1,
                    value=0,
                    updatemode="drag",
                    marks=None,
                    tooltip={"always_visible": False, "placement": "top"},
                ),
                className="sv-transport-slider",
            ),
            html.Div(
                [
                    html.B("0", id="frame-current"),
                    html.Span(" / 0", id="frame-total"),
                ],
                id="frame-readout",
                className="sv-frame-readout",
            ),
        ],
        className="sv-transport",
    )


def get_canvas_layout():
    """
    Build the 3D plot stage.

    Returns:
        html.Div: The canvas, with its floating controls layered over the plot.
    """
    return html.Div(
        [
            _canvas_tools(),
            _axis_config_panel(),
            dcc.Graph(
                id="scatter3d",
                responsive=True,
                config={
                    "displaylogo": False,
                    "modeBarButtonsToRemove": [
                        "resetCameraDefault3d",
                        "resetCameraLastSave3d",
                    ],
                },
                figure={
                    "data": [
                        {
                            "mode": "markers",
                            "type": "scatter3d",
                            "x": [],
                            "y": [],
                            "z": [],
                        }
                    ],
                    "layout": {
                        "template": pio.templates["plotly"],
                        "uirevision": "no_change",
                    },
                },
                style={"height": "100%", "width": "100%"},
            ),
        ],
        className="sv-canvas",
    )
