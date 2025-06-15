from dash import dcc
from dash import html

import dash_bootstrap_components as dbc

hist_card = dbc.Card(
    [
        dbc.CardBody(
            [
                dbc.Row(
                    [
                        dbc.Col(dbc.Label("Histogram")),
                        dbc.Col(
                            dbc.Checklist(
                                options=[{"label": "Enable", "value": True}],
                                value=[],
                                id="histogram-switch",
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
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("x"),
                                    dbc.Select(
                                        id="x-picker-histogram",
                                        disabled=False,
                                    ),
                                ]
                            )
                        ),
                        dbc.Tooltip(
                            "Select x axis",
                            target="x-picker-histogram",
                            placement="top",
                        ),
                        dbc.Col(
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("y"),
                                    dbc.Select(
                                        id="y-histogram",
                                        options=[
                                            {
                                                "label": "Probability",
                                                "value": "probability",
                                            },
                                            {"label": "Density", "value": "density"},
                                        ],
                                        value="density",
                                        disabled=False,
                                    ),
                                ]
                            )
                        ),
                        dbc.Tooltip(
                            "Select y axis",
                            target="y-histogram",
                            placement="top",
                        ),
                        dbc.Col(
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("c"),
                                    dbc.Select(
                                        id="c-picker-histogram",
                                        disabled=False,
                                    ),
                                ]
                            )
                        ),
                        dbc.Tooltip(
                            "Select color axis",
                            target="c-picker-histogram",
                            placement="top",
                        ),
                    ]
                ),
                dcc.Loading(
                    id="loading_histogram",
                    children=[
                        dbc.Collapse(
                            html.Div(
                                [
                                    dcc.Graph(
                                        id="histogram",
                                        config={"displaylogo": False},
                                        figure={
                                            "data": [{"type": "histogram", "x": []}]
                                        },
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                dbc.Button(
                                                    html.I(
                                                        className="bi bi-camera-fill"
                                                    ),
                                                    id="export-histogram",
                                                    n_clicks=0,
                                                    style={"float": "right"},
                                                )
                                            ),
                                        ]
                                    ),
                                    dbc.Tooltip(
                                        "Export the current figure",
                                        target="export-histogram",
                                        placement="top",
                                    ),
                                ]
                            ),
                            is_open=False,
                            id="collapse-hist",
                        )
                    ],
                    type="default",
                ),
            ]
        )
    ],
    className="shadow-sm",
)
