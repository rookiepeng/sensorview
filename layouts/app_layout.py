"""SensorView Layout Module

The application shell.

Everything is sized against the viewport rather than flowing down the page: the
top bar and transport are fixed height, the rail, inspector, and dock have
sizes the user controls -- each has a splitter on its inner edge, dragged
clientside -- and the 3D canvas takes whatever is left. Nothing
scrolls except panel interiors, so no view is ever more than a click from
visible -- which is the point, since all of them describe the same instant.

Region ownership:
    top bar      -- identity, which log is open, global actions
    left rail    -- display options and per-column filters
    canvas       -- the 3D point cloud
    inspector    -- camera and threshold for the current frame
    transport    -- frame scrubbing and playback
    bottom dock  -- the six statistical views, one tab each

Usage:
    from layouts.app_layout import get_app_layout

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

import uuid

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc

import plotly.io as pio

from layouts.modal_layout import get_modal_layout, get_error_modal
from layouts.topbar_layout import get_topbar_layout
from layouts.filter_panel_layout import get_filter_rail_layout
from layouts.canvas_layout import get_canvas_layout, get_transport_layout
from layouts.inspector_layout import get_inspector_layout
from layouts.analysis_dock_layout import get_analysis_dock_layout


def _stores():
    """
    Build the client-side state the views coordinate through.

    Returns:
        list: Stores, timers, and the download sink.
    """
    return [
        dcc.Store(id="selected-data-left"),
        dcc.Store(id="selected-data-right"),
        dcc.Store(id="session-id", data=str(uuid.uuid4())),
        dcc.Store(id="filter-trigger", data=0),
        dcc.Store(id="left-regenerate-trigger", data=0),
        dcc.Store(id="right-regenerate-trigger", data=0),
        dcc.Store(id="left-hide-trigger", data=0),
        dcc.Store(id="right-hide-trigger", data=0),
        dcc.Store(id="file-loaded-trigger", data=0),
        dcc.Store(id="background-trigger", data=0),
        dcc.Store(id="dummy-background"),
        dcc.Store(id="visible-table-change-trigger", data=0),
        dcc.Store(id="local-case-selection", storage_type="local"),
        dcc.Store(id="local-file-selection", storage_type="local"),
        dcc.Store(id="current-file"),
        dcc.Store(id="key-dict"),
        dcc.Store(id="relayout-data", data=None),
        dcc.Store(id="dark-template", data=pio.templates["plotly_dark"]),  # type: ignore
        dcc.Store(id="light-template", data=pio.templates["plotly"]),  # type: ignore
        dcc.Store(id="trigger-remote-figure", data=0),
        dcc.Interval(
            id="interval-buffer",
            interval=1000,  # in milliseconds
            disabled=False,
            n_intervals=0,
        ),
        dcc.Store(id="local-buffer-index", data=-1),
        dcc.Store(id="worker-status"),
        dcc.Download(id="download"),
    ]


def _loading_overlay(component_id, label, class_name="sv-loading-overlay"):
    """
    Build a full-screen overlay that blocks the whole app while work runs.

    Its geometry lives in the stylesheet; callbacks only ever set ``display``.
    Because it covers the viewport it also swallows every click, which is the
    point: none of the controls underneath can be moved while the job they
    would re-trigger is still running.

    Args:
        component_id (str): Component id, which is what callbacks toggle.
        label (str): Text shown under the spinner.
        class_name (str): Overlay classes, which decide how it fades in.

    Returns:
        html.Div: The overlay.
    """
    return html.Div(
        [
            dbc.Spinner(
                color="primary", spinner_style={"width": "3rem", "height": "3rem"}
            ),
            html.Span(label, className="sv-loading-label"),
        ],
        id=component_id,
        className=class_name,
        style={"display": "none"},
    )


def get_app_layout():
    """
    Build the application shell.

    Returns:
        html.Div: The root layout.
    """
    return html.Div(
        [
            *_stores(),
            get_modal_layout(),
            get_error_modal(),
            _loading_overlay("loading-view", "Loading dataset"),
            # Raised for as long as a filter or axis change is being applied.
            # It is deferred rather than instant (see the stylesheet): most
            # changes return before it would be painted, and a full-screen
            # flash on every slider nudge is worse than no overlay at all --
            # but the click blocking is in force from the first frame either
            # way, which is what stops a second change being queued behind the
            # one still running.
            _loading_overlay(
                "update-loading-view",
                "Applying changes",
                class_name="sv-loading-overlay sv-loading-deferred",
            ),
            get_topbar_layout(),
            html.Div(
                [
                    html.Div(
                        [
                            get_filter_rail_layout(),
                            html.Div(
                                id="rail-splitter",
                                className="sv-splitter sv-splitter-col",
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            get_canvas_layout(),
                                            # Hidden with the inspector until a
                                            # log arrives that has something to
                                            # show in it (camera_view.py).
                                            html.Div(
                                                id="inspector-splitter",
                                                className="sv-splitter sv-splitter-col",
                                                style={"display": "none"},
                                            ),
                                            get_inspector_layout(),
                                        ],
                                        className="sv-stage",
                                    ),
                                    get_transport_layout(),
                                ],
                                className="sv-center",
                            ),
                        ],
                        className="sv-upper",
                    ),
                    get_analysis_dock_layout(),
                ],
                className="sv-workspace",
            ),
        ],
        className="sv-shell dbc",
    )
