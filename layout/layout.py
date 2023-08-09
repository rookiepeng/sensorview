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


view3d_card = dbc.Card([
    dbc.CardBody([dbc.Row([
        dbc.Col(dbc.Row([
            dbc.Col(dbc.InputGroup([
                dbc.InputGroupText('Color'),
                dbc.Select(id='c-picker-3d'),
                dbc.Tooltip(
                    'Select color axis',
                    target='c-picker-3d',
                    placement='top',
                ),
            ]), width=3),
            dbc.Col(dbc.InputGroup([
                dbc.InputGroupText('Colormap'),
                dbc.Select(
                    id='colormap-3d',
                    options=[{'value': x,
                              'label': x}
                             for x in colorscales],
                    value='Portland',
                ),
                dbc.Tooltip(
                    'Select colormap',
                    target='colormap-3d',
                    placement='top',
                ),
            ]), width=3
            ),
            dbc.Col(
                dbc.Checklist(
                    options=[
                        {'label': 'Dark mode',
                         'value': True}],
                    value=[True],
                    id='darkmode-switch',
                    switch=True,
                    style={'float': 'right'}
                ), width=6
            ),

            dbc.Col(dcc.Graph(
                id='scatter3d',
                config={'displaylogo': False,
                        'modeBarButtonsToRemove': [
                            'resetCameraDefault3d',
                            'resetCameraLastSave3d']},
                figure={'data': [{'mode': 'markers',
                                  'type': 'scatter3d',
                                  'x': [],
                                  'y': [],
                                  'z': []}],
                        'layout': {'template': pio.templates['plotly'],
                                   'uirevision': 'no_change'}
                        },
                style={'height': '85vh'},
            ), class_name='mt-2'),

            dcc.Interval(
                id='buffer-interval',
                interval=2000,  # in milliseconds
                disabled=False,
                n_intervals=0
            ),
            dbc.Col(
                dbc.Progress(
                    id='buffer',
                    value=0,
                    color='info',
                    style={'height': '2px',
                           'margin-top': 0,
                           'margin-bottom': 5,
                           'margin-left': 25,
                           'margin-right': 25},
                    className='mb-3'
                ), width=12
            ),
            dbc.Tooltip(
                'Progree of buffering on server',
                target='buffer',
                placement='top',
            ),
            dbc.Col(
                dcc.Slider(
                    id='slider-frame',
                    step=1,
                    value=0,
                    updatemode='drag',
                    marks=None,
                    tooltip={'always_visible': False,
                             'placement': 'top'}
                ), width=12
            ),

            dbc.Row([
                dcc.Interval(
                    id='interval-component',
                    interval=2*100,  # in milliseconds
                    disabled=True,
                    n_intervals=0
                ),
                dbc.Col(
                    dbc.ButtonGroup([
                        dbc.Button(
                            html.I(className='bi bi-skip-backward-fill'),
                            id='previous-button',
                            color='dark',
                            n_clicks=0
                        ),
                        dbc.Button(
                            html.I(className='bi bi-play-fill'),
                            id='play-button',
                            color='primary',
                            n_clicks=0
                        ),
                        dbc.Button(
                            html.I(className='bi bi-stop-fill'),
                            id='stop-button',
                            color='danger',
                            n_clicks=0
                        ),
                        dbc.Button(
                            html.I(className='bi bi-skip-forward-fill'),
                            id='next-button',
                            color='dark',
                            n_clicks=0
                        )
                    ]), width=2
                ),
                dbc.Tooltip(
                    'Previous frame',
                    target='previous-button',
                    placement='top',
                ),
                dbc.Tooltip(
                    'Play',
                    target='play-button',
                    placement='top',
                ),
                dbc.Tooltip(
                    'Stop',
                    target='stop-button',
                    placement='top',
                ),
                dbc.Tooltip(
                    'Next frame',
                    target='next-button',
                    placement='top',
                ),
            ], justify='center'
            ),
            html.Div([
                dbc.DropdownMenu([
                    dbc.DropdownMenuItem(
                        'Export all frames as an HTML video',
                        id='export-scatter3d',
                        n_clicks=0
                    ),
                    dbc.DropdownMenuItem(
                        'Save filtered data',
                        id='export-data',
                        n_clicks=0
                    )
                ], label='Export',
                    right=True,
                    style={'float': 'right'}
                ),
                html.Div(
                    id='hidden-scatter3d',
                    style={'display': 'none'}
                ),
            ]),
        ]), width=9, class_name='me-3'),
        dbc.Col(dbc.Row([
            dbc.Checklist(
                options=[
                        {'label': 'Add outline to scatters',
                            'value': True}],
                value=[],
                id='outline-switch',
                switch=True,
            ),
            dbc.Tooltip(
                'Add grey outlines to the scatters',
                target='outline-switch',
                placement='top',
            ),
            dbc.Checklist(
                options=[
                    {'label': 'Overlay all frames',
                     'value': True}],
                value=[],
                id='overlay-switch',
                switch=True,
            ),
            dbc.Tooltip(
                'Overlay all the frames',
                target='overlay-switch',
                placement='top',
            ),
            dbc.Checklist(
                options=[
                    {'label': 'Click to change visibility',
                     'value': True}],
                value=[],
                id='click-hide-switch',
                switch=True,
            ),
            dbc.Tooltip(
                'When this is enabled, you can click a scatter on the graph \
                    to toggle its hidden/visible state',
                target='click-hide-switch',
                placement='top',
            ),

            dbc.Label('Visibility options'),
            dbc.Checklist(
                options=[
                    {'label': 'Show visible',
                     'value': 'visible'},
                    {'label': 'Show hidden',
                     'value': 'hidden'}],
                value=['visible'],
                id='visible-picker',
            ),

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

            dbc.CardHeader('Filter'),
            dbc.CardBody([
                html.Div(id='dropdown-container', children=[]),
                html.Div(id='slider-container', children=[]),
            ], )]), style={'overflow-y': 'scroll', 'height': '110vh'}),
    ])
    ], class_name='mx-3 my-3 g-0'),
], className="mb-3")


