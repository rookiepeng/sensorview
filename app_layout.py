"""SensorView Layout Module

This module defines the complete UI layout and visual components of the
SensorView application using Dash and Bootstrap components.

Core Components:
---------------
1. Modal Dialogs:
   - Configuration modal
   - File selection interface
   - Settings management

2. Visualization Cards:
   - 3D scatter plot view
   - 2D scatter plot views
   - Histogram, Violin plots
   - Heatmap visualization
   - Parallel categories view

3. Control Elements:
   - Playback controls
   - Data filtering
   - View customization
   - Export options

Layout Structure:
---------------
- Main container
  |- Header section
  |- Configuration modal
  |- 3D view card
  |- 2D view cards
  |- Analysis view cards
  |- Loading overlay
  |- Footer

Dependencies:
------------
- dash & dash-bootstrap-components
- plotly
- app_config settings

Usage:
------
Import the layout generator:
    from app_layout import get_app_layout

Author: Zhengyu Peng
Email: zpeng.me@gmail.com
Website: https://zpeng.me
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

import uuid

import dash
from dash import dcc
from dash import html

import dash_bootstrap_components as dbc

import plotly.io as pio

from app_config import APP_TITLE, APP_VERSION, THEME

from layouts.modal_layout import modal
from layouts.view3d_card_layout import view3d_card

colorscales = [
    "Blackbody",
    "Bluered",
    "Blues",
    "Earth",
    "Electric",
    "Greens",
    "Greys",
    "Hot",
    "Jet",
    "Picnic",
    "Portland",
    "Rainbow",
    "RdBu",
    "Reds",
    "Viridis",
    "YlGnBu",
    "YlOrRd",
]


left2d_card = dbc.Card(
    [
        dbc.CardBody(
            [
                dbc.Row(
                    [
                        dbc.Col(dbc.Label("2D View")),
                        dbc.Col(
                            dbc.Checklist(
                                options=[{"label": "Enable", "value": True}],
                                value=[],
                                id="left-switch",
                                switch=True,
                                style={"float": "right"},
                            )
                        ),
                    ]
                ),
                html.Hr(),
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("x"),
                                    dbc.Select(
                                        id="x-picker-2d-left",
                                        disabled=False,
                                    ),
                                ],
                                size="sm",
                            )
                        ),
                        dbc.Tooltip(
                            "Select x axis",
                            target="x-picker-2d-left",
                            placement="top",
                        ),
                        dbc.Col(
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("y"),
                                    dbc.Select(
                                        id="y-picker-2d-left",
                                        disabled=False,
                                    ),
                                ],
                                size="sm",
                            )
                        ),
                        dbc.Tooltip(
                            "Select y axis",
                            target="y-picker-2d-left",
                            placement="top",
                        ),
                        dbc.Col(
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("c"),
                                    dbc.Select(
                                        id="c-picker-2d-left",
                                        disabled=False,
                                    ),
                                ],
                                size="sm",
                            )
                        ),
                        dbc.Tooltip(
                            "Select color axis",
                            target="c-picker-2d-left",
                            placement="top",
                        ),
                        dbc.Col(
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("cmap"),
                                    dbc.Select(
                                        id="colormap-scatter2d-left",
                                        disabled=False,
                                        options=[
                                            {"value": x, "label": x}
                                            for x in colorscales
                                        ],
                                        value="Portland",
                                    ),
                                ],
                                size="sm",
                            )
                        ),
                        dbc.Tooltip(
                            "Select colormap",
                            target="colormap-scatter2d-left",
                            placement="top",
                        ),
                    ],
                    className="g-1 mb-2",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.RadioItems(
                                options=[
                                    {
                                        "label": "Current frame",
                                        "value": "current",
                                    },
                                    {
                                        "label": "All frames",
                                        "value": "all",
                                    },
                                ],
                                value="current",
                                id="scatter2dl-allframe-switch",
                                inline=True,
                                style={"float": "right"},
                            ),
                        )
                    ]
                ),
                dcc.Loading(
                    id="loading_left",
                    children=[
                        dbc.Collapse(
                            html.Div(
                                [
                                    dcc.Graph(
                                        id="scatter2d-left",
                                        config={"displaylogo": False},
                                        figure={
                                            "data": [
                                                {
                                                    "mode": "markers",
                                                    "type": "scattergl",
                                                    "x": [],
                                                    "y": [],
                                                }
                                            ],
                                            "layout": {"uirevision": "no_change"},
                                        },
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                dbc.Button(
                                                    html.I(
                                                        className="bi bi-eye-slash-fill"
                                                    ),
                                                    id="hide-left",
                                                    color="warning",
                                                    n_clicks=0,
                                                )
                                            ),
                                            dbc.Tooltip(
                                                "Toggle the hidden/visible states of \
                                    the selected dots",
                                                target="hide-left",
                                                placement="top",
                                            ),
                                            dbc.Col(
                                                dbc.Button(
                                                    html.I(
                                                        className="bi bi-camera-fill"
                                                    ),
                                                    id="export-scatter2d-left",
                                                    n_clicks=0,
                                                    style={"float": "right"},
                                                )
                                            ),
                                            dbc.Tooltip(
                                                "Export the current figure",
                                                target="export-scatter2d-left",
                                                placement="top",
                                            ),
                                        ],
                                        style={"marginTop": 10},
                                    ),
                                ]
                            ),
                            is_open=False,
                            id="collapse-left2d",
                        ),
                    ],
                    type="default",
                ),
            ]
        )
    ],
    className="shadow-sm",
)

right2d_card = dbc.Card(
    [
        dbc.CardBody(
            [
                dbc.Row(
                    [
                        dbc.Col(dbc.Label("2D View")),
                        dbc.Col(
                            dbc.Checklist(
                                options=[{"label": "Enable", "value": True}],
                                value=[],
                                id="right-switch",
                                switch=True,
                                style={"float": "right"},
                            )
                        ),
                    ]
                ),
                html.Hr(),
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("x"),
                                    dbc.Select(
                                        id="x-picker-2d-right",
                                        disabled=False,
                                    ),
                                ],
                                size="sm",
                            )
                        ),
                        dbc.Tooltip(
                            "Select x axis",
                            target="x-picker-2d-right",
                            placement="top",
                        ),
                        dbc.Col(
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("y"),
                                    dbc.Select(
                                        id="y-picker-2d-right",
                                        disabled=False,
                                    ),
                                ],
                                size="sm",
                            )
                        ),
                        dbc.Tooltip(
                            "Select y axis",
                            target="y-picker-2d-right",
                            placement="top",
                        ),
                        dbc.Col(
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("c"),
                                    dbc.Select(
                                        id="c-picker-2d-right",
                                        disabled=False,
                                    ),
                                ],
                                size="sm",
                            )
                        ),
                        dbc.Tooltip(
                            "Select color axis",
                            target="c-picker-2d-right",
                            placement="top",
                        ),
                        dbc.Col(
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("cmap"),
                                    dbc.Select(
                                        id="colormap-scatter2d-right",
                                        disabled=False,
                                        options=[
                                            {"value": x, "label": x}
                                            for x in colorscales
                                        ],
                                        value="Portland",
                                    ),
                                ],
                                size="sm",
                            )
                        ),
                        dbc.Tooltip(
                            "Select colormap",
                            target="colormap-scatter2d-right",
                            placement="top",
                        ),
                    ],
                    className="g-1 mb-2",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.RadioItems(
                                options=[
                                    {
                                        "label": "Current frame",
                                        "value": "current",
                                    },
                                    {
                                        "label": "All frames",
                                        "value": "all",
                                    },
                                ],
                                value="current",
                                id="scatter2dr-allframe-switch",
                                inline=True,
                                style={"float": "right"},
                            ),
                        )
                    ]
                ),
                dcc.Loading(
                    id="loading_right",
                    children=[
                        dbc.Collapse(
                            html.Div(
                                [
                                    dcc.Graph(
                                        id="scatter2d-right",
                                        config={"displaylogo": False},
                                        figure={
                                            "data": [
                                                {
                                                    "mode": "markers",
                                                    "type": "scattergl",
                                                    "x": [],
                                                    "y": [],
                                                }
                                            ],
                                            "layout": {"uirevision": "no_change"},
                                        },
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                dbc.Button(
                                                    html.I(
                                                        className="bi bi-eye-slash-fill"
                                                    ),
                                                    id="hide-right",
                                                    color="warning",
                                                    n_clicks=0,
                                                )
                                            ),
                                            dbc.Tooltip(
                                                "Toggle the hidden/visible states of \
                                    the selected dots",
                                                target="hide-right",
                                                placement="top",
                                            ),
                                            dbc.Col(
                                                dbc.Button(
                                                    html.I(
                                                        className="bi bi-camera-fill"
                                                    ),
                                                    id="export-scatter2d-right",
                                                    n_clicks=0,
                                                    style={"float": "right"},
                                                )
                                            ),
                                        ],
                                        style={"marginTop": 10},
                                    ),
                                    dbc.Tooltip(
                                        "Export the current figure",
                                        target="export-scatter2d-right",
                                        placement="top",
                                    ),
                                ]
                            ),
                            is_open=False,
                            id="collapse-right2d",
                        )
                    ],
                    type="default",
                ),
            ]
        )
    ],
    className="shadow-sm",
)


hist_card = dbc.Card(
    [
        dbc.CardBody(
            [
                dbc.Row(
                    [
                        dbc.Col(dbc.Label("Histogram")),
                        dbc.Col(
                            dbc.Checklist(
                                options=[{"label": "Enable", "value": True}],
                                value=[],
                                id="histogram-switch",
                                switch=True,
                                style={"float": "right"},
                            )
                        ),
                    ]
                ),
                html.Hr(),
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("x"),
                                    dbc.Select(
                                        id="x-picker-histogram",
                                        disabled=False,
                                    ),
                                ]
                            )
                        ),
                        dbc.Tooltip(
                            "Select x axis",
                            target="x-picker-histogram",
                            placement="top",
                        ),
                        dbc.Col(
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("y"),
                                    dbc.Select(
                                        id="y-histogram",
                                        options=[
                                            {
                                                "label": "Probability",
                                                "value": "probability",
                                            },
                                            {"label": "Density", "value": "density"},
                                        ],
                                        value="density",
                                        disabled=False,
                                    ),
                                ]
                            )
                        ),
                        dbc.Tooltip(
                            "Select y axis",
                            target="y-histogram",
                            placement="top",
                        ),
                        dbc.Col(
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("c"),
                                    dbc.Select(
                                        id="c-picker-histogram",
                                        disabled=False,
                                    ),
                                ]
                            )
                        ),
                        dbc.Tooltip(
                            "Select color axis",
                            target="c-picker-histogram",
                            placement="top",
                        ),
                    ]
                ),
                dcc.Loading(
                    id="loading_histogram",
                    children=[
                        dbc.Collapse(
                            html.Div(
                                [
                                    dcc.Graph(
                                        id="histogram",
                                        config={"displaylogo": False},
                                        figure={
                                            "data": [{"type": "histogram", "x": []}]
                                        },
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                dbc.Button(
                                                    html.I(
                                                        className="bi bi-camera-fill"
                                                    ),
                                                    id="export-histogram",
                                                    n_clicks=0,
                                                    style={"float": "right"},
                                                )
                                            ),
                                        ]
                                    ),
                                    dbc.Tooltip(
                                        "Export the current figure",
                                        target="export-histogram",
                                        placement="top",
                                    ),
                                ]
                            ),
                            is_open=False,
                            id="collapse-hist",
                        )
                    ],
                    type="default",
                ),
            ]
        )
    ],
    className="shadow-sm",
)


violin_card = dbc.Card(
    [
        dbc.CardBody(
            [
                dbc.Row(
                    [
                        dbc.Col(dbc.Label("Violin")),
                        dbc.Col(
                            dbc.Checklist(
                                options=[{"label": "Enable", "value": True}],
                                value=[],
                                id="violin-switch",
                                switch=True,
                                style={"float": "right"},
                            )
                        ),
                    ]
                ),
                html.Hr(),
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("x"),
                                    dbc.Select(
                                        id="x-picker-violin",
                                        disabled=False,
                                    ),
                                ]
                            )
                        ),
                        dbc.Tooltip(
                            "Select x axis",
                            target="x-picker-violin",
                            placement="top",
                        ),
                        dbc.Col(
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("y"),
                                    dbc.Select(
                                        id="y-picker-violin",
                                        disabled=False,
                                    ),
                                ]
                            )
                        ),
                        dbc.Tooltip(
                            "Select y axis",
                            target="y-picker-violin",
                            placement="top",
                        ),
                        dbc.Col(
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("c"),
                                    dbc.Select(
                                        id="c-picker-violin",
                                        disabled=False,
                                    ),
                                ]
                            )
                        ),
                        dbc.Tooltip(
                            "Select color axis",
                            target="c-picker-violin",
                            placement="top",
                        ),
                    ]
                ),
                dcc.Loading(
                    id="loading_violin",
                    children=[
                        dbc.Collapse(
                            html.Div(
                                [
                                    dcc.Graph(
                                        id="violin", config={"displaylogo": False}
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                dbc.Button(
                                                    html.I(
                                                        className="bi bi-camera-fill"
                                                    ),
                                                    id="export-violin",
                                                    n_clicks=0,
                                                    style={"float": "right"},
                                                )
                                            ),
                                        ]
                                    ),
                                    dbc.Tooltip(
                                        "Export the current figure",
                                        target="export-violin",
                                        placement="top",
                                    ),
                                ]
                            ),
                            is_open=False,
                            id="collapse-violin",
                        )
                    ],
                    type="default",
                ),
            ]
        )
    ],
    className="shadow-sm",
)


parallel_card = dbc.Card(
    [
        dbc.CardBody(
            [
                dbc.Row(
                    [
                        dbc.Col(dbc.Label("Parallel Categories")),
                        dbc.Col(
                            dbc.Checklist(
                                options=[{"label": "Enable", "value": True}],
                                value=[],
                                id="parallel-switch",
                                switch=True,
                                style={"float": "right"},
                            )
                        ),
                    ]
                ),
                html.Hr(),
                dbc.Row(
                    [
                        dbc.Col(
                            html.Div(
                                dcc.Dropdown(id="dim-picker-parallel", multi=True),
                                className=THEME,
                            ),
                        ),
                        dbc.Tooltip(
                            "Dimensions",
                            target="dim-picker-parallel",
                            placement="top",
                        ),
                        dbc.Col(
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("c"),
                                    dbc.Select(
                                        id="c-picker-parallel",
                                        disabled=False,
                                    ),
                                ]
                            )
                        ),
                        dbc.Tooltip(
                            "Select color axis",
                            target="c-picker-parallel",
                            placement="top",
                        ),
                    ]
                ),
                dcc.Loading(
                    id="loading_parallel",
                    children=[
                        dbc.Collapse(
                            html.Div(
                                [
                                    dcc.Graph(
                                        id="parallel", config={"displaylogo": False}
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                dbc.Button(
                                                    html.I(
                                                        className="bi bi-camera-fill"
                                                    ),
                                                    id="export-parallel",
                                                    n_clicks=0,
                                                    style={"float": "right"},
                                                )
                                            ),
                                        ]
                                    ),
                                    dbc.Tooltip(
                                        "Export the current figure",
                                        target="export-parallel",
                                        placement="top",
                                    ),
                                ]
                            ),
                            is_open=False,
                            id="collapse-parallel",
                        )
                    ],
                    type="default",
                ),
            ]
        )
    ],
    className="shadow-sm",
)


heatmap_card = dbc.Card(
    [
        dbc.CardBody(
            [
                dbc.Row(
                    [
                        dbc.Col(dbc.Label("Heatmap")),
                        dbc.Col(
                            dbc.Checklist(
                                options=[{"label": "Enable", "value": True}],
                                value=[],
                                id="heat-switch",
                                switch=True,
                                style={"float": "right"},
                            )
                        ),
                    ]
                ),
                html.Hr(),
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("x"),
                                    dbc.Select(
                                        id="x-picker-heatmap",
                                        disabled=False,
                                    ),
                                ]
                            )
                        ),
                        dbc.Tooltip(
                            "Select x axis",
                            target="x-picker-heatmap",
                            placement="top",
                        ),
                        dbc.Col(
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("y"),
                                    dbc.Select(
                                        id="y-picker-heatmap",
                                        disabled=False,
                                    ),
                                ]
                            )
                        ),
                        dbc.Tooltip(
                            "Select y axis",
                            target="y-picker-heatmap",
                            placement="top",
                        ),
                    ]
                ),
                dcc.Loading(
                    id="loading_heat",
                    children=[
                        dbc.Collapse(
                            html.Div(
                                [
                                    dcc.Graph(
                                        id="heatmap",
                                        config={"displaylogo": False},
                                        figure={
                                            "data": [
                                                {"type": "histogram2dcontour", "x": []}
                                            ]
                                        },
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                dbc.Button(
                                                    html.I(
                                                        className="bi bi-camera-fill"
                                                    ),
                                                    id="export-heatmap",
                                                    n_clicks=0,
                                                    style={"float": "right"},
                                                )
                                            ),
                                        ]
                                    ),
                                    dbc.Tooltip(
                                        "Export the current figure",
                                        target="export-heatmap",
                                        placement="top",
                                    ),
                                ]
                            ),
                            is_open=False,
                            id="collapse-heatmap",
                        )
                    ],
                    type="default",
                ),
            ]
        )
    ],
    className="shadow-sm",
)


def get_app_layout():
    """
    Get the layout for the Dash app.

    Returns:
    - dbc.Container: The app layout container.
    """
    return dbc.Container(
        [
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
            dcc.Store(id="dark-template", data=pio.templates["plotly_dark"]),
            dcc.Store(id="light-template", data=pio.templates["plotly"]),
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
            modal,
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Row(
                            [
                                html.Div(
                                    html.Img(
                                        src=dash.get_asset_url("sensorview_logo.svg"),
                                        id="sensorview-image",
                                        style={
                                            "height": "110px",
                                            "width": "auto",
                                        },
                                    ),
                                    className="text-center",
                                ),
                                html.H4(APP_TITLE, className="text-center"),
                                html.P(
                                    "Radar Data Visualization",
                                    className="text-center",
                                ),
                            ]
                        ),
                        width=3,
                    ),
                    dbc.Col(
                        dbc.Row(
                            [
                                dbc.Col(
                                    dbc.Row(
                                        [
                                            dbc.InputGroup(
                                                [
                                                    dbc.InputGroupText("Data Path"),
                                                    dbc.Input(
                                                        id="data-path",
                                                        type="text",
                                                        readonly=True,
                                                    ),
                                                ],
                                                size="sm",
                                            ),
                                            dbc.InputGroup(
                                                [
                                                    dbc.InputGroupText("Test Case"),
                                                    dbc.Input(
                                                        id="test-case",
                                                        type="text",
                                                        readonly=True,
                                                    ),
                                                ],
                                                size="sm",
                                                className="mt-1",
                                            ),
                                            dbc.InputGroup(
                                                [
                                                    dbc.InputGroupText("Log File"),
                                                    dbc.Input(
                                                        id="log-file",
                                                        type="text",
                                                        readonly=True,
                                                    ),
                                                ],
                                                size="sm",
                                                className="mt-1",
                                            ),
                                        ]
                                    ),
                                    width=11,
                                ),
                                dbc.Col(
                                    dbc.Button(
                                        html.I(className="bi bi-pencil-square"),
                                        id="select-button",
                                        n_clicks=0,
                                        className="h-100 w-100",
                                    ),
                                    width=1,
                                ),
                                dbc.Col(
                                    dbc.Button(
                                        html.I(className="bi bi-link-45deg"),
                                        id="button-add",
                                        n_clicks=0,
                                        color="secondary",
                                        size="sm",
                                        className="w-100",
                                    ),
                                    width=12,
                                    className="my-2",
                                ),
                                dbc.Tooltip(
                                    "Combine other log files",
                                    target="button-add",
                                    placement="top",
                                ),
                                dbc.Col(
                                    dbc.Collapse(
                                        html.Div(
                                            dcc.Dropdown(id="file-add", multi=True),
                                            className=THEME,
                                        ),
                                        id="collapse-add",
                                        is_open=False,
                                    ),
                                    width=12,
                                ),
                                dbc.Tooltip(
                                    "Select additional log files",
                                    target="file-add",
                                    placement="top",
                                ),
                            ],
                        ),
                        width=9,
                    ),
                ],
                align="center",
                className="my-3",
            ),
            view3d_card,
            dbc.CardGroup([left2d_card, right2d_card], className="mb-3"),
            dbc.CardGroup([hist_card, violin_card], className="mb-3"),
            dbc.CardGroup([parallel_card, heatmap_card], className="mb-3"),
            html.Hr(),
            dbc.Row(
                [
                    dbc.Row(
                        [
                            dbc.Spinner(
                                color="info",
                                spinner_style={"width": "6rem", "height": "6rem"},
                            ),
                            dbc.Label(
                                "Loading ...",
                                color="light",
                                className="text-center mt-3",
                            ),
                        ],
                        align="center",
                        justify="center",
                    )
                ],
                id="loading-view",
                align="center",
                justify="center",
                style={
                    "position": "fixed",
                    "top": 0,
                    "left": 0,
                    "width": "100%",
                    "height": "100%",
                    "backgroundColor": "rgba(0, 0, 0, 0.9)",
                },
            ),
            dcc.Markdown(
                APP_VERSION
                + " | Designed and developed by **Zhengyu Peng** \
                | Powered by [Dash](https://plotly.com/dash/)"
            ),
        ],
        fluid=True,
        className="dbc_light",
    )
