"""Threshold Map Card Layout Module

Layout for the radar threshold-map panel (range-Doppler, range-angle, ...).
These are dense 2D arrays read straight from the HDF5 sidecar, so the card
exposes only what selects and colors a map -- there is nothing to filter.

Usage:
    from layouts.threshold_card_layout import get_threshold_card_layout

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc

import dash_bootstrap_components as dbc

from layouts.layout_constants import colorscales


def get_threshold_card_layout():
    """
    Creates the threshold-map card with sensor and colormap selectors.

    The card includes:
        - A sensor selector listing sensors that have threshold maps
        - A colormap selector
        - A lock-color-scale switch for stable colors while scrubbing
        - The threshold-map graph

    Args:
        None

    Returns:
        dbc.Card: A Dash Bootstrap Card component containing the threshold map
        controls and figure. The card hides itself when the loaded dataset
        declares no threshold maps.
    """
    return dbc.Card(
        [
            dbc.CardBody(
                [
                    dbc.Row(
                        [
                            dbc.Col(dbc.Label("Threshold Map"), width="auto"),
                            dbc.Col(
                                dbc.InputGroup(
                                    [
                                        dbc.InputGroupText("Sensor"),
                                        dbc.Select(id="threshold-sensor-picker"),
                                        dbc.Tooltip(
                                            "Select the sensor whose threshold "
                                            "map to display",
                                            target="threshold-sensor-picker",
                                            placement="top",
                                        ),
                                    ],
                                    size="sm",
                                ),
                                width=4,
                                className="ms-auto",
                            ),
                            dbc.Col(
                                dbc.InputGroup(
                                    [
                                        dbc.InputGroupText("Colormap"),
                                        dbc.Select(
                                            id="colormap-threshold",
                                            options=[
                                                {"value": x, "label": x}
                                                for x in colorscales
                                            ],
                                            value="Jet",
                                        ),
                                        dbc.Tooltip(
                                            "Select colormap",
                                            target="colormap-threshold",
                                            placement="top",
                                        ),
                                    ],
                                    size="sm",
                                ),
                                width=3,
                            ),
                            dbc.Col(
                                dbc.Checklist(
                                    options=[{"label": "Lock scale", "value": True}],
                                    value=[True],
                                    id="threshold-lock-scale",
                                    switch=True,
                                    className="mb-0 d-flex align-items-center",
                                ),
                                width="auto",
                            ),
                            dbc.Tooltip(
                                "Hold the color scale fixed across frames so "
                                "levels stay comparable while scrubbing",
                                target="threshold-lock-scale",
                                placement="top",
                            ),
                        ],
                        className="mb-2 align-items-center",
                    ),
                    dcc.Loading(
                        dcc.Graph(
                            id="threshold-map",
                            config={"displaylogo": False},
                            figure={
                                "data": [{"type": "heatmap", "z": []}],
                                "layout": {"uirevision": "no_change"},
                            },
                            style={"height": "45vh"},
                        )
                    ),
                ],
                className="mx-3 my-3",
            )
        ],
        id="threshold-card",
        className="mb-3",
        style={"display": "none"},
    )