left2d_card = dbc.Card([
    dbc.CardBody([
        dbc.Row([
            dbc.Col(
                dbc.Label('2D View')
            ),
            dbc.Col(
                dbc.Checklist(
                    options=[{'label': 'Enable',
                              'value': True}],
                    value=[],
                    id='left-switch',
                    switch=True,
                    style={'float': 'right'}
                )
            )
        ]),

        html.Hr(),

        dcc.Loading(
            id='loading_left',
            children=[
                dbc.Row([
                        dbc.Col(dbc.InputGroup([
                            dbc.InputGroupText('x'),
                            dbc.Select(
                                id='x-picker-2d-left',
                                disabled=False,
                            )
                        ], size='sm')
                        ),
                        dbc.Tooltip(
                            'Select x axis',
                            target='x-picker-2d-left',
                            placement='top',
                        ),
                        dbc.Col(dbc.InputGroup([
                            dbc.InputGroupText('y'),
                            dbc.Select(
                                id='y-picker-2d-left',
                                disabled=False,
                            )
                        ], size='sm')
                        ),
                        dbc.Tooltip(
                            'Select y axis',
                            target='y-picker-2d-left',
                            placement='top',
                        ),
                        dbc.Col(dbc.InputGroup([
                            dbc.InputGroupText('c'),
                            dbc.Select(
                                id='c-picker-2d-left',
                                disabled=False,
                            )
                        ], size='sm')
                        ),
                        dbc.Tooltip(
                            'Select color axis',
                            target='c-picker-2d-left',
                            placement='top',
                        ),
                        dbc.Col(dbc.InputGroup([
                            dbc.InputGroupText('cmap'),
                            dbc.Select(
                                id='colormap-scatter2d-left',
                                disabled=False,
                                options=[{'value': x,
                                          'label': x}
                                         for x in colorscales],
                                value='Portland',
                            )
                        ], size='sm')
                        ),
                        dbc.Tooltip(
                            'Select colormap',
                            target='colormap-scatter2d-left',
                            placement='top',
                        ),
                        ], class_name='g-1 mb-2'),
                dbc.Collapse(
                    html.Div([
                        dcc.Graph(
                            id='scatter2d-left',
                            config={'displaylogo': False},
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
                            dbc.Col(
                                dbc.Button(
                                    'Hide/Unhide',
                                    id='hide-left',
                                    color='warning',
                                    n_clicks=0
                                )
                            ),
                            dbc.Tooltip(
                                'Toggle the hidden/visible states of \
                                    the selected dots',
                                target='hide-left',
                                placement='top',
                            ),
                            dbc.Col(
                                dbc.Button(
                                    'Export',
                                    id='export-scatter2d-left',
                                    n_clicks=0,
                                    style={'float': 'right'}
                                )
                            ),
                        ], style={'margin-top': 10}
                        )
                    ]),
                    is_open=False,
                    id="collapse-left2d"
                ),
            ],
            type='default',
        ),
    ])
], className="shadow-sm")

