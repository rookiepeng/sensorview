"""SensorView Layout Module

This module defines the complete UI layout and visual components of the
SensorView application using Dash and Bootstrap components.

Core Components:
---------------
1. Modal Dialogs:
   - Configuration modal
   - File selection interface
   - Settings management

2. Visualization Cards:
   - 3D scatter plot view
   - 2D scatter plot views
   - Histogram, Violin plots
   - Heatmap visualization
   - Parallel categories view

3. Control Elements:
   - Playback controls
   - Data filtering
   - View customization
   - Export options

Layout Structure:
---------------
- Main container
  |- Header section
  |- Configuration modal
  |- 3D view card
  |- 2D view cards
  |- Analysis view cards
  |- Loading overlay
  |- Footer

Dependencies:
------------
- dash & dash-bootstrap-components
- plotly
- app_config settings

Usage:
------
Import the layout generator:
    from app_layout import get_app_layout

Author: Zhengyu Peng
Email: zpeng.me@gmail.com
Website: https://zpeng.me
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

import uuid

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc

import plotly.io as pio

from app_config import APP_VERSION

from layouts.modal_layout import modal
from layouts.header_layout import get_header_layout
from layouts.view3d_card_layout import view3d_card
from layouts.left2d_card_layout import left2d_card
from layouts.right2d_card_layout import right2d_card
from layouts.hist_card_layout import hist_card
from layouts.violin_card_layout import violin_card
from layouts.parallel_card_layout import parallel_card
from layouts.heatmap_card_layout import heatmap_card


def get_app_layout(app):
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
            dcc.Store(id="dark-template", data=pio.templates["plotly_dark"]),
            dcc.Store(id="light-template", data=pio.templates["plotly"]),
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
            modal,
            get_header_layout(app),
            view3d_card,
            dbc.CardGroup([left2d_card, right2d_card], className="mb-3"),
            dbc.CardGroup([hist_card, violin_card], className="mb-3"),
            dbc.CardGroup([parallel_card, heatmap_card], className="mb-3"),
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
                APP_VERSION
                + " | Designed and developed by **Zhengyu Peng** \
                | Powered by [Dash](https://plotly.com/dash/)"
            ),
        ],
        fluid=True,
        className="dbc_light",
    )
