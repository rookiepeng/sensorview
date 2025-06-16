"""SensorView Header Layout Module

This module defines the header section of the SensorView application using Dash and Bootstrap components.

Core Components:
---------------
- Application logo and title
- Data path, test case, and log file display
- File selection and combination controls
- Tooltips and dropdowns for file management

Layout Structure:
---------------
- Header row
  |- Logo and title column
  |- File information and controls column

Dependencies:
------------
- dash & dash-bootstrap-components
- app_config settings

Usage:
------
Import the header layout:
    from header_layout import header

Author: Zhengyu Peng
Email: zpeng.me@gmail.com
Website: https://zpeng.me
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc

from app_config import APP_TITLE, THEME


def get_header_layout(app):
    return dbc.Row(
        [
            dbc.Col(
                dbc.Row(
                    [
                        html.Div(
                            html.Img(
                                src=app.get_asset_url("sensorview_logo.svg"),
                                id="sensorview-image",
                                style={
                                    "height": "110px",
                                    "width": "auto",
                                },
                            ),
                            className="text-center",
                        ),
                        html.H4(APP_TITLE, className="text-center"),
                        html.P(
                            "Radar Data Visualization",
                            className="text-center",
                        ),
                    ]
                ),
                width=3,
            ),
            dbc.Col(
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.Row(
                                [
                                    dbc.InputGroup(
                                        [
                                            dbc.InputGroupText("Data Path"),
                                            dbc.Input(
                                                id="data-path",
                                                type="text",
                                                readonly=True,
                                            ),
                                        ],
                                        size="sm",
                                    ),
                                    dbc.InputGroup(
                                        [
                                            dbc.InputGroupText("Test Case"),
                                            dbc.Input(
                                                id="test-case",
                                                type="text",
                                                readonly=True,
                                            ),
                                        ],
                                        size="sm",
                                        className="mt-1",
                                    ),
                                    dbc.InputGroup(
                                        [
                                            dbc.InputGroupText("Log File"),
                                            dbc.Input(
                                                id="log-file",
                                                type="text",
                                                readonly=True,
                                            ),
                                        ],
                                        size="sm",
                                        className="mt-1",
                                    ),
                                ]
                            ),
                            width=11,
                        ),
                        dbc.Col(
                            dbc.Button(
                                html.I(className="bi bi-pencil-square"),
                                id="select-button",
                                n_clicks=0,
                                className="h-100 w-100",
                            ),
                            width=1,
                        ),
                        dbc.Col(
                            dbc.Button(
                                html.I(className="bi bi-link-45deg"),
                                id="button-add",
                                n_clicks=0,
                                color="secondary",
                                size="sm",
                                className="w-100",
                            ),
                            width=12,
                            className="my-2",
                        ),
                        dbc.Tooltip(
                            "Combine other log files",
                            target="button-add",
                            placement="top",
                        ),
                        dbc.Col(
                            dbc.Collapse(
                                html.Div(
                                    dcc.Dropdown(id="file-add", multi=True),
                                    className=THEME,
                                ),
                                id="collapse-add",
                                is_open=False,
                            ),
                            width=12,
                        ),
                        dbc.Tooltip(
                            "Select additional log files",
                            target="file-add",
                            placement="top",
                        ),
                    ],
                ),
                width=9,
            ),
        ],
        align="center",
        className="my-3",
    )