right2d_card = dbc.Card([
    dbc.CardBody([
        dbc.Row([
            dbc.Col(
                dbc.Label('2D View')
            ),
            dbc.Col(
                dbc.Checklist(
                    options=[{'label': 'Enable',
                              'value': True}],
                    value=[],
                    id='right-switch',
                    switch=True,
                    style={'float': 'right'}
                )
            )
        ]),

        html.Hr(),

        dcc.Loading(
            id='loading_right',
            children=[
                dbc.Row([
                    dbc.Col(dbc.InputGroup([
                        dbc.InputGroupText('x'),
                        dbc.Select(
                            id='x-picker-2d-right',
                            disabled=False,
                        )
                    ], size='sm')
                    ),
                    dbc.Tooltip(
                        'Select x axis',
                        target='x-picker-2d-right',
                        placement='top',
                    ),
                    dbc.Col(dbc.InputGroup([
                        dbc.InputGroupText('y'),
                        dbc.Select(
                            id='y-picker-2d-right',
                            disabled=False,
                        )
                    ], size='sm')
                    ),
                    dbc.Tooltip(
                        'Select y axis',
                        target='y-picker-2d-right',
                        placement='top',
                    ),
                    dbc.Col(dbc.InputGroup([
                        dbc.InputGroupText('c'),
                        dbc.Select(
                            id='c-picker-2d-right',
                            disabled=False,
                        )
                    ], size='sm')
                    ),
                    dbc.Tooltip(
                        'Select color axis',
                        target='c-picker-2d-right',
                        placement='top',
                    ),
                    dbc.Col(dbc.InputGroup([
                        dbc.InputGroupText('cmap'),
                        dbc.Select(
                            id='colormap-scatter2d-right',
                            disabled=False,
                            options=[{'value': x, 'label': x}
                                     for x in colorscales],
                            value='Portland',
                        )
                    ], size='sm')
                    ),
                    dbc.Tooltip(
                        'Select colormap',
                        target='colormap-scatter2d-right',
                        placement='top',
                    ),
                ], class_name='g-1 mb-2'),
                dbc.Collapse(
                    html.Div([
                        dcc.Graph(
                            id='scatter2d-right',
                            config={'displaylogo': False},
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
                            dbc.Col(
                                dbc.Button(
                                    'Export',
                                    id='export-scatter2d-right',
                                    n_clicks=0,
                                    style={'float': 'right'}
                                )
                            )
                        ], style={'margin-top': 10})
                    ]),
                    is_open=False,
                    id="collapse-right2d"
                )
            ],
            type='default',
        ),
    ])
], className="shadow-sm")


hist_card = dbc.Card([
    dbc.CardBody([
        dbc.Row([
            dbc.Col(
                dbc.Label('Histogram')
            ),
            dbc.Col(
                dbc.Checklist(
                    options=[{'label': 'Enable',
                              'value': True}],
                    value=[],
                    id='histogram-switch',
                    switch=True,
                    style={'float': 'right'}
                )
            )
        ]),

        html.Hr(),

        dcc.Loading(
            id='loading_histogram',
            children=[
                dbc.Row([
                    dbc.Col(dbc.InputGroup([
                        dbc.InputGroupText('x'),
                        dbc.Select(
                            id='x-picker-histogram',
                            disabled=False,
                        )
                    ])
                    ),
                    dbc.Tooltip(
                        'Select x axis',
                        target='x-picker-histogram',
                        placement='top',
                    ),
                    dbc.Col(dbc.InputGroup([
                        dbc.InputGroupText('y'),
                        dbc.Select(
                            id='y-histogram',
                            options=[{'label': 'Probability',
                                      'value': 'probability'},
                                     {'label': 'Density',
                                      'value': 'density'}],
                            value='density',
                            disabled=False,
                        )
                    ])
                    ),
                    dbc.Tooltip(
                        'Select y axis',
                        target='y-histogram',
                        placement='top',
                    ),
                    dbc.Col(dbc.InputGroup([
                        dbc.InputGroupText('c'),
                        dbc.Select(
                            id='c-picker-histogram',
                            disabled=False,
                        )
                    ])
                    ),
                    dbc.Tooltip(
                        'Select color axis',
                        target='c-picker-histogram',
                        placement='top',
                    ),
                ]),
                dbc.Collapse(
                    html.Div([
                        dcc.Graph(
                            id='histogram',
                            config={'displaylogo': False},
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
                                    style={'float': 'right'}
                                )
                            ),
                        ]),
                    ]), is_open=False,
                    id="collapse-hist")
            ],
            type='default',
        ),
    ])
], className="shadow-sm")


