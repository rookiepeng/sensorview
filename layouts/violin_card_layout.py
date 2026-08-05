"""Violin Pane Layout Module

The violin pane in the analysis dock: the distribution of a numeric column
across the levels of a categorical one.

Usage:
    from layouts.violin_card_layout import get_violin_pane_layout

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc

from layouts.pane_common import icon_button, labelled_select, pane


def get_violin_pane_layout():
    """
    Build the violin pane.

    Returns:
        html.Div: The pane.
    """
    controls = [
        labelled_select("x-picker-violin", "x", "Categorical column to group by"),
        labelled_select("y-picker-violin", "y", "Numeric column to describe"),
        labelled_select("c-picker-violin", "c", "Column the violins are split by"),
        icon_button(
            "export-violin",
            "bi-camera-fill",
            "Export this figure",
            class_name="ms-auto",
        ),
    ]

    graph = dcc.Graph(
        id="violin",
        responsive=True,
        config={"displaylogo": False},
        style={"height": "100%", "width": "100%"},
    )

    return pane(
        controls, graph, collapse_id="collapse-violin", loading_id="loading_violin"
    )
