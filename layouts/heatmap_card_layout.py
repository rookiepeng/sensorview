"""Heatmap Card Layout Module

Defines the layout for the heatmap visualization card in the SensorView application,
using Dash and Bootstrap components.

Core Components:
---------------
- Heatmap enable switch
- Axis selectors (x, y)
- Heatmap plot area with loading overlay
- Export button

Dependencies:
------------
- dash & dash-bootstrap-components

Usage:
------
Import the heatmap card layout:
    from layouts.heatmap_card_layout import heatmap_card

Author: Zhengyu Peng
Email: zpeng.me@gmail.com
Website: https://zpeng.me
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc


def get_heatmap_card():
    """
    Creates a Dash Bootstrap Card layout for a heatmap visualization with controls.

    The card includes:
        - A header with a label and an enable switch.
        - Dropdown selectors for x and y axes with tooltips.
        - A collapsible section containing a loading spinner, a heatmap graph, 
          an export button, and corresponding tooltips.

    Args:
        None

    Returns:
        dbc.Card: A Dash Bootstrap Card component containing the heatmap controls and visualization.
    """
    return dbc.Card(
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
                                                    {
                                                        "type": "histogram2dcontour",
                                                        "x": [],
                                                    }
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
