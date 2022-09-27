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

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc

import plotly.io as pio

import uuid
from maindash import app

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
    dbc.CardHeader(
        dbc.Row([
            dbc.Col(html.H6('Test Cases'), class_name='mt-2'),
            dbc.Col(dbc.Button(
                '↻',
                id='refresh-button',
                color='secondary',
                # className='mr-1',
                n_clicks=0,
                size="sm",
                style={
                    'float': 'right'
                }
            ), width=3, class_name='mt-1')
        ], justify="end"),
    ),
    dbc.CardBody([
        dbc.Row([
            dbc.Col(dbc.Select(id='case-picker'), width=3),
            dbc.Col(dbc.Select(id='file-picker'))]),
        dbc.Row([dbc.Button(
            '+',
            id='button-add',
            color='secondary',
            # className='mr-1',
            n_clicks=0,
            size="sm",
        )], class_name='mx-1 my-1'),
        dbc.Row([
            dbc.Col(
                dbc.Collapse(
                    dcc.Dropdown(
                        id='file-add',
                        multi=True,
                    ),
                    id='collapse-add',
                    is_open=False,
                ),
            )
        ])])],
    color='secondary',
    inverse=True,
    className="h-100 shadow-sm")

filter_card = dbc.Card([
    dbc.CardHeader('Control'),
    dbc.CardBody([
        dbc.Row(
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

        dbc.Row(
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

        dbc.Row(
            [
                dbc.Label('Decay'),
                dcc.Slider(
                    id='decay-slider',
                    min=0,
                    max=10,
                    step=1,
                    value=0,
                    marks=None,
                    tooltip={'always_visible': False,
                             'placement': 'top'}
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
            ), width=2),
            dbc.Col(
                dbc.Checklist(
                    options=[
                        {'label': 'Dark mode',
                         'value': True},
                    ],
                    value=[True],
                    id='darkmode-switch',
                    switch=True,
                    style={
                        'float': 'right'
                    }
                ), width=8),
        ], justify='end', style={'margin-bottom': 10}),

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
                             color='info',
                             style={'height': '2px',
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
                marks=None,
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
                        '▢',
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
                ),
                    dbc.DropdownMenuItem(
                    'Save filtered data',
                    id='export-data',
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
                    style={'float': 'right'}
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
                disabled=False,
            )),
            dbc.Col(dbc.Select(
                id='y-picker-2d-left',
                disabled=False,
            )),
            dbc.Col(dbc.Select(
                id='c-picker-2d-left',
                disabled=False,
            )),
            dbc.Col(dbc.Select(
                id='colormap-scatter2d-left',
                disabled=False,
                options=[{'value': x,
                          'label': x}
                         for x in colorscales],
                value='Portland',
            )),
        ], style={'margin-bottom': 10}),

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
                        color='warning',
                        n_clicks=0)),
                    dbc.Col(dbc.Button(
                        'Export',
                        id='export-scatter2d-left',
                        n_clicks=0,
                        style={'float': 'right'})),
                ], style={'margin-top': 10}),
            ],
            type='default',
        ),
    ])], color='danger', outline=True)

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
            dbc.Col(dbc.Label('x-axis')),
            dbc.Col(dbc.Label('y-axis')),
            dbc.Col(dbc.Label('color')),
            dbc.Col(dbc.Label('colormap')),
        ]),

        dbc.Row([
            dbc.Col(dbc.Select(
                id='x-picker-2d-right',
                disabled=False,
            )),
            dbc.Col(dbc.Select(
                id='y-picker-2d-right',
                disabled=False,
            )),
            dbc.Col(dbc.Select(
                id='c-picker-2d-right',
                disabled=False,
            )),
            dbc.Col(dbc.Select(
                id='colormap-scatter2d-right',
                disabled=False,
                options=[{'value': x, 'label': x}
                         for x in colorscales],
                value='Portland',
            )),
        ], style={'margin-bottom': 10}),

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
                ], style={'margin-top': 10}),
            ],
            type='default',
        ),
    ])], color='danger', outline=True)


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
            dbc.Col(dbc.Label('x-axis')),
            dbc.Col(dbc.Label('y-axis')),
            dbc.Col(dbc.Label('color')),
        ]),

        dbc.Row([
            dbc.Col(dbc.Select(
                id='x-picker-histogram',
                disabled=False,
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
                disabled=False,
            )),
            dbc.Col(dbc.Select(
                id='c-picker-histogram',
                disabled=False,
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
                                 ]
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
            dbc.Col(dbc.Label('x-axis')),
            dbc.Col(dbc.Label('y-axis')),
            dbc.Col(dbc.Label('color')),
        ]),

        dbc.Row([
            dbc.Col(dbc.Select(
                id='x-picker-violin',
                disabled=False,
            )),
            dbc.Col(dbc.Select(
                id='y-picker-violin',
                disabled=False,
            )),
            dbc.Col(dbc.Select(
                id='c-picker-violin',
                disabled=False,
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
            dbc.Col(dbc.Label('dimensions')),
            dbc.Col(dbc.Label('color')),
        ]),

        dbc.Row([
            dbc.Col(
                dcc.Dropdown(
                    id='dim-picker-parallel',
                    multi=True
                )),
            dbc.Col(dbc.Select(
                    id='c-picker-parallel',
                    disabled=False,
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
            dbc.Col(dbc.Label('x-axis')),
            dbc.Col(dbc.Label('y-axis'))
        ]),

        dbc.Row([
            dbc.Col(dbc.Select(
                id='x-picker-heatmap',
                disabled=False,
            )),
            dbc.Col(dbc.Select(
                id='y-picker-heatmap',
                disabled=False,
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
                                 ]
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


def get_app_layout():
    return dbc.Container([
        dcc.Store(id='selected-data-left'),
        dcc.Store(id='selected-data-right'),
        dcc.Store(id='session-id', data=str(uuid.uuid4())),
        dcc.Store(id='filter-trigger', data=0),
        dcc.Store(id='left-hide-trigger', data=0),
        dcc.Store(id='file-loaded-trigger', data=0),
        dcc.Store(id='dummy-export-scatter2d-left'),
        dcc.Store(id='dummy-export-scatter2d-right'),
        dcc.Store(id='dummy-export-histogram'),
        dcc.Store(id='dummy-export-violin'),
        dcc.Store(id='dummy-export-parallel'),
        dcc.Store(id='dummy-export-heatmap'),
        dcc.Store(id='dummy-export-data'),

        dbc.Row([
            dbc.Col(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.Div(html.Img(
                                src=app.get_asset_url('sensorview_logo.svg'),
                                id='sensorview-image',
                                style={
                                    'height': '100px',
                                    'width': 'auto',
                                },
                            ), className="text-center"),
                            html.H1(app.title, className="text-center"),
                            # html.Hr(className="my-2"),
                            html.P(
                                'Sensor Data Visualization',
                                className="text-center"
                            ),
                        ],
                    ), color="light",
                    outline=True,
                    className="h-100 shadow-sm"),
                width=3),
            dbc.Col(testcase_card),
        ], className="my-3"),

        dbc.Collapse(
            dbc.Row([
                dbc.Col(
                    dbc.Progress(
                        value=100,
                        color='light',
                        id="loading-progress",
                        animated=False,
                        striped=False,
                        label=''
                    ))]),
            id="collapse",
            is_open=True),

        html.Hr(),
        tabs,
        html.Hr(),

        dcc.Markdown(
            'Designed and developed by **Zhengyu Peng** \
                | Powered by [Dash](https://plotly.com/dash/),\
                [Redis](https://redis.io/),\
                [Celery](https://docs.celeryproject.org/en/stable/)'),
    ], fluid=True, className="dbc_light")
