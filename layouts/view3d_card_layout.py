"""3D View Card Layout Module

Layout for 3D scatter plot visualization card with enable switch, axis selectors
(x, y, z, color), colormap selector, plot area with loading overlay, and export button.

Usage:
    from layouts.view3d_card_layout import get_view3d_card_layout

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc

import plotly.io as pio

from app_config import THEME

from layouts.layout_constants import colorscales


def get_3d_view_config_layout():
    """
    Creates and returns the configuration row layout for 3D visualization controls.

    The layout includes:
        - Dark/light mode toggle switch with sun/moon icons
        - Color axis selector dropdown
        - Colormap selector dropdown with predefined colorscales

    Args:
        None

    Returns:
        List[dbc.Col]: A list of Dash Bootstrap Column components containing dark mode toggle,
        color picker, and colormap selector with tooltips.
    """
    return [
        dbc.Col(
            dbc.InputGroup(
                [
                    dbc.InputGroupText("Color"),
                    dbc.Select(id="c-picker-3d"),
                    dbc.Tooltip(
                        "Select color axis",
                        target="c-picker-3d",
                        placement="top",
                    ),
                ],
                size="sm",
            ),
            width=3,
        ),
        dbc.Col(
            dbc.InputGroup(
                [
                    dbc.InputGroupText("Colormap"),
                    dbc.Select(
                        id="colormap-3d",
                        options=[{"value": x, "label": x} for x in colorscales],
                        value="Portland",
                    ),
                    dbc.Tooltip(
                        "Select colormap",
                        target="colormap-3d",
                        placement="top",
                    ),
                ],
                size="sm",
            ),
            width=3,
        ),
        dbc.Col(
            dbc.InputGroup(
                [
                    dbc.Label(
                        html.I(className="bi bi-brightness-high-fill"),
                        className="me-2 mb-0 d-flex align-items-center",
                    ),
                    dbc.Checklist(
                        options=[
                            {
                                "label": html.I(className="bi bi-moon-stars-fill"),
                                "value": True,
                            }
                        ],
                        value=[True],
                        id="darkmode-switch",
                        switch=True,
                        className="mb-0 d-flex align-items-center mt-1",
                        inline=True,
                    ),
                    dbc.Tooltip(
                        "Toggle between light and dark background",
                        id="darkmode-switch-tooltip",
                        target="darkmode-switch",
                        placement="top",
                    ),
                ],
                className="align-items-center",
            ),
            className="ms-auto",
            width="auto",
        ),
        dbc.Col(
            dbc.Button(
                html.I(className="bi bi-layout-sidebar-reverse"),
                id="toggle-sidebar-button",
                className="mb-0",
                color="transparent",
                n_clicks=0,
                size="sm",
            ),
            width="auto",
            className="d-flex align-items-center",
        ),
        dbc.Tooltip(
            "Toggle filter sidebar",
            target="toggle-sidebar-button",
            placement="top",
        ),
        dbc.Col(
            dbc.Button(
                html.I(className="bi bi-three-dots-vertical"),
                id="3d-config-more-button",
                className="mb-0",
                color="transparent",
                n_clicks=0,
                size="sm",
            ),
            width="auto",
            className="d-flex align-items-center",
        ),
        dbc.Tooltip(
            "More configuration options",
            target="3d-config-more-button",
            placement="top",
        ),
        dbc.Col(
            dbc.Collapse(
                dbc.Card(
                    dbc.CardBody(
                        dbc.Row(
                            [
                                dbc.Col(
                                    dbc.InputGroup(
                                        [
                                            dbc.InputGroupText("slider"),
                                            dbc.Select(id="slider-picker-3d"),
                                            dbc.Tooltip(
                                                "Select temporal column. This data needs to "
                                                "be integer and will be used as the slider value.",
                                                target="slider-picker-3d",
                                                placement="top",
                                            ),
                                        ],
                                        size="sm",
                                    ),
                                    width=3,
                                    className="mb-3",
                                ),
                                dbc.Col(
                                    dbc.InputGroup(
                                        [
                                            dbc.InputGroupText("x"),
                                            dbc.Select(id="x-picker-3d"),
                                            dbc.Tooltip(
                                                "Select data for x axis",
                                                target="x-picker-3d",
                                                placement="top",
                                            ),
                                        ],
                                        size="sm",
                                    ),
                                    width=3,
                                ),
                                dbc.Col(
                                    dbc.InputGroup(
                                        [
                                            dbc.InputGroupText("y"),
                                            dbc.Select(id="y-picker-3d"),
                                            dbc.Tooltip(
                                                "Select data for y axis",
                                                target="y-picker-3d",
                                                placement="top",
                                            ),
                                        ],
                                        size="sm",
                                    ),
                                    width=3,
                                ),
                                dbc.Col(
                                    dbc.InputGroup(
                                        [
                                            dbc.InputGroupText("z"),
                                            dbc.Select(id="z-picker-3d"),
                                            dbc.Tooltip(
                                                "Select data for z axis",
                                                target="z-picker-3d",
                                                placement="top",
                                            ),
                                        ],
                                        size="sm",
                                    ),
                                    width=3,
                                ),
                                dbc.Col(
                                    dbc.InputGroup(
                                        [
                                            dbc.InputGroupText("x ref"),
                                            dbc.Select(id="x-ref-picker-3d"),
                                            dbc.Tooltip(
                                                "Select data for reference in x axis",
                                                target="x-ref-picker-3d",
                                                placement="top",
                                            ),
                                        ],
                                        size="sm",
                                    ),
                                    width={"size": 3, "offset": 3},
                                ),
                                dbc.Col(
                                    dbc.InputGroup(
                                        [
                                            dbc.InputGroupText("y ref"),
                                            dbc.Select(id="y-ref-picker-3d"),
                                            dbc.Tooltip(
                                                "Select data for reference in y axis",
                                                target="y-ref-picker-3d",
                                                placement="top",
                                            ),
                                        ],
                                        size="sm",
                                    ),
                                    width=3,
                                ),
                                dbc.Col(
                                    dbc.InputGroup(
                                        [
                                            dbc.InputGroupText("z ref"),
                                            dbc.Select(id="z-ref-picker-3d"),
                                            dbc.Tooltip(
                                                "Select data for reference in z axis",
                                                target="z-ref-picker-3d",
                                                placement="top",
                                            ),
                                        ],
                                        size="sm",
                                    ),
                                    width=3,
                                ),
                            ]
                        )
                    )
                ),
                id="3d-config-collapse",
                is_open=False,
            ),
            width=12,
        ),
    ]


def get_3d_play_view_layout():
    """
    Creates and returns the main 3D visualization layout with playback controls.

    The layout includes:
        - Configuration controls (dark mode, color, colormap)
        - 3D scatter plot with custom toolbar configuration
        - Server and local buffering progress bars
        - Frame navigation slider
        - Playback control buttons (previous, play, stop, next)
        - Export dropdown with multiple export options
        - Hidden div for additional functionality

    Args:
        None

    Returns:
        dbc.Row: A Dash Bootstrap Row component containing the complete 3D visualization
        interface with interactive controls, progress indicators, and export options.
    """
    return dbc.Row(
        get_3d_view_config_layout()
        + [
            dbc.Col(
                dcc.Graph(
                    id="scatter3d",
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
                    style={"height": "80vh"},
                ),
                className="mt-2",
            ),
            dbc.Col(
                dbc.Progress(
                    id="buffer",
                    value=0,
                    color="warning",
                    style={
                        "height": "2px",
                        "marginTop": 0,
                        "marginBottom": 0,
                        "marginLeft": 25,
                        "marginRight": 25,
                    },
                    className="mb-0",
                ),
                width=12,
            ),
            dbc.Tooltip(
                "Progress of buffering on server",
                id="buffer-tooltip",
                target="buffer",
                placement="top",
            ),
            dbc.Col(
                dbc.Progress(
                    id="buffer-local",
                    value=0,
                    color="info",
                    style={
                        "height": "2px",
                        "marginTop": 0,
                        "marginBottom": 5,
                        "marginLeft": 25,
                        "marginRight": 25,
                    },
                    className="mb-3",
                ),
                width=12,
            ),
            dbc.Col(
                dcc.Slider(
                    id="slider-frame",
                    step=1,
                    value=0,
                    updatemode="drag",
                    marks=None,
                    tooltip={
                        "always_visible": False,
                        "placement": "top",
                    },
                ),
                width=12,
                className="mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dcc.Interval(
                            id="interval-component",
                            interval=2 * 100,  # in milliseconds
                            disabled=True,
                            n_intervals=0,
                        ),
                        width=4,
                    ),
                    dbc.Col(
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
                            className="w-100 mx-auto",
                        ),
                        width=4,
                    ),
                    dbc.Col(
                        dcc.Loading(
                            children=[
                                dbc.DropdownMenu(
                                    [
                                        dbc.DropdownMenuItem(
                                            "Export all frames as an HTML video",
                                            id="export-scatter3d",
                                            n_clicks=0,
                                        ),
                                        dbc.DropdownMenuItem(
                                            "Export current plot (html)",
                                            id="export-scatter3d-html",
                                            n_clicks=0,
                                        ),
                                        dbc.DropdownMenuItem(
                                            "Export current plot (png)",
                                            id="export-scatter3d-png",
                                            n_clicks=0,
                                        ),
                                        dbc.DropdownMenuItem(
                                            "Filtered Data (Current Frame)",
                                            id="export-data-current",
                                            n_clicks=0,
                                        ),
                                        dbc.DropdownMenuItem(
                                            "Filtered Data (All Frames)",
                                            id="export-data-all",
                                            n_clicks=0,
                                        ),
                                    ],
                                    label=html.I(className="bi bi-box-arrow-up"),
                                    id="export-dropdown",
                                    # right=True,
                                    style={"float": "right"},
                                )
                            ],
                            id="export-spinner",
                            display="hide",
                            delay_hide=1000,
                        ),
                        className="ms-auto",
                        width="auto",
                    ),
                    dbc.Tooltip(
                        "Previous frame",
                        target="previous-button",
                        placement="top",
                    ),
                    dbc.Tooltip(
                        "Play / Stop",
                        target="play-stop-button",
                        placement="top",
                    ),
                    dbc.Tooltip(
                        "Next frame",
                        target="next-button",
                        placement="top",
                    ),
                    dbc.Tooltip(
                        "Export",
                        target="export-dropdown",
                        placement="top",
                    ),
                ],
            ),
        ]
    )


def get_filter_sidebar():
    """
    Creates and returns the filter sidebar layout for 3D visualization options.

    The layout includes:
        - Overlay all frames toggle switch
        - Click to change visibility toggle switch
        - Decay slider for temporal effects
        - Filter card with visibility options dropdown
        - Dynamic dropdown and slider containers for filtering

    Args:
        None

    Returns:
        dbc.Row: A Dash Bootstrap Row component containing overlay controls, decay slider,
        and filtering options with tooltips and expandable filter containers.
    """
    return dbc.Row(
        [
            dbc.Checklist(
                options=[
                    {
                        "label": "Overlay all frames",
                        "value": True,
                    }
                ],
                value=[],
                id="overlay-switch",
                switch=True,
                className="mb-2",
            ),
            dbc.Tooltip(
                "Overlay all the frames",
                target="overlay-switch",
                placement="top",
            ),
            dbc.Checklist(
                options=[
                    {
                        "label": "Click to change visibility",
                        "value": True,
                    }
                ],
                value=[],
                id="click-hide-switch",
                switch=True,
                className="mb-2",
            ),
            dbc.Tooltip(
                "When this is enabled, you can click a scatter "
                "on the graph to toggle its hidden/visible state",
                target="click-hide-switch",
                placement="top",
            ),
            dbc.Checklist(
                options=[
                    {
                        "label": "Dot size varies with categories",
                        "value": True,
                    }
                ],
                value=[],
                id="size-vary-switch",
                switch=True,
                className="mb-3",
            ),
            dbc.Tooltip(
                "When this is enabled, the dot size varies with categories",
                target="size-vary-switch",
                placement="top",
            ),
            html.Div(
                [
                    dbc.Label(
                        "Decay",
                        className="mb-1 fw-bold",
                        style={"fontSize": "0.85rem"},
                    ),
                    dcc.Slider(
                        id="decay-slider",
                        min=0,
                        max=10,
                        step=1,
                        value=0,
                        marks=None,
                        tooltip={
                            "always_visible": False,
                            "placement": "top",
                        },
                        className="px-0 py-0",
                    ),
                ],
                className="mb-4 mt-2",
            ),
            dbc.CardHeader("Filter", className="fw-bold mb-2 rounded"),
            dbc.CardBody(
                [
                    html.Div(
                        [
                            dbc.Label(
                                "Visibility Options",
                                className="mb-1 fw-bold",
                                style={"fontSize": "0.85rem"},
                            ),
                            html.Div(
                                dcc.Dropdown(
                                    id="visible-picker",
                                    options=["visible", "hidden"],
                                    value=["visible"],
                                    multi=True,
                                ),
                                className=f"{THEME} mb-0",
                            ),
                        ],
                        className="mb-3",
                        id="visible-picker-container",
                    ),
                    dbc.Tooltip(
                        "By default, all the data is initially labeled as 'visible.' "
                        "You can change the label of the data to 'hidden' using this tool.",
                        target="visible-picker-container",
                        placement="top",
                    ),
                    html.Div(id="dropdown-container", children=[]),
                    html.Div(id="slider-container", children=[]),
                ]
            ),
        ]
    )


def get_view3d_card_layout():
    """
    Creates and returns a Dash Bootstrap Card layout for a 3D scatter plot
    view with interactive controls.

    The layout includes:
        - Dark mode toggle
        - Color and colormap selectors
        - 3D scatter plot graph
        - Buffering progress bars (server and local)
        - Frame slider and playback controls (play, stop, next, previous)
        - Export options for plots and data
        - Overlay and click-to-hide switches
        - Decay slider
        - Visibility filter options

    Args:
        None

    Returns:
        dbc.Card: A Dash Bootstrap Card component containing the
        full 3D scatter plot layout with all controls and tooltips.
    """
    return dbc.Card(
        [
            dbc.CardBody(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                get_3d_play_view_layout(),
                                id="3d-play-view-col",
                                width=9,
                                className="me-3",
                            ),
                            dbc.Col(
                                get_filter_sidebar(),
                                id="filter-sidebar-col",
                                width=True,
                                style={"overflowY": "scroll", "height": "100vh"},
                            ),
                        ]
                    )
                ],
                className="mx-3 my-3 g-0",
            )
        ],
        className="mb-3",
    )
