"""Violin Card Layout Module

Layout for violin plot visualization card with enable switch, axis selectors,
plot area with loading overlay, and export button.

Usage:
    from layouts.violin_card_layout import get_violin_card_layout

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc


def get_violin_card_layout():
    """
    Creates and returns a Dash Bootstrap Card layout for a violin plot visualization panel.

    The layout includes:
        - A header with a label and an enable switch.
        - Selectors for x, y, and color axes, each with tooltips.
        - A loading spinner that wraps a collapsible area containing:
            - A violin plot graph.
            - An export button with tooltip.

    Args:
        None

    Returns:
        dbc.Card: A Dash Bootstrap Card component containing the violin plot controls and visualization.
    """
    return dbc.Card(
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
