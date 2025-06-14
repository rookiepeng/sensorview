from dash import dcc
from dash import html

import dash_bootstrap_components as dbc

import plotly.io as pio

from app_config import THEME

from layouts.layout_constants import colorscales

view3d_card = dbc.Card(
    [
        dbc.CardBody(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dbc.InputGroup(
                                            [
                                                dbc.Label(
                                                    html.I(
                                                        className="bi bi-brightness-high-fill"
                                                    ),
                                                    className="me-2",
                                                ),
                                                dbc.Checklist(
                                                    options=[
                                                        {
                                                            "label": html.I(
                                                                className="bi bi-moon-stars-fill"
                                                            ),
                                                            "value": True,
                                                        }
                                                    ],
                                                    value=[True],
                                                    id="darkmode-switch",
                                                    switch=True,
                                                ),
                                                dbc.Tooltip(
                                                    "Toggle between light and dark background",
                                                    id="darkmode-switch-tooltip",
                                                    target="darkmode-switch",
                                                    placement="top",
                                                ),
                                            ],
                                        ),
                                        width="auto",
                                    ),
                                    dbc.Col(
                                        dbc.InputGroup(
                                            [
                                                dbc.InputGroupText("Color"),
                                                dbc.Select(id="c-picker-3d"),
                                                dbc.Tooltip(
                                                    "Select color axis",
                                                    target="c-picker-3d",
                                                    placement="top",
                                                ),
                                            ],
                                            size="sm",
                                        ),
                                        width=3,
                                    ),
                                    dbc.Col(
                                        dbc.InputGroup(
                                            [
                                                dbc.InputGroupText("Colormap"),
                                                dbc.Select(
                                                    id="colormap-3d",
                                                    options=[
                                                        {"value": x, "label": x}
                                                        for x in colorscales
                                                    ],
                                                    value="Portland",
                                                ),
                                                dbc.Tooltip(
                                                    "Select colormap",
                                                    target="colormap-3d",
                                                    placement="top",
                                                ),
                                            ],
                                            size="sm",
                                        ),
                                        width=3,
                                    ),
                                    dbc.Col(
                                        dcc.Graph(
                                            id="scatter3d",
                                            config={
                                                "displaylogo": False,
                                                "modeBarButtonsToRemove": [
                                                    "resetCameraDefault3d",
                                                    "resetCameraLastSave3d",
                                                ],
                                            },
                                            figure={
                                                "data": [
                                                    {
                                                        "mode": "markers",
                                                        "type": "scatter3d",
                                                        "x": [],
                                                        "y": [],
                                                        "z": [],
                                                    }
                                                ],
                                                "layout": {
                                                    "template": pio.templates["plotly"],
                                                    "uirevision": "no_change",
                                                },
                                            },
                                            style={"height": "80vh"},
                                        ),
                                        className="mt-2",
                                    ),
                                    dbc.Col(
                                        dbc.Progress(
                                            id="buffer",
                                            value=0,
                                            color="warning",
                                            style={
                                                "height": "2px",
                                                "marginTop": 0,
                                                "marginBottom": 0,
                                                "marginLeft": 25,
                                                "marginRight": 25,
                                            },
                                            className="mb-0",
                                        ),
                                        width=12,
                                    ),
                                    dbc.Tooltip(
                                        "Progress of buffering on server",
                                        id="buffer-tooltip",
                                        target="buffer",
                                        placement="top",
                                    ),
                                    dbc.Col(
                                        dbc.Progress(
                                            id="buffer-local",
                                            value=0,
                                            color="info",
                                            style={
                                                "height": "2px",
                                                "marginTop": 0,
                                                "marginBottom": 5,
                                                "marginLeft": 25,
                                                "marginRight": 25,
                                            },
                                            className="mb-3",
                                        ),
                                        width=12,
                                    ),
                                    dbc.Col(
                                        dcc.Slider(
                                            id="slider-frame",
                                            step=1,
                                            value=0,
                                            updatemode="drag",
                                            marks=None,
                                            tooltip={
                                                "always_visible": False,
                                                "placement": "top",
                                            },
                                        ),
                                        width=12,
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                dcc.Interval(
                                                    id="interval-component",
                                                    interval=2 * 100,  # in milliseconds
                                                    disabled=True,
                                                    n_intervals=0,
                                                ),
                                                width=4,
                                            ),
                                            dbc.Col(
                                                dbc.ButtonGroup(
                                                    [
                                                        dbc.Button(
                                                            html.I(
                                                                className="bi bi-skip-backward-fill"
                                                            ),
                                                            id="previous-button",
                                                            color="secondary",
                                                            n_clicks=0,
                                                        ),
                                                        dbc.Button(
                                                            html.I(
                                                                className="bi bi-play-fill"
                                                            ),
                                                            id="play-button",
                                                            color="primary",
                                                            n_clicks=0,
                                                        ),
                                                        dbc.Button(
                                                            html.I(
                                                                className="bi bi-stop-fill"
                                                            ),
                                                            id="stop-button",
                                                            color="danger",
                                                            n_clicks=0,
                                                        ),
                                                        dbc.Button(
                                                            html.I(
                                                                className="bi bi-skip-forward-fill"
                                                            ),
                                                            id="next-button",
                                                            color="secondary",
                                                            n_clicks=0,
                                                        ),
                                                    ],
                                                    className="w-100 mx-auto",
                                                ),
                                                width=4,
                                            ),
                                            dbc.Col(
                                                dbc.DropdownMenu(
                                                    [
                                                        dbc.DropdownMenuItem(
                                                            "Export all frames as an HTML video",
                                                            id="export-scatter3d",
                                                            n_clicks=0,
                                                        ),
                                                        dbc.DropdownMenuItem(
                                                            "Export current plot (html)",
                                                            id="export-scatter3d-html",
                                                            n_clicks=0,
                                                        ),
                                                        dbc.DropdownMenuItem(
                                                            "Export current plot (png)",
                                                            id="export-scatter3d-png",
                                                            n_clicks=0,
                                                        ),
                                                        dbc.DropdownMenuItem(
                                                            "Filtered Data (Current Frame)",
                                                            id="export-data-current",
                                                            n_clicks=0,
                                                        ),
                                                        dbc.DropdownMenuItem(
                                                            "Filtered Data (All Frames)",
                                                            id="export-data-all",
                                                            n_clicks=0,
                                                        ),
                                                    ],
                                                    label=html.I(
                                                        className="bi bi-box-arrow-up"
                                                    ),
                                                    id="export-dropdown",
                                                    # right=True,
                                                    style={"float": "right"},
                                                ),
                                                width=4,
                                            ),
                                            dbc.Tooltip(
                                                "Previous frame",
                                                target="previous-button",
                                                placement="top",
                                            ),
                                            dbc.Tooltip(
                                                "Play",
                                                target="play-button",
                                                placement="top",
                                            ),
                                            dbc.Tooltip(
                                                "Stop",
                                                target="stop-button",
                                                placement="top",
                                            ),
                                            dbc.Tooltip(
                                                "Next frame",
                                                target="next-button",
                                                placement="top",
                                            ),
                                            dbc.Tooltip(
                                                "Export",
                                                target="export-dropdown",
                                                placement="top",
                                            ),
                                            html.Div(
                                                id="hidden-scatter3d",
                                                style={"display": "none"},
                                            ),
                                        ],
                                    ),
                                ]
                            ),
                            width=9,
                            className="me-3",
                        ),
                        dbc.Col(
                            dbc.Row(
                                [
                                    dbc.Checklist(
                                        options=[
                                            {
                                                "label": "Overlay all frames",
                                                "value": True,
                                            }
                                        ],
                                        value=[],
                                        id="overlay-switch",
                                        switch=True,
                                    ),
                                    dbc.Tooltip(
                                        "Overlay all the frames",
                                        target="overlay-switch",
                                        placement="top",
                                    ),
                                    dbc.Checklist(
                                        options=[
                                            {
                                                "label": "Click to change visibility",
                                                "value": True,
                                            }
                                        ],
                                        value=[],
                                        id="click-hide-switch",
                                        switch=True,
                                    ),
                                    dbc.Tooltip(
                                        "When this is enabled, you can click a scatter \
                                            on the graph to toggle its hidden/visible state",
                                        target="click-hide-switch",
                                        placement="top",
                                    ),
                                    dbc.Label("Decay"),
                                    dcc.Slider(
                                        id="decay-slider",
                                        min=0,
                                        max=10,
                                        step=1,
                                        value=0,
                                        marks=None,
                                        tooltip={
                                            "always_visible": False,
                                            "placement": "top",
                                        },
                                    ),
                                    dbc.CardHeader("Filter"),
                                    dbc.CardBody(
                                        [
                                            dbc.Label("Visibility Options"),
                                            html.Div(
                                                dcc.Dropdown(
                                                    id="visible-picker",
                                                    options=["visible", "hidden"],
                                                    value=["visible"],
                                                    multi=True,
                                                ),
                                                className=THEME,
                                            ),
                                            dbc.Tooltip(
                                                "By default, all the data is initially labeled as 'visible.' \
                                                    You can change the label of the data to 'hidden' using this tool.",
                                                target="visible-picker",
                                                placement="top",
                                            ),
                                            html.Div(
                                                id="dropdown-container", children=[]
                                            ),
                                            html.Div(
                                                id="slider-container", children=[]
                                            ),
                                        ]
                                    ),
                                ]
                            ),
                            style={"overflowY": "scroll", "height": "100vh"},
                        ),
                    ]
                )
            ],
            className="mx-3 my-3 g-0",
        )
    ],
    className="mb-3",
)
