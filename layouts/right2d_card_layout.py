"""Right 2D Card Layout Module

Layout for right 2D scatter plot card with enable switch, axis selectors (x, y, color),
colormap selector, frame selection, plot area, and hide/export buttons.

Usage:
    from layouts.right2d_card_layout import get_right2d_card_layout

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc

from layouts.layout_constants import colorscales


def get_right2d_card_layout():
    """
    Creates and returns a Dash Bootstrap Card layout for the 2D scatter plot controls and display on the right panel.

    The layout includes:
        - A switch to enable/disable the 2D view.
        - Dropdown selectors for x, y, c (color), and colormap axes.
        - Tooltips for each selector.
        - Radio items to toggle between "Current frame" and "All frames".
        - A loading spinner wrapping a collapsible section containing:
            - The 2D scatter plot graph.
            - Buttons to hide/show selected dots and to export the figure.
            - Tooltips for the buttons.

    Args:
        None

    Returns:
        dbc.Card: A Dash Bootstrap Card component containing the 2D scatter plot controls and display layout.
    """
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
