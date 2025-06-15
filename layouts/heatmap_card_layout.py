from dash import dcc
from dash import html

import dash_bootstrap_components as dbc


heatmap_card = dbc.Card(
    [
        dbc.CardBody(
            [
                dbc.Row(
                    [
                        dbc.Col(dbc.Label("Heatmap")),
                        dbc.Col(
                            dbc.Checklist(
                                options=[{"label": "Enable", "value": True}],
                                value=[],
                                id="heat-switch",
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
                                        id="x-picker-heatmap",
                                        disabled=False,
                                    ),
                                ]
                            )
                        ),
                        dbc.Tooltip(
                            "Select x axis",
                            target="x-picker-heatmap",
                            placement="top",
                        ),
                        dbc.Col(
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("y"),
                                    dbc.Select(
                                        id="y-picker-heatmap",
                                        disabled=False,
                                    ),
                                ]
                            )
                        ),
                        dbc.Tooltip(
                            "Select y axis",
                            target="y-picker-heatmap",
                            placement="top",
                        ),
                    ]
                ),
                dcc.Loading(
                    id="loading_heat",
                    children=[
                        dbc.Collapse(
                            html.Div(
                                [
                                    dcc.Graph(
                                        id="heatmap",
                                        config={"displaylogo": False},
                                        figure={
                                            "data": [
                                                {"type": "histogram2dcontour", "x": []}
                                            ]
                                        },
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                dbc.Button(
                                                    html.I(
                                                        className="bi bi-camera-fill"
                                                    ),
                                                    id="export-heatmap",
                                                    n_clicks=0,
                                                    style={"float": "right"},
                                                )
                                            ),
                                        ]
                                    ),
                                    dbc.Tooltip(
                                        "Export the current figure",
                                        target="export-heatmap",
                                        placement="top",
                                    ),
                                ]
                            ),
                            is_open=False,
                            id="collapse-heatmap",
                        )
                    ],
                    type="default",
                ),
            ]
        )
    ],
    className="shadow-sm",
)
