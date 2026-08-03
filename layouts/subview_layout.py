"""Subview Panel Layout Module

A floating panel that keeps the camera and the threshold plot on screen while
the 3D point cloud is being explored. All three are views of the same instant,
so stacking them down the page meant scrolling away from the thing you were
looking at.

The panel is draggable by its header, minimizable to just that header, and
resizable. Drag and minimize are handled clientside (see
``assets/subview.js``) so neither costs a server round trip.

Usage:
    from layouts.subview_layout import get_subview_layout

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc


def _panel_header():
    """
    Build the drag handle and window controls.

    Returns:
        html.Div: The panel header.
    """
    return html.Div(
        [
            html.Span(
                [
                    html.I(className="bi bi-grip-vertical me-2"),
                    html.Span("Camera & Threshold", id="subview-title"),
                ],
                className="subview-header-title",
            ),
            html.Div(
                [
                    dbc.Button(
                        html.I(className="bi bi-dash-lg"),
                        id="subview-minimize",
                        color="transparent",
                        size="sm",
                        n_clicks=0,
                        className="subview-btn",
                    ),
                    dbc.Tooltip(
                        "Minimize / restore",
                        target="subview-minimize",
                        placement="left",
                    ),
                ],
                className="subview-header-actions",
            ),
        ],
        id="subview-header",
        className="subview-header",
    )


def _camera_section():
    """
    Build the camera portion of the panel.

    Returns:
        html.Div: Camera controls and the video element.
    """
    return html.Div(
        [
            dcc.Store(id="camera-config"),
            dcc.Store(id="camera-seek-ack"),
            html.Div(
                dbc.InputGroup(
                    [
                        dbc.InputGroupText("Stream"),
                        dbc.Select(id="camera-stream-picker"),
                    ],
                    size="sm",
                ),
                id="camera-stream-picker-col",
                className="mb-2",
            ),
            html.Video(
                id="camera-video",
                # Playback is driven entirely by the frame slider, so the
                # element never plays on its own: no controls, no autoplay,
                # muted so browsers never block the load.
                controls=False,
                autoPlay=False,
                muted=True,
                preload="auto",
                className="subview-video",
            ),
        ],
        id="subview-camera-section",
    )


def _threshold_section():
    """
    Build the threshold portion of the panel.

    Returns:
        html.Div: Plot selector and the 1D threshold figure.
    """
    return html.Div(
        [
            html.Div(
                dbc.InputGroup(
                    [
                        dbc.InputGroupText("Plot"),
                        dbc.Select(id="threshold-plot-picker"),
                    ],
                    size="sm",
                ),
                id="threshold-plot-picker-col",
                className="mb-2 mt-2",
            ),
            dcc.Graph(
                id="threshold-plot",
                config={"displaylogo": False, "displayModeBar": False},
                figure={
                    "data": [{"type": "scatter", "x": [], "y": []}],
                    "layout": {"uirevision": "no_change"},
                },
                className="subview-graph",
            ),
        ],
        id="subview-threshold-section",
    )


def get_subview_layout():
    """
    Create the floating camera + threshold panel.

    The panel hides itself when the loaded log has neither a camera nor a
    threshold sidecar, and each section hides independently when only one of
    the two is present.

    Args:
        None

    Returns:
        html.Div: The floating subview panel.
    """
    return html.Div(
        [
            # Remembers position and minimized state across figure updates.
            dcc.Store(id="subview-state", data={"minimized": False}),
            _panel_header(),
            html.Div(
                [_camera_section(), _threshold_section()],
                id="subview-body",
                className="subview-body",
            ),
        ],
        id="subview-panel",
        className="subview-panel",
        style={"display": "none"},
    )
