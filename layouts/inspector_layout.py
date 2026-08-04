"""Inspector Layout Module

The right dock: the camera stream and the threshold plot for the current frame.

All three views -- point cloud, camera, threshold -- show the same instant, so
they have to be on screen together. This used to be a floating window that
covered the thing it was meant to accompany; docking it means the canvas gives
up width it can spare instead of being occluded, and the dock still collapses
to a strip when the extra views are not wanted.

The panel hides itself entirely when the loaded log has neither sidecar, and
each section hides independently (see ``view_callbacks/camera_view.py`` and
``view_callbacks/threshold_view.py``), so the canvas reclaims the full width.

Usage:
    from layouts.inspector_layout import get_inspector_layout

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc


def _camera_section():
    """
    Build the camera portion of the dock.

    Returns:
        html.Div: Stream selector and the video element, behind a header with
        its own minimize toggle so it can give up space to the curve section.
    """
    return html.Div(
        [
            dcc.Store(id="camera-config"),
            dcc.Store(id="camera-seek-ack"),
            html.Div(
                [
                    html.Span(
                        [html.I(className="bi bi-camera-video me-2"), "Image"],
                        className="sv-section-label",
                    ),
                    dbc.Button(
                        html.I(className="bi bi-dash-lg"),
                        id="camera-section-toggle",
                        color="transparent",
                        n_clicks=0,
                        className="sv-icon-btn sv-icon-btn-sm",
                    ),
                ],
                className="sv-subsection-head",
            ),
            dbc.Tooltip(
                "Minimize / restore the image",
                target="camera-section-toggle",
                placement="left",
            ),
            html.Div(
                [
                    html.Div(
                        html.Div(
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("Stream"),
                                    dbc.Select(id="camera-stream-picker"),
                                ],
                                size="sm",
                            ),
                            id="camera-stream-picker-col",
                        ),
                        className="sv-subsection-controls",
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
                        className="sv-video",
                    ),
                ],
                className="sv-subsection-body",
            ),
        ],
        id="subview-camera-section",
        className="sv-subsection",
    )


def _threshold_section():
    """
    Build the threshold portion of the dock.

    Returns:
        html.Div: Source and plot selectors, and the 1D threshold figure,
        behind a header with its own minimize toggle. This section grows to
        fill whatever height the image section does not need, so the plot
        gets more room when the image is minimized.
    """
    return html.Div(
        [
            html.Div(
                [
                    html.Span(
                        [html.I(className="bi bi-graph-up me-2"), "Curve"],
                        className="sv-section-label",
                    ),
                    dbc.Button(
                        html.I(className="bi bi-dash-lg"),
                        id="threshold-section-toggle",
                        color="transparent",
                        n_clicks=0,
                        className="sv-icon-btn sv-icon-btn-sm",
                    ),
                ],
                className="sv-subsection-head",
            ),
            dbc.Tooltip(
                "Minimize / restore the curve",
                target="threshold-section-toggle",
                placement="left",
            ),
            html.Div(
                [
                    # Both selectors share one row, and each still hides on its
                    # own when there is only one thing to pick.
                    html.Div(
                        [
                            # A log may carry one sidecar per sensor. Their
                            # range bins differ, so they are picked between
                            # rather than drawn together.
                            html.Div(
                                dbc.InputGroup(
                                    [
                                        dbc.InputGroupText("Sensor"),
                                        dbc.Select(id="threshold-source-picker"),
                                    ],
                                    size="sm",
                                ),
                                id="threshold-source-picker-col",
                            ),
                            html.Div(
                                dbc.InputGroup(
                                    [
                                        dbc.InputGroupText("Plot"),
                                        dbc.Select(id="threshold-plot-picker"),
                                    ],
                                    size="sm",
                                ),
                                id="threshold-plot-picker-col",
                            ),
                        ],
                        className="sv-subsection-controls",
                    ),
                    # A responsive Graph sets its own height:100% inline, so the
                    # size has to be pinned on the wrapper.
                    html.Div(
                        dcc.Graph(
                            id="threshold-plot",
                            responsive=True,
                            config={"displaylogo": False, "displayModeBar": False},
                            figure={
                                "data": [{"type": "scatter", "x": [], "y": []}],
                                "layout": {"uirevision": "no_change"},
                            },
                        ),
                        className="sv-threshold-graph",
                    ),
                ],
                className="sv-subsection-body",
            ),
        ],
        id="subview-threshold-section",
        className="sv-subsection sv-subsection--grow",
    )



def get_inspector_layout():
    """
    Build the collapsible right inspector dock.

    Returns:
        html.Aside: The dock. Its id is unchanged from the floating panel it
        replaces, so the callbacks that show and hide it still apply.
    """
    return html.Aside(
        [
            html.Div(
                [
                    html.Span(
                        [html.I(className="bi bi-eye"), "Inspector"],
                        className="sv-panel-title",
                    ),
                    dbc.Button(
                        html.I(className="bi bi-layout-sidebar-inset-reverse"),
                        id="inspector-toggle",
                        color="transparent",
                        n_clicks=0,
                        className="sv-icon-btn",
                    ),
                ],
                className="sv-panel-head",
            ),
            dbc.Tooltip(
                "Collapse / expand the inspector",
                target="inspector-toggle",
                placement="left",
            ),
            html.Div(
                [_camera_section(), _threshold_section()],
                className="sv-inspector-body",
            ),
        ],
        id="subview-panel",
        className="sv-inspector",
        style={"display": "none"},
    )
