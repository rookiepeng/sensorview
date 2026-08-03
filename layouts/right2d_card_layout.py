"""Right 2D Pane Layout Module

The right 2D scatter pane in the analysis dock. Identical in structure to the
left pane; the two exist so a dataset can be looked at through two different
projections at once.

Usage:
    from layouts.right2d_card_layout import get_right2d_pane_layout

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc

from layouts.layout_constants import colorscales
from layouts.pane_common import icon_button, labelled_select, number_input, pane


def get_right2d_pane_layout():
    """
    Build the right 2D scatter pane.

    Returns:
        html.Div: The pane.
    """
    controls = [
        labelled_select("x-picker-2d-right", "x", "Column plotted on the x axis"),
        labelled_select("y-picker-2d-right", "y", "Column plotted on the y axis"),
        labelled_select("c-picker-2d-right", "c", "Column mapped to marker color"),
        labelled_select(
            "colormap-scatter2d-right",
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
            id="scatter2dr-allframe-switch",
            inline=True,
            className="ms-1",
        ),
        dbc.Tooltip(
            "Plot only the current frame, or every frame at once",
            target="scatter2dr-allframe-switch",
            placement="top",
        ),
        html.Div(
            [
                dbc.Button(
                    html.I(className="bi bi-arrows-angle-expand"),
                    id="range-config-button-right",
                    color="transparent",
                    n_clicks=0,
                    className="sv-icon-btn",
                ),
                dbc.Tooltip(
                    "Set fixed axis limits",
                    target="range-config-button-right",
                    placement="top",
                ),
            ],
            className="ms-auto",
        ),
        icon_button(
            "hide-right",
            "bi-eye-slash-fill",
            "Toggle the hidden/visible state of the selected points",
            color="warning",
        ),
        icon_button("export-scatter2d-right", "bi-camera-fill", "Export this figure"),
    ]

    ranges = dbc.Collapse(
        html.Div(
            [
                number_input("x-min-2d-right", "x min"),
                number_input("x-max-2d-right", "x max"),
                number_input("y-min-2d-right", "y min"),
                number_input("y-max-2d-right", "y max"),
            ],
            className="sv-pane-controls",
        ),
        id="range-config-collapse-right",
        is_open=False,
    )

    graph = dcc.Graph(
        id="scatter2d-right",
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
        collapse_id="collapse-right2d",
        loading_id="loading_right",
        extra_rows=[ranges],
    )