violin_card = dbc.Card([
    dbc.CardBody([
        dbc.Row([
            dbc.Col(
                dbc.Label('Violin')
            ),
            dbc.Col(
                dbc.Checklist(
                    options=[{'label': 'Enable',
                              'value': True}],
                    value=[],
                    id='violin-switch',
                    switch=True,
                    style={'float': 'right'}
                )
            )
        ]),

        html.Hr(),

        dcc.Loading(
            id='loading_violin',
            children=[
                dbc.Row([
                    dbc.Col(dbc.InputGroup([
                        dbc.InputGroupText('x'),
                        dbc.Select(
                            id='x-picker-violin',
                            disabled=False,
                        )
                    ])
                    ),
                    dbc.Tooltip(
                        'Select x axis',
                        target='x-picker-violin',
                        placement='top',
                    ),
                    dbc.Col(dbc.InputGroup([
                        dbc.InputGroupText('y'),
                        dbc.Select(
                            id='y-picker-violin',
                            disabled=False,
                        )
                    ])
                    ),
                    dbc.Tooltip(
                        'Select y axis',
                        target='y-picker-violin',
                        placement='top',
                    ),
                    dbc.Col(dbc.InputGroup([
                        dbc.InputGroupText('c'),
                        dbc.Select(
                            id='c-picker-violin',
                            disabled=False,
                        )
                    ])
                    ),
                    dbc.Tooltip(
                        'Select color axis',
                        target='c-picker-violin',
                        placement='top',
                    ),
                ]),
                dbc.Collapse(
                    html.Div([
                        dcc.Graph(
                            id='violin',
                            config={'displaylogo': False}
                        ),
                        dbc.Row([
                            dbc.Col(
                                dbc.Button(
                                    'Export',
                                    id='export-violin',
                                    n_clicks=0,
                                    style={'float': 'right'}
                                )
                            ),
                        ])
                    ]), is_open=False,
                    id="collapse-violin"
                )
            ],
            type='default',
        ),
    ])
], className="shadow-sm")


parallel_card = dbc.Card([
    dbc.CardBody([
        dbc.Row([
            dbc.Col(
                dbc.Label('Parallel Categories')
            ),
            dbc.Col(
                dbc.Checklist(
                    options=[{'label': 'Enable',
                              'value': True}],
                    value=[],
                    id='parallel-switch',
                    switch=True,
                    style={'float': 'right'}
                )
            )
        ]),

        html.Hr(),

        dcc.Loading(
            id='loading_parallel',
            children=[
                dbc.Row([
                    dbc.Col(
                        dcc.Dropdown(
                            id='dim-picker-parallel',
                            multi=True
                        ),
                    ),
                    dbc.Tooltip(
                        'Dimensions',
                        target='dim-picker-parallel',
                        placement='top',
                    ),
                    dbc.Col(dbc.InputGroup([
                        dbc.InputGroupText('c'),
                        dbc.Select(
                            id='c-picker-parallel',
                            disabled=False,
                        )
                    ])
                    ),
                    dbc.Tooltip(
                        'Select color axis',
                        target='c-picker-parallel',
                        placement='top',
                    ),
                ]),
                dbc.Collapse(
                    html.Div([
                        dcc.Graph(
                            id='parallel',
                            config={'displaylogo': False}
                        ),
                        dbc.Row([
                            dbc.Col(
                                dbc.Button(
                                    'Export',
                                    id='export-parallel',
                                    n_clicks=0,
                                    style={'float': 'right'}
                                )
                            ),
                        ])
                    ]), is_open=False,
                    id="collapse-parallel"
                )
            ],
            type='default',
        ),
    ])
], className="shadow-sm")


