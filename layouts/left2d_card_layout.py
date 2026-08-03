"""Left 2D Pane Layout Module

The left 2D scatter pane in the analysis dock: axis and color selectors, axis
limits, current-frame vs all-frames scope, and the selection tools that relabel
points as hidden.

Usage:
    from layouts.left2d_card_layout import get_left2d_pane_layout

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc

from layouts.layout_constants import colorscales
from layouts.pane_common import icon_button, labelled_select, number_input, pane


def get_left2d_pane_layout():
    """
    Build the left 2D scatter pane.

    Returns:
        html.Div: The pane.
    """
    controls = [
        labelled_select("x-picker-2d-left", "x", "Column plotted on the x axis"),
        labelled_select("y-picker-2d-left", "y", "Column plotted on the y axis"),
        labelled_select("c-picker-2d-left", "c", "Column mapped to marker color"),
        labelled_select(
            "colormap-scatter2d-left",
            "map",
            "Colormap applied to the color axis",
            options=[{"value": x, "label": x} for x in colorscales],
            value="Portland",
        ),
        dbc.RadioItems(
            options=[
                {"label": "Frame", "value": "current"},
                {"label": "All", "value": "all"},
            ],
            value="current",
            id="scatter2dl-allframe-switch",
            inline=True,
            className="ms-1",
        ),
        dbc.Tooltip(
            "Plot only the current frame, or every frame at once",
            target="scatter2dl-allframe-switch",
            placement="top",
        ),
        html.Div(
            [
                dbc.Button(
                    html.I(className="bi bi-arrows-angle-expand"),
                    id="range-config-button-left",
                    color="transparent",
                    n_clicks=0,
                    className="sv-icon-btn",
                ),
                dbc.Tooltip(
                    "Set fixed axis limits",
                    target="range-config-button-left",
                    placement="top",
                ),
            ],
            className="ms-auto",
        ),
        icon_button(
            "hide-left",
            "bi-eye-slash-fill",
            "Toggle the hidden/visible state of the selected points",
            color="warning",
        ),
        icon_button("export-scatter2d-left", "bi-camera-fill", "Export this figure"),
    ]

    ranges = dbc.Collapse(
        html.Div(
            [
                number_input("x-min-2d-left", "x min"),
                number_input("x-max-2d-left", "x max"),
                number_input("y-min-2d-left", "y min"),
                number_input("y-max-2d-left", "y max"),
            ],
            className="sv-pane-controls",
        ),
        id="range-config-collapse-left",
        is_open=False,
    )

    graph = dcc.Graph(
        id="scatter2d-left",
        responsive=True,
        config={"displaylogo": False},
        figure={
            "data": [{"mode": "markers", "type": "scattergl", "x": [], "y": []}],
            "layout": {"uirevision": "no_change"},
        },
        style={"height": "100%", "width": "100%"},
    )

    return pane(
        controls,
        graph,
        collapse_id="collapse-left2d",
        loading_id="loading_left",
        extra_rows=[ranges],
    )
