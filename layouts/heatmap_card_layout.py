"""Heatmap Pane Layout Module

The heatmap pane in the analysis dock: a 2D density contour of two numeric
columns, with an optional log color scale for long-tailed counts.

Usage:
    from layouts.heatmap_card_layout import get_heatmap_pane_layout

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc

from layouts.layout_constants import colorscales
from layouts.pane_common import icon_button, labelled_select, pane


def get_heatmap_pane_layout():
    """
    Build the heatmap pane.

    Returns:
        html.Div: The pane.
    """
    controls = [
        labelled_select("x-picker-heatmap", "x", "Column plotted on the x axis"),
        labelled_select("y-picker-heatmap", "y", "Column plotted on the y axis"),
        labelled_select(
            "colormap-heatmap",
            "map",
            "Colormap applied to the density",
            options=[{"value": x, "label": x} for x in colorscales],
            value="Jet",
        ),
        html.Div(
            [
                dbc.Checklist(
                    options=[{"label": "Log color", "value": True}],
                    value=[],
                    id="heatmap-log-scale",
                    switch=True,
                    inline=True,
                    className="d-flex align-items-center",
                ),
                dbc.Tooltip(
                    "Use a log scale for the color axis",
                    target="heatmap-log-scale",
                    placement="top",
                ),
            ],
            className="d-flex align-items-center ms-1",
        ),
        icon_button(
            "export-heatmap",
            "bi-camera-fill",
            "Export this figure",
            class_name="ms-auto",
        ),
    ]

    graph = dcc.Graph(
        id="heatmap",
        responsive=True,
        config={"displaylogo": False},
        figure={"data": [{"type": "histogram2dcontour", "x": []}]},
        style={"height": "100%", "width": "100%"},
    )

    return pane(
        controls, graph, collapse_id="collapse-heatmap", loading_id="loading_heat"
    )
