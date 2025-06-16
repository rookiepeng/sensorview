"""Histogram Card Layout Module

Defines the layout for the histogram visualization card in the SensorView application,
using Dash and Bootstrap components.

Core Components:
---------------
- Histogram enable switch
- Axis selectors (x, y, color)
- Histogram plot area with loading overlay
- Export button

Dependencies:
------------
- dash & dash-bootstrap-components

Usage:
------
Import the histogram card layout:
    from layouts.hist_card_layout import hist_card

Author: Zhengyu Peng
Email: zpeng.me@gmail.com
Website: https://zpeng.me
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc


def get_hist_card_layout():
    """
    Creates and returns a Dash Bootstrap Card layout for a histogram visualization panel.

    The layout includes:
        - A header with a label and an enable switch.
        - Selectors for x, y, and color axes, each with tooltips.
        - A loading spinner that wraps a collapsible area containing:
            - A histogram graph.
            - An export button with tooltip.

    Args:
        None

    Returns:
        dbc.Card: A Dash Bootstrap Card component containing the histogram controls and visualization.
    """
    return dbc.Card(
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
                                                {
                                                    "label": "Density",
                                                    "value": "density",
                                                },
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
