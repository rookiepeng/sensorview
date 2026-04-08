"""SensorView Layout Module

Defines the complete UI layout and visual components using Dash and Bootstrap
including modal dialogs, visualization cards, control elements, and main container.

Usage:
    from app_layout import get_app_layout

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

import uuid

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc

import plotly.io as pio

from app_config import APP_VERSION

from layouts.modal_layout import get_modal_layout
from layouts.header_layout import get_header_layout
from layouts.view3d_card_layout import get_view3d_card_layout
from layouts.left2d_card_layout import get_left2d_card_layout
from layouts.right2d_card_layout import get_right2d_card_layout
from layouts.hist_card_layout import get_hist_card_layout
from layouts.violin_card_layout import get_violin_card_layout
from layouts.parallel_card_layout import get_parallel_card_layout
from layouts.heatmap_card_layout import get_heatmap_card


def get_app_layout():
    """
    Get the layout for the Dash app.

    Returns:
    - dbc.Container: The app layout container.
    """
    return dbc.Container(
        [
            dcc.Store(id="selected-data-left"),
            dcc.Store(id="selected-data-right"),
            dcc.Store(id="session-id", data=str(uuid.uuid4())),
            dcc.Store(id="filter-trigger", data=0),
            dcc.Store(id="left-regenerate-trigger", data=0),
            dcc.Store(id="right-regenerate-trigger", data=0),
            dcc.Store(id="left-hide-trigger", data=0),
            dcc.Store(id="right-hide-trigger", data=0),
            dcc.Store(id="file-loaded-trigger", data=0),
            dcc.Store(id="background-trigger", data=0),
            dcc.Store(id="dummy-background"),
            dcc.Store(id="visible-table-change-trigger", data=0),
            dcc.Store(id="local-case-selection", storage_type="local"),
            dcc.Store(id="local-file-selection", storage_type="local"),
            dcc.Store(id="current-file"),
            dcc.Store(id="key-dict"),
            dcc.Store(id="relayout-data", data=None),
            dcc.Store(id="dark-template", data=pio.templates["plotly_dark"]),  # type: ignore
            dcc.Store(id="light-template", data=pio.templates["plotly"]),  # type: ignore
            dcc.Store(id="trigger-remote-figure", data=0),
            dcc.Interval(
                id="interval-buffer",
                interval=1000,  # in milliseconds
                disabled=False,
                n_intervals=0,
            ),
            dcc.Store(id="local-buffer-index", data=-1),
            dcc.Store(id="worker-status"),
            dcc.Download(id="download"),
            get_modal_layout(),
            get_header_layout(),
            get_view3d_card_layout(),
            dbc.CardGroup(
                [get_left2d_card_layout(), get_right2d_card_layout()], className="mb-3"
            ),
            dbc.CardGroup(
                [get_hist_card_layout(), get_violin_card_layout()], className="mb-3"
            ),
            dbc.CardGroup(
                [get_parallel_card_layout(), get_heatmap_card()], className="mb-3"
            ),
            html.Hr(),
            dbc.Row(
                [
                    dbc.Row(
                        [
                            dbc.Spinner(
                                color="info",
                                spinner_style={"width": "6rem", "height": "6rem"},
                            ),
                            dbc.Label(
                                "Loading ...",
                                color="light",
                                className="text-center mt-3",
                            ),
                        ],
                        align="center",
                        justify="center",
                    )
                ],
                id="loading-view",
                align="center",
                justify="center",
                style={
                    "position": "fixed",
                    "top": 0,
                    "left": 0,
                    "width": "100%",
                    "height": "100%",
                    "backgroundColor": "rgba(0, 0, 0, 0.9)",
                },
            ),
            dcc.Markdown(
                APP_VERSION + " | Powered by [Dash](https://plotly.com/dash/)"
            ),
        ],
        fluid=True,
        className="dbc",
    )
