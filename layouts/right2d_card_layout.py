"""Right 2D Card Layout Module

Defines the layout for the right 2D scatter plot card in the SensorView application,
using Dash and Bootstrap components.

Core Components:
---------------
- Enable switch
- Axis selectors (x, y, color)
- Colormap selector
- Frame selection radio
- 2D scatter plot area with loading overlay
- Hide and export buttons

Dependencies:
------------
- dash & dash-bootstrap-components

Usage:
------
Import the right 2D card layout:
    from layouts.right2d_card_layout import right2d_card

Author: Zhengyu Peng
Email: zpeng.me@gmail.com
Website: https://zpeng.me
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc

from layouts.layout_constants import colorscales


def get_right2d_card_layout():
    return dbc.Card(
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
