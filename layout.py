"""

    Copyright (C) 2019 - PRESENT  Zhengyu Peng
    E-mail: zpeng.me@gmail.com
    Website: https://zpeng.me

    `                      `
    -:.                  -#:
    -//:.              -###:
    -////:.          -#####:
    -/:.://:.      -###++##:
    ..   `://:-  -###+. :##:
           `:/+####+.   :##:
    .::::::::/+###.     :##:
    .////-----+##:    `:###:
     `-//:.   :##:  `:###/.
       `-//:. :##:`:###/.
         `-//:+######/.
           `-/+####/.
             `+##+.
              :##:
              :##:
              :##:
              :##:
              :##:
               .+:

"""

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
    dbc.CardHeader('Test Case'),
    dbc.CardBody([
        dbc.Row([
            dbc.Col(dbc.Select(
                id='case-picker',
            )),
            dbc.Col(dbc.Button(
                'Refresh',
                id='refresh-button',
                color='success',
                className='mr-1',
                n_clicks=0,
                style={
                    'float': 'right'
                }), width=2)
        ]),
    ])], color='primary', inverse=True)

datafile_card = dbc.Card([
    dbc.CardHeader('Data File'),
    dbc.CardBody([
        dbc.Select(
            id='file-picker',
        ),
    ])
], color='primary', inverse=True)


filter_card = dbc.Card([
    dbc.CardHeader('Control'),
    dbc.CardBody([
        dbc.FormGroup(
            [
                dbc.Checklist(
                    options=[
                        {'label': 'Add outline to scatters',
                         'value': True},
                    ],
                    value=[],
                    id='outline-switch',
                    switch=True,
                ),
                dbc.Checklist(
                    options=[
                        {'label': 'Overlay all frames',
                         'value': True},
                    ],
                    value=[],
                    id='overlay-switch',
                    switch=True,
                ),
                dbc.Checklist(
                    options=[
                        {'label': 'Click to change visibility',
                         'value': True},
                    ],
                    value=[],
                    id='click-hide-switch',
                    switch=True,
                ),
            ]
        ),

        dbc.FormGroup(
            [
                dbc.Label('Visibility options'),
                dbc.Checklist(
                    options=[
                        {'label': 'Show visible',
                         'value': 'visible'},
                        {'label': 'Show hidden',
                         'value': 'hidden'},
                    ],
                    value=['visible'],
                    id='visible-picker',
                ),
            ]
        ),
    ]),
    dbc.CardHeader('Filter'),
    dbc.CardBody([
        html.Div(id='dropdown-container', children=[]),
        html.Div(id='slider-container', children=[]),
    ], style={'overflow': 'scroll', 'height': '600px'})
], color='info', outline=True)

view3d_card = dbc.Card([
    dbc.CardHeader('3D View'),
    dbc.CardBody([
        dbc.Row([
            dbc.Col(dbc.Select(
                id='c-picker-3d',
            ), width=2),
            dbc.Col(dbc.Select(
                id='colormap-3d',
                options=[{'value': x,
                          'label': x}
                         for x in colorscales],
                value='Portland',
            ), width=2)
        ], justify='end'),

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
            dcc.Interval(
                id='buffer-interval',
                interval=2000,  # in milliseconds
                disabled=False,
                n_intervals=0
            ),
            dbc.Col(
                dbc.Progress(id='buffer',
                             value=0,
                             color='success',
                             style={'height': '1px',
                                    'margin-top': 0,
                                    'margin-bottom': 5,
                                    'margin-left': 25,
                                    'margin-right': 25},
                             className='mb-3'), width=12),
            dbc.Col(dcc.Slider(
                id='slider-frame',
                step=1,
                value=0,
                updatemode='drag',
                tooltip={'always_visible': False,
                         'placement': 'top'}
            ), width=12),
        ], style={'margin-top': 0, 'margin-bottom': -15}),
        dbc.Row([
            dcc.Interval(
                id='interval-component',
                interval=2*100,  # in milliseconds
                disabled=True,
                n_intervals=0
            ),
            dbc.Col(
                dbc.ButtonGroup(
                    [dbc.Button(
                        '<<',
                        id='previous-button',
                        color='dark',
                        n_clicks=0),
                     dbc.Button(
                        '▷',
                        id='play-button',
                        color='primary',
                        n_clicks=0),
                     dbc.Button(
                        '◼',
                        id='stop-button',
                        color='danger',
                        n_clicks=0),
                     dbc.Button(
                        '>>',
                        id='next-button',
                        color='dark',
                        n_clicks=0)
                     ]), width=2),
        ], justify='center'),
        html.Div([
            dbc.DropdownMenu(
                [dbc.DropdownMenuItem(
                    'Export all frames as an HTML video',
                    id='export-scatter3d',
                    n_clicks=0
                )],
                label='Export',
                right=True,
                style={'float': 'right'}
            ),
            html.Div(id='hidden-scatter3d',
                     style={'display': 'none'}),
        ]),
    ])], color='success', outline=True)