heatmap_card = dbc.Card([
    dbc.CardBody([
        dbc.Row([
            dbc.Col(
                dbc.Label('Heatmap')
            ),
            dbc.Col(
                dbc.Checklist(
                    options=[{'label': 'Enable',
                              'value': True}],
                    value=[],
                    id='heat-switch',
                    switch=True,
                    style={'float': 'right'}
                )
            )
        ]),

        html.Hr(),

        dcc.Loading(
            id='loading_heat',
            children=[
                dbc.Row([
                    dbc.Col(dbc.InputGroup([
                        dbc.InputGroupText('x'),
                        dbc.Select(
                            id='x-picker-heatmap',
                            disabled=False,
                        )
                    ])
                    ),
                    dbc.Tooltip(
                        'Select x axis',
                        target='x-picker-heatmap',
                        placement='top',
                    ),
                    dbc.Col(dbc.InputGroup([
                        dbc.InputGroupText('y'),
                        dbc.Select(
                            id='y-picker-heatmap',
                            disabled=False,
                        )
                    ])
                    ),
                    dbc.Tooltip(
                        'Select y axis',
                        target='y-picker-heatmap',
                        placement='top',
                    ),
                ]),
                dbc.Collapse(
                    html.Div([
                        dcc.Graph(
                            id='heatmap',
                            config={'displaylogo': False},
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
                                    style={'float': 'right'}
                                )
                            ),
                        ])
                    ]), is_open=False,
                    id="collapse-heatmap")
            ],
            type='default',
        ),
    ])
], className="shadow-sm")


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
        dcc.Store(id='visible-table-change-trigger', data=0),

        dcc.Store(id='local-case-selection', storage_type='local'),
        dcc.Store(id='local-file-selection', storage_type='local'),

        dbc.Card(
            dbc.CardBody([dbc.Row([
                dbc.Col(dbc.Row([
                    html.Div(
                        html.Img(
                            src=app.get_asset_url(
                                'sensorview_logo.svg'),
                            id='sensorview-image',
                            style={'height': '110px',
                                   'width': 'auto'},
                        ), className="text-center"
                    ),
                    html.H4(app.title, className="text-center"),
                    html.P(
                        'Sensor Data Visualization',
                        className="text-center"
                    ),
                ]), width=3),
                dbc.Col(dbc.Row([
                    dbc.Col(dbc.InputGroup([
                        dbc.InputGroupText('Test Case'),
                        dbc.Select(id='case-picker'),
                    ]), width=4),
                    dbc.Tooltip(
                        'Select a test case',
                        target='case-picker',
                        placement='top',
                    ),
                    dbc.Col(dbc.InputGroup([
                        dbc.InputGroupText('Log File'),
                        dbc.Select(id='file-picker'),
                        dbc.Button(html.I(className='bi bi-arrow-clockwise'),
                            id='refresh-button',
                            n_clicks=0)
                    ]), width=8),
                    dbc.Tooltip(
                        'Select a log file',
                        target='file-picker',
                        placement='top',
                    ),
                    dbc.Tooltip(
                        'Refresh test cases',
                        target='refresh-button',
                        placement='top',
                    ),
                    dbc.Col(html.Div([dbc.Button(
                        html.I(className='bi bi-link-45deg'),
                        id='button-add',
                        n_clicks=0,
                        size="sm")], className='d-grid'), width=12, className='my-2'),
                    dbc.Tooltip(
                        'Combine other log files',
                        target='button-add',
                        placement='top',
                    ),
                    dbc.Col(dbc.Collapse(
                            dcc.Dropdown(id='file-add',
                                         multi=True),
                            id='collapse-add',
                            is_open=False), width=12),
                    dbc.Tooltip(
                        'Select additional log files',
                        target='file-add',
                        placement='top',
                    ),
                ]), width=9),
            ], align="center"),]), className="my-3"),

        html.Hr(),

        view3d_card,

        dbc.CardGroup(
            [left2d_card,
             right2d_card], className='mb-3'),

        dbc.CardGroup(
            [hist_card,
             violin_card], className='mb-3'),

        dbc.CardGroup(
            [parallel_card,
             heatmap_card], className='mb-3'),

        html.Hr(),

        dbc.Row(
            [
                dbc.Row([
                    dbc.Spinner(color="info",
                                spinner_style={"width": "6rem",
                                               "height": "6rem"}),
                    dbc.Label('Loading ...',
                              color='light',
                              className="text-center")
                ], align="center",
                    justify="center",)
            ],
            id='loading-view',
            align="center",
            justify="center",
            style={
                'position': 'fixed',
                'top': 0,
                'left': 0,
                'width': '100%',
                'height': '100%',
                'background-color': 'rgba(0, 0, 0, 0.9)'}
        ),

        dcc.Markdown(
            'Designed and developed by **Zhengyu Peng** \
                | Powered by [Dash](https://plotly.com/dash/),\
                [Redis](https://redis.io/),\
                [Celery](https://docs.celeryproject.org/en/stable/)'),
    ], fluid=True, className="dbc_light")
