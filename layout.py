import dash_core_components as dcc
import dash_html_components as html

import dash_bootstrap_components as dbc

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


testcase_card = dbc.Card([
    dbc.CardHeader("Test Case"),
    dbc.CardBody([
        dbc.Row([
            dbc.Col(dbc.Select(
                id='test-case',
            )),
            dbc.Col(dbc.Button(
                'Refresh',
                id='refresh-case',
                color="success",
                className="mr-1",
                n_clicks=0,
                style={
                    "float": "right"
                }), width=2)
        ]),
    ])], color="primary", inverse=True)

datafile_card = dbc.Card([
    dbc.CardHeader("Data File"),
    dbc.CardBody([
        dbc.Select(
            id='data-file',
        ),
    ])
], color="primary", inverse=True)


filter_card = dbc.Card([
    dbc.CardHeader("Control"),
    dbc.CardBody([
        dbc.FormGroup(
            [
                dbc.Checklist(
                    options=[
                        {"label": "Add outline to scatters",
                         "value": True},
                    ],
                    value=[],
                    id="outline-switch",
                    switch=True,
                ),
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
    ], style={"overflow": "scroll", "height": "700px"})
], color="info", outline=True)

view3d_card = dbc.Card([
    dbc.CardHeader("3D View"),
    dbc.CardBody([
        dbc.Row([
            dbc.Col(dbc.Select(
                id='color-picker-3d',
            ), width=2),
            dbc.Col(dbc.Select(
                id='colormap-3d',
                options=[{"value": x, "label": x}
                         for x in colorscales],
                value='Portland',
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
                    updatemode='drag',
                    tooltip={'always_visible': True,
                             'placement': 'bottom'}
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
    ])], color="success", outline=True)


left2d_card = dbc.Card([
    dbc.CardHeader(
        dbc.Row([
            dbc.Col(
                dbc.Label('2D View')),
            dbc.Col(
                dbc.Checklist(
                    options=[
                        {"label": "Enable",
                         "value": True},
                    ],
                    value=[],
                    id="left-switch",
                    switch=True,
                    style={
                        "float": "right"
                    }
                )
            )]),
    ),
    dbc.CardBody([
        dbc.Row([
            dbc.Col(dbc.Label('x-axis')),
            dbc.Col(dbc.Label('y-axis')),
            dbc.Col(dbc.Label('color')),
            dbc.Col(dbc.Label('colormap')),
        ]),

        dbc.Row([
            dbc.Col(dbc.Select(
                id='x-scatter2d-left',
                disabled=True,
                # clearable=False,
            )),
            dbc.Col(dbc.Select(
                id='y-scatter2d-left',
                disabled=True,
                # clearable=False,
            )),
            dbc.Col(dbc.Select(
                id='color-scatter2d-left',
                disabled=True,
                # clearable=False,
            )),
            dbc.Col(dbc.Select(
                id='colormap-scatter2d-left',
                disabled=True,
                options=[{"value": x, "label": x}
                         for x in colorscales],
                value='Portland',
                # clearable=False,
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
    ])
])

right2d_card = dbc.Card([
    dbc.CardHeader(
        dbc.Row([
            dbc.Col(
                dbc.Label('2D View')),
            dbc.Col(
                dbc.Checklist(
                    options=[
                        {"label": "Enable",
                         "value": True},
                    ],
                    value=[],
                    id="right-switch",
                    switch=True,
                    style={
                        "float": "right"
                    }
                )
            )]),
    ),
    dbc.CardBody([
        dbc.Row([
            dbc.Col(html.Label('x-axis')),
            dbc.Col(html.Label('y-axis')),
            dbc.Col(html.Label('color')),
            dbc.Col(html.Label('colormap')),
        ]),

        dbc.Row([
            dbc.Col(dbc.Select(
                id='x-scatter2d-right',
                disabled=True,
                # clearable=False,
            )),
            dbc.Col(dbc.Select(
                id='y-scatter2d-right',
                disabled=True,
                # clearable=False,
            )),
            dbc.Col(dbc.Select(
                id='color-scatter2d-right',
                disabled=True,
                # clearable=False,
            )),
            dbc.Col(dbc.Select(
                id='colormap-scatter2d-right',
                disabled=True,
                options=[{"value": x, "label": x}
                         for x in colorscales],
                value='Portland',
                # clearable=False,
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
    ])])


hist_card = dbc.Card([
    dbc.CardHeader(
        dbc.Row([
            dbc.Col(
                dbc.Label('Histogram')),
            dbc.Col(
                dbc.Checklist(
                    options=[
                        {"label": "Enable",
                         "value": True},
                    ],
                    value=[],
                    id="histogram-switch",
                    switch=True,
                    style={
                        "float": "right"
                    }
                )
            )]),
    ),
    dbc.CardBody([
        dbc.Row([
            dbc.Col(html.Label('x-axis')),
            dbc.Col(html.Label('y-axis')),
        ]),

        dbc.Row([
            dbc.Col(dbc.Select(
                id='x-histogram',
                disabled=True,
                # clearable=False,
            )),
            dbc.Col(dbc.Select(
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
                # clearable=False,
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
    ])])


heatmap_card = dbc.Card([
    dbc.CardHeader(
        dbc.Row([
            dbc.Col(
                dbc.Label('Heatmap')),
            dbc.Col(
                dbc.Checklist(
                    options=[
                        {"label": "Enable",
                         "value": True},
                    ],
                    value=[],
                    id="heat-switch",
                    switch=True,
                    style={
                        "float": "right"
                    }
                )
            )]),
    ),
    dbc.CardBody([
        dbc.Row([
            dbc.Col(html.Label('x-axis')),
            dbc.Col(html.Label('y-axis'))
        ]),

        dbc.Row([
            dbc.Col(dbc.Select(
                id='x-heatmap',
                disabled=True,
                # clearable=False,
            )),
            dbc.Col(dbc.Select(
                id='y-heatmap',
                disabled=True,
                # clearable=False,
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
    ])])


def get_app_layout(app):
    return dbc.Container([
        dcc.Store(id='config'),
        dcc.Store(id='keys-dict'),
        dcc.Store(id='num-key-list'),
        dcc.Store(id='cat-key-list'),
        dcc.Store(id='selected-data-left'),
        dcc.Store(id='selected-data-right'),
        dcc.Store(id='session-id', data=str(uuid.uuid4())),
        dcc.Store(id='filter-trigger', data=0),
        dcc.Store(id='left-hide-trigger', data=0),
        dcc.Store(id='dummy-export-scatter2d-left'),
        dcc.Store(id='dummy-export-scatter2d-right'),
        dcc.Store(id='dummy-export-histogram'),
        dcc.Store(id='dummy-export-heatmap'),

        dbc.Row([
            dbc.Col(
                dbc.CardGroup([
                    testcase_card,
                    datafile_card
                ])
            )], className="mb-3"),

        dbc.Row([
            dbc.Col(filter_card, width=3),
            dbc.Col(view3d_card, width=9)
        ], className="mb-3"),

        dbc.Row([
            dbc.Col(left2d_card, width=6),
            dbc.Col(right2d_card, width=6)
        ], className="mb-3"),

        dbc.Row([
                dbc.Col(hist_card, width=6),
                dbc.Col(heatmap_card, width=6),
                ], className="mb-3")
    ], fluid=True, style={'background-color': '#f9f8fc'})