left2d_card = dbc.Card([
    dbc.CardHeader(
        dbc.Row([
            dbc.Col(
                dbc.Label('2D View')),
            dbc.Col(
                dbc.Checklist(
                    options=[
                        {'label': 'Enable',
                         'value': True},
                    ],
                    value=[],
                    id='left-switch',
                    switch=True,
                    style={
                        'float': 'right'
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
                id='x-picker-2d-left',
                disabled=True,
            )),
            dbc.Col(dbc.Select(
                id='y-picker-2d-left',
                disabled=True,
            )),
            dbc.Col(dbc.Select(
                id='c-picker-2d-left',
                disabled=True,
            )),
            dbc.Col(dbc.Select(
                id='colormap-scatter2d-left',
                disabled=True,
                options=[{'value': x,
                          'label': x}
                         for x in colorscales],
                value='Portland',
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
                        style={'float': 'right'})),
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
                        {'label': 'Enable',
                         'value': True},
                    ],
                    value=[],
                    id='right-switch',
                    switch=True,
                    style={'float': 'right'}
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
                id='x-picker-2d-right',
                disabled=True,
            )),
            dbc.Col(dbc.Select(
                id='y-picker-2d-right',
                disabled=True,
            )),
            dbc.Col(dbc.Select(
                id='c-picker-2d-right',
                disabled=True,
            )),
            dbc.Col(dbc.Select(
                id='colormap-scatter2d-right',
                disabled=True,
                options=[{'value': x, 'label': x}
                         for x in colorscales],
                value='Portland',
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
                            'x': [],
                            'y': []
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
                        style={'float': 'right'}))
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
                        {'label': 'Enable',
                         'value': True},
                    ],
                    value=[],
                    id='histogram-switch',
                    switch=True,
                    style={'float': 'right'}
                )
            )]),
    ),
    dbc.CardBody([
        dbc.Row([
            dbc.Col(html.Label('x-axis')),
            dbc.Col(html.Label('y-axis')),
            dbc.Col(html.Label('color')),
        ]),

        dbc.Row([
            dbc.Col(dbc.Select(
                id='x-picker-histogram',
                disabled=True,
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
            )),
            dbc.Col(dbc.Select(
                id='c-picker-histogram',
                disabled=True,
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
                            style={'float': 'right'})),
                ]),
            ],
            type='default',
        ),
    ])])


violin_card = dbc.Card([
    dbc.CardHeader(
        dbc.Row([
            dbc.Col(
                dbc.Label('Violin')),
            dbc.Col(
                dbc.Checklist(
                    options=[
                        {'label': 'Enable',
                         'value': True},
                    ],
                    value=[],
                    id='violin-switch',
                    switch=True,
                    style={'float': 'right'}
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
                id='x-picker-violin',
                disabled=True,
            )),
            dbc.Col(dbc.Select(
                id='y-picker-violin',
                disabled=True,
            )),
            dbc.Col(dbc.Select(
                id='c-picker-violin',
                disabled=True,
            )),
        ]),

        dcc.Loading(
            id='loading_violin',
            children=[
                dcc.Graph(
                    id='violin',
                    config={
                        'displaylogo': False
                    }
                ),
                dbc.Row([
                    dbc.Col(
                        dbc.Button(
                            'Export',
                            id='export-violin',
                            n_clicks=0,
                            style={'float': 'right'})),
                ]),
            ],
            type='default',
        ),
    ])])


parallel_card = dbc.Card([
    dbc.CardHeader(
        dbc.Row([
            dbc.Col(
                dbc.Label('Parallel Categories')),
            dbc.Col(
                dbc.Checklist(
                    options=[
                        {'label': 'Enable',
                         'value': True},
                    ],
                    value=[],
                    id='parallel-switch',
                    switch=True,
                    style={'float': 'right'}
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
                id='x-picker-parallel',
                disabled=True,
            )),
            dbc.Col(dbc.Select(
                id='y-parallel',
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
            )),
        ]),

        dcc.Loading(
            id='loading_parallel',
            children=[
                dcc.Graph(
                    id='parallel',
                    config={
                        'displaylogo': False
                    }
                ),
                dbc.Row([
                    dbc.Col(
                        dbc.Button(
                            'Export',
                            id='export-parallel',
                            n_clicks=0,
                            style={'float': 'right'})),
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
                        {'label': 'Enable',
                         'value': True},
                    ],
                    value=[],
                    id='heat-switch',
                    switch=True,
                    style={'float': 'right'}
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
                id='x-picker-heatmap',
                disabled=True,
            )),
            dbc.Col(dbc.Select(
                id='y-picker-heatmap',
                disabled=True,
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
                            style={'float': 'right'})),
                ]),
            ],
            type='default',
        ),
    ])])


scatter_tab = html.Div([
    dbc.Row([
            dbc.Col(filter_card, width=3),
            dbc.Col(view3d_card, width=9)
            ], className='mb-3', align='start'),

    dbc.Row([
            dbc.Col(left2d_card, width=6),
            dbc.Col(right2d_card, width=6)
            ], className='mb-3'),
])

statistical_tab = html.Div([
    dbc.Row([
        dbc.Col(hist_card, width=6),
        dbc.Col(violin_card, width=6),
    ], className='mb-3'),
    dbc.Row([
        dbc.Col(parallel_card, width=6),
        dbc.Col(heatmap_card, width=6),
    ], className='mb-3')
])

tabs = dbc.Tabs(
    [
        dbc.Tab(scatter_tab, label="Scatter"),
        dbc.Tab(statistical_tab, label="Statistical"),
    ]
)


def get_app_layout(app):
    return dbc.Container([
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
            )], className='mb-3'),

        tabs,

        dcc.Markdown(
            'Designed and developed by **Zhengyu Peng** \
                | Powered by [Dash](https://plotly.com/dash/),\
                [Redis](https://redis.io/),\
                [Celery](https://docs.celeryproject.org/en/stable/),\
                [Docker](https://www.docker.com/)'),
    ], fluid=True, style={'background-color': '#f9f8fc'})
