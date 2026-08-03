"""Histogram Pane Layout Module

The histogram pane in the analysis dock: one numeric column binned, optionally
split by a categorical column.

Usage:
    from layouts.hist_card_layout import get_hist_pane_layout

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc

from layouts.pane_common import icon_button, labelled_select, pane


def get_hist_pane_layout():
    """
    Build the histogram pane.

    Returns:
        html.Div: The pane.
    """
    controls = [
        labelled_select("x-picker-histogram", "x", "Column to bin"),
        labelled_select(
            "y-histogram",
            "y",
            "How bin heights are normalized",
            options=[
                {"label": "Probability", "value": "probability"},
                {"label": "Density", "value": "density"},
            ],
            value="density",
        ),
        labelled_select("c-picker-histogram", "c", "Column the bins are split by"),
        icon_button(
            "export-histogram",
            "bi-camera-fill",
            "Export this figure",
            class_name="ms-auto",
        ),
    ]

    graph = dcc.Graph(
        id="histogram",
        responsive=True,
        config={"displaylogo": False},
        figure={"data": [{"type": "histogram", "x": []}]},
        style={"height": "100%", "width": "100%"},
    )

    return pane(
        controls, graph, collapse_id="collapse-hist", loading_id="loading_histogram"
    )
