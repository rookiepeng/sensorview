from dash import dcc
from dash import html

import dash_bootstrap_components as dbc

from app_config import THEME

parallel_card = dbc.Card(
    [
        dbc.CardBody(
            [
                dbc.Row(
                    [
                        dbc.Col(dbc.Label("Parallel Categories")),
                        dbc.Col(
                            dbc.Checklist(
                                options=[{"label": "Enable", "value": True}],
                                value=[],
                                id="parallel-switch",
                                switch=True,
                                style={"float": "right"},
                            )
                        ),
                    ]
                ),
                html.Hr(),
                dbc.Row(
                    [
                        dbc.Col(
                            html.Div(
                                dcc.Dropdown(id="dim-picker-parallel", multi=True),
                                className=THEME,
                            ),
                        ),
                        dbc.Tooltip(
                            "Dimensions",
                            target="dim-picker-parallel",
                            placement="top",
                        ),
                        dbc.Col(
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("c"),
                                    dbc.Select(
                                        id="c-picker-parallel",
                                        disabled=False,
                                    ),
                                ]
                            )
                        ),
                        dbc.Tooltip(
                            "Select color axis",
                            target="c-picker-parallel",
                            placement="top",
                        ),
                    ]
                ),
                dcc.Loading(
                    id="loading_parallel",
                    children=[
                        dbc.Collapse(
                            html.Div(
                                [
                                    dcc.Graph(
                                        id="parallel", config={"displaylogo": False}
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                dbc.Button(
                                                    html.I(
                                                        className="bi bi-camera-fill"
                                                    ),
                                                    id="export-parallel",
                                                    n_clicks=0,
                                                    style={"float": "right"},
                                                )
                                            ),
                                        ]
                                    ),
                                    dbc.Tooltip(
                                        "Export the current figure",
                                        target="export-parallel",
                                        placement="top",
                                    ),
                                ]
                            ),
                            is_open=False,
                            id="collapse-parallel",
                        )
                    ],
                    type="default",
                ),
            ]
        )
    ],
    className="shadow-sm",
)
