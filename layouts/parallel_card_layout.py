"""Parallel Categories Card Layout Module

Layout for parallel categories visualization card with enable switch, axis selectors,
plot area with loading overlay, and export button.

Usage:
    from layouts.parallel_card_layout import get_parallel_card_layout

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc

from app_config import THEME


def get_parallel_card_layout():
    """
    Creates and returns a Dash Bootstrap Card layout for configuring and displaying a
    parallel categories plot.

    The layout includes:
        - A label and switch to enable/disable the parallel categories plot.
        - A dropdown for selecting dimensions.
        - A select input for choosing the color axis.
        - Tooltips for guidance.
        - A loading spinner while the plot is being generated.
        - A collapsible section containing the plot, an export button, and an export tooltip.

    Args:
        None

    Returns:
        dbc.Card: A Dash Bootstrap Card component containing the layout for the
        parallel categories plot.
    """
    return dbc.Card(
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
                                    ],
                                    size="sm",
                                )
                            ),
                            dbc.Tooltip(
                                "Select color axis",
                                target="c-picker-parallel",
                                placement="top",
                            ),
                        ],
                        class_name="mb-3",
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
                                            ],
                                            class_name="mt-2",
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
