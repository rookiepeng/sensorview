"""Left 2D Card Layout Module

Layout for left 2D scatter plot card with enable switch, axis selectors (x, y, color),
colormap selector, frame selection, plot area, and hide/export buttons.

Usage:
    from layouts.left2d_card_layout import get_left2d_card_layout

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc

from layouts.layout_constants import colorscales


def get_left2d_card_layout():
    """
    Creates and returns a Dash Bootstrap Card layout for the 2D scatter plot controls and display.

    The layout includes:
        - A header with a label and enable switch for the 2D view.
        - Dropdown selectors for x, y, color axes, and colormap.
        - Radio buttons to toggle between current frame and all frames.
        - A collapsible section containing a loading spinner, the 2D scatter plot,
        and action buttons for hiding points and exporting the figure.
        - Tooltips for user guidance.

    Args:
        None

    Returns:
        dbc.Card: A Dash Bootstrap Card component containing the full 2D scatter plot control
        and display layout.
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
