"""Histogram Card Layout Module

Layout for histogram visualization card with enable switch, axis selectors (x, y, color),
plot area with loading overlay, and export button.

Usage:
    from layouts.hist_card_layout import get_hist_card_layout

Author: Zhengyu Peng
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
        dbc.Card: A Dash Bootstrap Card component containing the
        histogram controls and visualization.
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
                                    ],
                                    size="sm",
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
                                    ],
                                    size="sm",
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
                                    ],
                                    size="sm",
                                )
                            ),
                            dbc.Tooltip(
                                "Select color axis",
                                target="c-picker-histogram",
                                placement="top",
                            ),
                        ],
                        class_name="mb-3",
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
                                            ],
                                            class_name="mt-2",
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
