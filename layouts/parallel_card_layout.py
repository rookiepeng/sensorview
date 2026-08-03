"""Parallel Categories Pane Layout Module

The parallel-categories pane in the analysis dock: how records flow between the
levels of several categorical columns at once.

Usage:
    from layouts.parallel_card_layout import get_parallel_pane_layout

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc

from app_config import THEME

from layouts.pane_common import icon_button, labelled_select, pane


def get_parallel_pane_layout():
    """
    Build the parallel categories pane.

    Returns:
        html.Div: The pane.
    """
    controls = [
        html.Div(
            [
                html.Div(
                    dcc.Dropdown(id="dim-picker-parallel", multi=True),
                    className=THEME,
                ),
                dbc.Tooltip(
                    "Categorical columns to lay out as axes, left to right",
                    target="dim-picker-parallel",
                    placement="top",
                ),
            ],
            className="sv-grow",
            # Several column names side by side need more room than a select.
            style={"flex": "1 1 240px"},
        ),
        labelled_select("c-picker-parallel", "c", "Column the ribbons are colored by"),
        icon_button(
            "export-parallel",
            "bi-camera-fill",
            "Export this figure",
            class_name="ms-auto",
        ),
    ]

    graph = dcc.Graph(
        id="parallel",
        responsive=True,
        config={"displaylogo": False},
        style={"height": "100%", "width": "100%"},
    )

    return pane(
        controls, graph, collapse_id="collapse-parallel", loading_id="loading_parallel"
    )
