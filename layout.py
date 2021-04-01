import dash_core_components as dcc
import dash_html_components as html

import dash_bootstrap_components as dbc

import dash_daq as daq

import plotly.io as pio

import uuid

colorscales = ['Blackbody',
               'Bluered',
               'Blues',
               'Earth',
               'Electric',
               'Greens',
               'Greys',
               'Hot',
               'Jet',
               'Picnic',
               'Portland',
               'Rainbow',
               'RdBu',
               'Reds',
               'Viridis',
               'YlGnBu',
               'YlOrRd']


def get_app_layout(app):
    return dbc.Container([
        dbc.Row([
            dcc.Store(id='config'),
            dcc.Store(id='keys-dict'),
            dcc.Store(id='num-key-list'),
            dcc.Store(id='cat-key-list'),
            dcc.Store(id='selected-data-left'),
            dcc.Store(id='selected-data-right'),
            dcc.Store(id='session-id', data=str(uuid.uuid4())),
            dcc.Store(id='frame-value'),
            html.Div(id='filter-trigger', children=0,
                     style={'display': 'none'}),
            html.Div(id='left-hide-trigger', children=0,
                        style={'display': 'none'}),
            html.Div(id='trigger', style={'display': 'none'}),
            html.Div(id='dummy', style={'display': 'none'}),
            html.Div(id='hidden-scatter2d-left',
                     style={'display': 'none'}),
            html.Div(id='hidden-scatter2d-right',
                     style={'display': 'none'}),
            html.Div(id='hidden-histogram',
                        style={'display': 'none'}),
            html.Div(id='hidden-heatmap',
                     style={'display': 'none'})]),
        dbc.Jumbotron([
            dbc.Row([
                html.Img(
                    src=app.get_asset_url('sensorview_logo.svg'),
                    id='sensorview-image',
                    style={
                        'height': '100px',
                        'width': 'auto',
                    },
                ),
                html.H1('SensorView',),
            ], align="end"),
            html.Hr(className="my-2"),
            html.P('Sensor Data Visualization'),
        ]),

        dbc.Row([
            dbc.Col(
                dbc.CardGroup([
                    dbc.Card([
                        dbc.CardHeader("Test Case"),
                        dbc.CardBody([
                            dbc.Row([
                                dbc.Col(dcc.Dropdown(
                                    id='test-case',
                                    clearable=False,
                                )),
                                dbc.Col(dbc.Button(
                                    'Refresh',
                                    id='refresh-case',
                                    color="primary",
                                    className="mr-1",
                                    n_clicks=0,
                                    style={
                                        "float": "right"
                                    }), width=2)
                            ]),
                        ])], color="primary", outline=True),
                    dbc.Card([
                        dbc.CardHeader("Data File"),
                        dbc.CardBody([
                            dcc.Dropdown(
                                id='data-file',
                                clearable=False,
                            ),
                        ])
                    ], color="primary", outline=True)])
            )], className="mb-3"),

        dbc.Row([dbc.Col(dbc.Card([
            dbc.CardHeader("Control"),
            dbc.CardBody([
                dbc.FormGroup(
                    [
                        dbc.Checklist(
                            options=[
                                {"label": "Overlay all frames",
                                 "value": True},
                            ],
                            value=[],
                            id="overlay-switch",
                            switch=True,
                        ),
                        dbc.Checklist(
                            options=[
                                {"label": "Click to change visibility",
                                 "value": True},
                            ],
                            value=[],
                            id="visible-switch",
                            switch=True,
                        ),
                    ]
                ),

                dbc.FormGroup(
                    [
                        dbc.Label("Visibility options"),
                        dbc.Checklist(
                            options=[
                                {"label": "Show visible", "value": "visible"},
                                {"label": "Show hidden", "value": "hidden"},
                            ],
                            value=["visible"],
                            id="vis-picker",
                        ),
                    ]
                ),
            ]),
            dbc.CardHeader("Filter"),
            dbc.CardBody([
                html.Div(id='dropdown-container', children=[]),
                html.Div(id='slider-container', children=[]),
            ])
        ], color="info", outline=True), width=3),
            dbc.Col(
            dbc.Card([
                dbc.CardHeader("3D View"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col(dcc.Dropdown(
                            id='color-picker-3d',
                            clearable=False,
                        ), width=2),
                        dbc.Col(dcc.Dropdown(
                            id='colormap-3d',
                            options=[{"value": x, "label": x}
                                     for x in colorscales],
                            value='Jet',
                            clearable=False,
                        ), width=2)
                    ], justify="end"),

                    dcc.Graph(
                        id='scatter3d',
                        config={
                            'displaylogo': False,
                            'modeBarButtonsToRemove': [
                                'resetCameraDefault3d',
                                'resetCameraLastSave3d'],
                        },
                        figure={
                            'data': [{'mode': 'markers',
                                      'type': 'scatter3d',
                                      'x': [],
                                      'y': [],
                                      'z': []}
                                     ],
                            'layout': {'template': pio.templates['plotly'],
                                       'height': 650,
                                       'uirevision': 'no_change'
                                       }
                        },
                    ),
                    dbc.Row([
                        dbc.Col(
                            dbc.ButtonGroup(
                                [dbc.Button(
                                    '<<',
                                    id='left-frame',
                                    n_clicks=0),
                                    dbc.Button(
                                    '>>',
                                    id='right-frame',
                                    n_clicks=0)
                                 ]), width=1),
                        dbc.Col(
                            dcc.Slider(
                                id='slider-frame',
                                step=1,
                                value=0,
                                updatemode='drag'
                            )
                        )
                    ]),
                    html.Div([
                        dbc.Button(
                            'Export',
                            id='export-scatter3d',
                            n_clicks=0,
                            style={
                                "float": "right"
                            }),
                        html.Div(id='hidden-scatter3d',
                                 style={'display': 'none'}),
                    ]),
                ])], color="success", outline=True), width=9
        )], className="mb-3"),

        dbc.Row([
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col(html.H6('2D View',
                                            className="card-title")),
                            dbc.Col(daq.BooleanSwitch(
                                id='left-switch',
                                on=False,
                                style={
                                    "float": "right"
                                }
                            ))
                        ]),

                        dbc.Row([
                            dbc.Col(html.Label('x-axis')),
                            dbc.Col(html.Label('y-axis')),
                            dbc.Col(html.Label('color')),
                            dbc.Col(html.Label('colormap')),
                        ]),

                        dbc.Row([
                            dbc.Col(dcc.Dropdown(
                                id='x-scatter2d-left',
                                disabled=True,
                                clearable=False,
                            )),
                            dbc.Col(dcc.Dropdown(
                                id='y-scatter2d-left',
                                disabled=True,
                                clearable=False,
                            )),
                            dbc.Col(dcc.Dropdown(
                                id='color-scatter2d-left',
                                disabled=True,
                                clearable=False,
                            )),
                            dbc.Col(dcc.Dropdown(
                                id='colormap-scatter2d-left',
                                disabled=True,
                                options=[{"value": x, "label": x}
                                         for x in colorscales],
                                value='Jet',
                                clearable=False,
                            )),
                        ]),

                        dcc.Loading(
                            id='loading_left',
                            children=[
                                dcc.Graph(
                                    id='scatter2d-left',
                                    config={
                                        'displaylogo': False
                                    },
                                    figure={
                                        'data': [{
                                            'mode': 'markers',
                                            'type': 'scattergl',
                                            'x': [], 'y': []
                                        }],
                                        'layout': {
                                            'uirevision': 'no_change'
                                        }
                                    },
                                ),
                                dbc.Row([
                                    dbc.Col(dbc.Button(
                                            'Hide/Unhide',
                                            id='hide-left',
                                            n_clicks=0)),
                                    dbc.Col(dbc.Button(
                                            'Export',
                                            id='export-scatter2d-left',
                                            n_clicks=0,
                                            style={
                                                "float": "right"
                                            })),
                                ]),
                            ],
                            type='default',
                        ),
                    ]))),

            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col(
                                html.H6('2D View', className="card-title")),
                            dbc.Col(
                                daq.BooleanSwitch(
                                    id='right-switch',
                                    on=False,
                                    style={
                                        "float": "right"
                                    }
                                ))]),

                        dbc.Row([
                            dbc.Col(html.Label('x-axis')),
                            dbc.Col(html.Label('y-axis')),
                            dbc.Col(html.Label('color')),
                            dbc.Col(html.Label('colormap')),
                        ]),

                        dbc.Row([
                            dbc.Col(dcc.Dropdown(
                                id='x-scatter2d-right',
                                disabled=True,
                                clearable=False,
                            )),
                            dbc.Col(dcc.Dropdown(
                                id='y-scatter2d-right',
                                disabled=True,
                                clearable=False,
                            )),
                            dbc.Col(dcc.Dropdown(
                                id='color-scatter2d-right',
                                disabled=True,
                                clearable=False,
                            )),
                            dbc.Col(dcc.Dropdown(
                                id='colormap-scatter2d-right',
                                disabled=True,
                                options=[{"value": x, "label": x}
                                         for x in colorscales],
                                value='Jet',
                                clearable=False,
                            )),
                        ]),

                        dcc.Loading(
                            id='loading_right',
                            children=[
                                dcc.Graph(
                                    id='scatter2d-right',
                                    config={
                                        'displaylogo': False
                                    },
                                    figure={
                                        'data': [{
                                            'mode': 'markers',
                                            'type': 'scattergl',
                                            'x': [], 'y': []
                                        }],
                                        'layout': {
                                            'uirevision': 'no_change'
                                        }
                                    },
                                ),
                                dbc.Row([
                                    dbc.Col(dbc.Button(
                                        'Export',
                                        id='export-scatter2d-right',
                                        n_clicks=0,
                                        style={
                                            "float": "right"
                                        }))
                                ]),
                            ],
                            type='default',
                        ),
                    ])),
            )
        ], className="mb-3"),

        dbc.Row([
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody([
                            dbc.Row([
                                dbc.Col(
                                    html.H6('Histogram',
                                            className="card-title")),
                                dbc.Col(
                                    daq.BooleanSwitch(
                                        id='histogram-switch',
                                        on=False,
                                        style={
                                            "float": "right"
                                        }
                                    ))]),

                            dbc.Row([
                                    dbc.Col(html.Label('x-axis')),
                                    dbc.Col(html.Label('y-axis')),
                                    ]),

                            dbc.Row([
                                dbc.Col(dcc.Dropdown(
                                    id='x-histogram',
                                    disabled=True,
                                    clearable=False,
                                )),
                                dbc.Col(dcc.Dropdown(
                                    id='y-histogram',
                                    options=[{
                                        'label': 'Probability',
                                        'value': 'probability'
                                    },
                                        {
                                        'label': 'Density',
                                        'value': 'density'
                                    },
                                    ],
                                    value='density',
                                    disabled=True,
                                    clearable=False,
                                )),
                            ]),

                            dcc.Loading(
                                id='loading_histogram',
                                children=[
                                    dcc.Graph(
                                        id='histogram',
                                        config={
                                            'displaylogo': False
                                        },
                                        figure={
                                            'data': [{'type': 'histogram',
                                                      'x': []}
                                                     ],
                                            'layout': {
                                                'uirevision': 'no_change'
                                            }
                                        },
                                    ),
                                    dbc.Row([
                                        dbc.Col(
                                            dbc.Button(
                                                'Export',
                                                id='export-histogram',
                                                n_clicks=0,
                                                style={
                                                    "float": "right"
                                                })),
                                    ]),
                                ],
                                type='default',
                            ),
                        ]))),

                dbc.Col(
                    dbc.Card(
                        dbc.CardBody([
                            dbc.Row([
                                dbc.Col(
                                    html.H6('Heatmap',
                                            className="card-title")),
                                dbc.Col(
                                    daq.BooleanSwitch(
                                        id='heat-switch',
                                        on=False,
                                        style={
                                            "float": "right"
                                        }
                                    ))]),

                            dbc.Row([
                                    dbc.Col(html.Label('x-axis')),
                                    dbc.Col(html.Label('y-axis'))
                                    ]),

                            dbc.Row([
                                dbc.Col(dcc.Dropdown(
                                    id='x-heatmap',
                                    disabled=True,
                                    clearable=False,
                                )),
                                dbc.Col(dcc.Dropdown(
                                    id='y-heatmap',
                                    disabled=True,
                                    clearable=False,
                                ))
                            ]),

                            dcc.Loading(
                                id='loading_heat',
                                children=[
                                    dcc.Graph(
                                        id='heatmap',
                                        config={
                                            'displaylogo': False
                                        },
                                        figure={
                                            'data': [{'type': 'histogram2dcontour',
                                                      'x': []}
                                                     ],
                                            'layout': {
                                                'uirevision': 'no_change'
                                            }
                                        },
                                    ),
                                    dbc.Row([
                                        dbc.Col(
                                            dbc.Button(
                                                'Export',
                                                id='export-heatmap',
                                                n_clicks=0,
                                                style={
                                                    "float": "right"
                                                })),
                                    ]),
                                ],
                                type='default',
                            ),
                        ]))),
                ], className="mb-3")
    ], fluid=True, style={'background-color': '#ECEFF1'})
