"""Heatmap Card Layout Module

Layout for heatmap visualization card with enable switch, axis selectors,
plot area with loading overlay, and export button.

Usage:
    from layouts.heatmap_card_layout import get_heatmap_card

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc

from layouts.layout_constants import colorscales


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
                                    ],
                                    size="sm",
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
                                    ],
                                    size="sm",
                                )
                            ),
                            dbc.Tooltip(
                                "Select y axis",
                                target="y-picker-heatmap",
                                placement="top",
                            ),
                            dbc.Col(
                                dbc.InputGroup(
                                    [
                                        dbc.InputGroupText("cmap"),
                                        dbc.Select(
                                            id="colormap-heatmap",
                                            options=[
                                                {"value": x, "label": x}
                                                for x in colorscales
                                            ],
                                            value="Jet",
                                        ),
                                    ],
                                    size="sm",
                                )
                            ),
                            dbc.Tooltip(
                                "Select colormap",
                                target="colormap-heatmap",
                                placement="top",
                            ),
                            dbc.Col(
                                dbc.Checklist(
                                    options=[{"label": "Log color", "value": True}],
                                    value=[],
                                    id="heatmap-log-scale",
                                    switch=True,
                                    className="mb-0 d-flex align-items-center",
                                    inline=True,
                                ),
                                width="auto",
                                className="d-flex align-items-center",
                            ),
                            dbc.Tooltip(
                                "Use log scale for color axis",
                                target="heatmap-log-scale",
                                placement="top",
                            ),
                        ],
                        class_name="mb-3",
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
                                            ],
                                            class_name="mt-2",
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
