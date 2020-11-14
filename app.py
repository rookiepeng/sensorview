"""

    Copyright (C) 2019 - 2020  Zhengyu Peng
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


from queue import Queue

import datetime

from data_processing import filter_all
from data_processing import DataProcessing

import json
import os

import dash
import dash_daq as daq
from dash.dependencies import Input, Output, State, MATCH, ALL
import dash_core_components as dcc
import dash_html_components as html
from dash.exceptions import PreventUpdate
import numpy as np
import pandas as pd
import os
import plotly.graph_objs as go
import plotly.io as pio

from viz.viz import get_figure_data, get_figure_layout, get_host_data
from viz.viz import get_2d_scatter, get_histogram, get_heatmap


def scatter3d_data(det_list, params, keys_dict, name):

    return dict(
        data=[get_figure_data(
            det_list=det_list,
            x_key=params['x_det_key'],
            y_key=params['y_det_key'],
            z_key=params['z_det_key'],
            color_key=params['color_key'],
            color_label=params['color_label'],
            name=name,
            hover_dict=keys_dict,
            c_range=params['c_range']
        ),
            get_host_data(
            det_list=det_list,
            x_key=params['x_host_key'],
            y_key=params['y_host_key'],
        )],
        layout=get_figure_layout(
            x_range=params['x_range'],
            y_range=params['y_range'],
            z_range=params['z_range'])
    )


def load_config(json_file):
    with open(json_file, 'r') as read_file:
        return json.load(read_file)


###############################################################
app = dash.Dash(__name__,
                meta_tags=[{
                    'name': 'viewport',
                    'content': 'width=device-width,initial-scale=1'
                }])
server = app.server
app.scripts.config.serve_locally = True
app.css.config.serve_locally = True
app.title = 'SensorView'

ui_config = load_config('ui.json')

num_keys = []
for idx, s_item in enumerate(ui_config['numerical']):
    num_keys.append(
        ui_config['numerical'][s_item]['key'])

cat_keys = []
for idx, d_item in enumerate(ui_config['categorical']):
    cat_keys.append(
        ui_config['categorical'][d_item]['key'])


keys_dict = {**ui_config['categorical'], **ui_config['numerical']}

task_queue = Queue()
processing = DataProcessing(ui_config, task_queue)

play_bar_callback_output = [
    Output('slider-frame', 'min'),
    Output('slider-frame', 'max'),
    Output('slider-frame', 'value'),
]

play_bar_callback_input = [
    Input('slider-frame', 'value')
]

test_cases = []
for (dirpath, dirnames, filenames) in os.walk('./data'):
    test_cases.extend(dirnames)
    break

data_files = []
for r, d, f in os.walk('./data/'+test_cases[0]):
    for file in f:
        if '.pkl' in file:
            data_files.append(file)
    break

graph_3d_params = {
    'x_det_key': keys_dict[
        ui_config['graph_3d_detections']['default_x']
    ]['key'],
    'y_det_key': keys_dict[
        ui_config['graph_3d_detections']['default_y']
    ]['key'],
    'z_det_key': keys_dict[
        ui_config['graph_3d_detections']['default_z']
    ]['key'],
    'x_host_key': ui_config['host'][
        ui_config['graph_3d_host']['default_x']
    ]['key'],
    'y_host_key': ui_config['host'][
        ui_config['graph_3d_host']['default_y']
    ]['key'],
    'x_range': [0, 0],
    'y_range': [0, 0],
    'z_range': [0, 0],
    'c_range': [0, 0],
    'color_key': keys_dict[
        ui_config['graph_3d_detections']['default_color']
    ]['key'],
    'color_label': keys_dict[
        ui_config['graph_3d_detections']['default_color']
    ]['description'],
    'db': False,
}

app.layout = html.Div([
    dcc.Store(id='config', data=ui_config),
    dcc.Store(id='keys-dict', data=keys_dict),
    dcc.Store(id='scatter3d-params', data=graph_3d_params),
    dcc.Store(id='num-key-list', data=num_keys),
    dcc.Store(id='cat-key-list', data=cat_keys),
    dcc.Store(id='cat-key-values'),
    dcc.Store(id='num-key-values'),
    dcc.Store(id='selected-data-left'),
    dcc.Store(id='selected-data-right'),
    html.Div([
        html.Div([
            html.Img(
                src=app.get_asset_url('sensorview_logo.svg'),
                id='sensorview-image',
                style={
                    'height': '100px',
                    'width': 'auto',
                    'margin-bottom': '0px',
                },
            )
        ], className='one-third column'),
        html.Div([
            html.Div(
                [
                    html.H3(
                        'SensorView',
                        style={'margin-bottom': '0px'},
                    ),
                    html.H5(
                        'Sensor Data Visualization',
                        style={'margin-top': '0px'}),
                ]
            ),
        ],
            className='one-half columns',
            id='title',
        ),

        html.Div([], className='one-third column'),
    ], className='row flex-display',
        style={'margin-bottomm': '25px'}),

    html.Div([
        html.Div([
            html.H6('Test Case'),
            dcc.Dropdown(
                id='test-case',
                options=[{'label': i, 'value': i} for i in test_cases],
                value=test_cases[0]
            ),
        ], className='pretty_container six column'),

        html.Div([
            html.H6('Data File'),
            dcc.Dropdown(
                id='data-file',
                options=[{'label': i, 'value': i} for i in data_files],
                value=data_files[0]
            ),
        ], className='pretty_container rix column'),
    ], className='row flex-display'),

    html.Div([
        html.Div([
            html.H6('Control'),

            html.Div([
                daq.BooleanSwitch(
                    id='overlay-switch',
                    on=False
                ),
                html.Label('Overlay all frames'),
            ], className='column flex-display',
                style={'margin-bottom': '10px'}
            ),

            html.Div([
                daq.BooleanSwitch(
                    id='visible-switch',
                    on=False
                ),
                html.Label('Click to change visibility'),
            ], className='column flex-display',
                style={'margin-bottom': '20px'}
            ),

            html.H6('Filter'),

            html.Div(id='dropdown-container', children=[]),

            html.Div(id='slider-container', children=[]),
        ],
            className='pretty_container three columns',
        ),

        html.Div([
            html.Div([
                html.Div([
                    html.H6('3D View'),
                ], className='ten columns'),

                html.Div([
                    dcc.Dropdown(
                        id='color-picker-3d',
                        options=[{
                            'label': ui_config['numerical'][f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                                ui_config['numerical'])],
                        value=ui_config['graph_3d_detections']['default_color']
                    ),
                ], className='two columns',
                    style={'margin-bottom': '10px'}),
            ], className='row flex-display'),
            dcc.Graph(
                id='scatter3d',
                config={
                    'displaylogo': False,
                    'modeBarButtonsToRemove': ['resetCameraDefault3d',
                                               'resetCameraLastSave3d'],
                },
                figure={
                    'data': [{'mode': 'markers', 'type': 'scatter3d',
                              'x': [], 'y': [], 'z': []}
                             ],
                    'layout': {'template': pio.templates['plotly_dark'],
                               'height': 650,
                               'uirevision': 'no_change'
                               }
                },
            ),
            html.Div([
                dcc.Slider(
                    id='slider-frame',
                    step=1,
                    value=0,
                    updatemode='drag',
                )], style={'box-sizing': 'border-box',
                           'width': '100%',
                           'display': 'inline-block',
                           'padding': '2rem 0rem'})
        ], className='pretty_container nine columns'),

    ], className='row flex-display rows',
    ),

    html.Div([
        html.Div([
            html.Div([
                html.Div([
                    html.H6('2D View'),
                ], className='ten columns'),
                html.Div([
                    daq.BooleanSwitch(
                        id='left-switch',
                        on=False
                    ),
                ], className='two columns',
                    style={'margin-top': '10px'}),
            ], className='row flex-display'),

            html.Div([
                html.Div([
                    html.Label('x-axis'),
                    dcc.Dropdown(
                        id='x-scatter2d-left',
                        options=[{
                            'label': keys_dict[f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                                keys_dict)],
                        value=ui_config['graph_2d_left']['default_x'],
                        disabled=True
                    ),
                ], className='one-third column'),
                html.Div([
                    html.Label('y-axis'),
                    dcc.Dropdown(
                        id='y-scatter2d-left',
                        options=[{
                            'label': keys_dict[f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                                keys_dict)],
                        value=ui_config['graph_2d_left']['default_y'],
                        disabled=True
                    ),
                ], className='one-third column'),
                html.Div([
                    html.Label('color'),
                    dcc.Dropdown(
                        id='color-scatter2d-left',
                        options=[{
                            'label': keys_dict[f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                                keys_dict)],
                        value=ui_config['graph_2d_left']['default_color'],
                        disabled=True
                    ),
                ], className='one-third column'),
            ], className='row flex-display'),

            dcc.Loading(
                id='loading_left',
                children=[
                    dcc.Graph(
                        id='scatter2d-left',
                        config={
                            'displaylogo': False
                        },
                        figure={
                            'data': [{'mode': 'markers', 'type': 'scattergl',
                                      'x': [], 'y': []}
                                     ],
                            'layout': {
                                'uirevision': 'no_change'
                            }
                        },
                    ),
                    html.Div([
                        html.Div([
                            html.Button(
                                'Hide/Unhide',
                                id='hide-left',
                                n_clicks=0),
                        ], className='nine columns'),
                        html.Div([
                            html.Button(
                                'Export',
                                id='export-scatter2d-left',
                                n_clicks=0),
                            html.Div(id='hidden-scatter2d-left',
                                     style={'display': 'none'}),
                        ], className='two columns'),
                    ], className='row flex-display'),
                ],
                type='default',
            ),
        ], className='pretty_container six columns'),

        html.Div([
            html.Div([
                html.Div([
                    html.H6('2D View'),
                ], className='ten columns'),
                html.Div([
                    daq.BooleanSwitch(
                        id='right-switch',
                        on=False
                    ),
                ], className='two columns',
                    style={'margin-top': '10px'}),
            ], className='row flex-display'),

            html.Div([
                html.Div([
                    html.Label('x-axis'),
                    dcc.Dropdown(
                        id='x-scatter2d-right',
                        options=[{
                            'label': keys_dict[f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                                keys_dict)],
                        value=ui_config['graph_2d_right']['default_x'],
                        disabled=True
                    ),
                ], className='one-third column'),
                html.Div([
                    html.Label('y-axis'),
                    dcc.Dropdown(
                        id='y-scatter2d-right',
                        options=[{
                            'label': keys_dict[f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                                keys_dict)],
                        value=ui_config['graph_2d_right']['default_y'],
                        disabled=True
                    ),
                ], className='one-third column'),
                html.Div([
                    html.Label('color'),
                    dcc.Dropdown(
                        id='color-scatter2d-right',
                        options=[{
                            'label': keys_dict[f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                                keys_dict)],
                        value=ui_config['graph_2d_right']['default_color'],
                        disabled=True
                    ),
                ], className='one-third column'),
            ], className='row flex-display'),

            dcc.Loading(
                id='loading_right',
                children=[
                    dcc.Graph(
                        id='scatter2d-right',
                        config={
                            'displaylogo': False
                        },
                        figure={
                            'data': [{'mode': 'markers', 'type': 'scattergl',
                                      'x': [], 'y': []}
                                     ],
                            'layout': {
                                'uirevision': 'no_change'
                            }
                        },
                    ),

                    html.Div([
                        html.Div([
                        ], className='nine columns'),
                        html.Div([
                            html.Button(
                                'Export',
                                id='export-scatter2d-right',
                                n_clicks=0),
                            html.Div(id='hidden-scatter2d-right',
                                     style={'display': 'none'}),
                        ], className='two columns'),
                    ], className='row flex-display'),
                ],
                type='default',
            ),
        ], className='pretty_container six columns'),
    ], className='row flex-display'),

    html.Div([
        html.Div([
            html.Div([
                html.Div([
                    html.H6('Histogram'),
                ], className='ten columns'),
                html.Div([
                    daq.BooleanSwitch(
                        id='histogram-switch',
                        on=False
                    ),
                ], className='two columns',
                    style={'margin-top': '10px'}),
            ], className='row flex-display'),

            html.Div([
                html.Div([
                    html.Label('x-axis'),
                    dcc.Dropdown(
                        id='x-histogram',
                        options=[{
                            'label': keys_dict[f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                            keys_dict)],
                        value=ui_config['graph_2d_right']['default_x'],
                        disabled=True
                    ),
                ], className='one-third column'),
                html.Div([
                    html.Label('y-axis'),
                    dcc.Dropdown(
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
                        disabled=True
                    ),
                ], className='one-third column'),
            ], className='row flex-display'),

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

                    html.Div([
                        html.Div([
                        ], className='nine columns'),
                        html.Div([
                            html.Button(
                                'Export', id='export-histogram', n_clicks=0),
                            html.Div(id='hidden-histogram',
                                     style={'display': 'none'}),
                        ], className='two columns'),
                    ], className='row flex-display'),
                ],
                type='default',
            ),

        ], className='pretty_container six columns'),

        html.Div([
            html.Div([
                html.Div([
                    html.H6('Heatmap'),
                ], className='ten columns'),
                html.Div([
                    daq.BooleanSwitch(
                        id='heat-switch',
                        on=False
                    ),
                ], className='two columns',
                    style={'margin-top': '10px'}),
            ], className='row flex-display'),

            html.Div([
                html.Div([
                    html.Label('x-axis'),
                    dcc.Dropdown(
                        id='x-heatmap',
                        options=[{
                            'label': keys_dict[f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                            keys_dict)],
                        value=ui_config['graph_2d_right']['default_x'],
                        disabled=True
                    ),
                ], className='one-third column'),
                html.Div([
                    html.Label('y-axis'),
                    dcc.Dropdown(
                        id='y-heatmap',
                        options=[{
                            'label': keys_dict[f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                            keys_dict)],
                        value=ui_config['graph_2d_right']['default_y'],
                        disabled=True
                    ),
                ], className='one-third column'),
            ], className='row flex-display'),

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

                    html.Div([
                        html.Div([
                        ], className='nine columns'),
                        html.Div([
                            html.Button(
                                'Export', id='export-heatmap', n_clicks=0),
                            html.Div(id='hidden-heatmap',
                                     style={'display': 'none'}),
                        ], className='two columns'),
                    ], className='row flex-display'),
                ],
                type='default',
            ),
        ], className='pretty_container six columns'),
    ], className='row flex-display'),

    # Hidden div inside the app that stores the intermediate value
    html.Div(id='filter-trigger', children=0, style={'display': 'none'}),
    html.Div(id='left-hide-trigger', children=0, style={'display': 'none'}),
    html.Div(id='trigger', style={'display': 'none'}),
    html.Div(id='dummy', style={'display': 'none'}),
], style={'display': 'flex', 'flex-direction': 'column'},)


@ app.callback(
    [
        Output('data-file', 'value'),
        Output('data-file', 'options'),
    ],
    [
        Input('test-case', 'value')
    ])
def test_case_selection(test_case):
    if test_case is not None:
        data_files = []
        for r, d, f in os.walk('./data/'+test_case):
            for file in f:
                if '.pkl' in file:
                    data_files.append(file)
            break

        return data_files[0], [{'label': i, 'value': i} for i in data_files]
    else:
        raise PreventUpdate


@ app.callback(
    [
        Output('scatter3d', 'figure'),
        Output('filter-trigger', 'children'),
        Output('cat-key-values', 'data'),
        Output('num-key-values', 'data'),
        Output('scatter3d-params', 'data'),
    ],
    [
        Input('slider-frame', 'value'),
        Input({'type': 'filter-dropdown', 'index': ALL}, 'value'),
        Input({'type': 'filter-slider', 'index': ALL}, 'value'),
        Input('color-picker-3d', 'value'),
        Input('overlay-switch', 'on'),
        Input('scatter3d', 'clickData'),
        Input('left-hide-trigger', 'children'),
    ],
    [
        State('keys-dict', 'data'),
        State('visible-switch', 'on'),
        State('num-key-list', 'data'),
        State('cat-key-list', 'data'),
        State('filter-trigger', 'children'),
        State('config', 'data'),
        State('scatter3d-params', 'data'),
    ])
def update_filter(
    slider_arg,
    categorical_key_values,
    numerical_key_values,
    color_picker,
    overlay_sw,
    click_data,
    left_hide_trigger,
    keys_dict,
    visible_sw,
    num_keys,
    cat_keys,
    trigger_idx,
    ui_config,
    graph_3d_params
):
    global task_queue

    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    color_key = keys_dict[color_picker]['key']
    color_label = keys_dict[color_picker]['description']

    slider_key = keys_dict[ui_config['slider']]['key']
    slider_label = keys_dict[ui_config['slider']
                             ]['description']

    x_det = graph_3d_params['x_det_key']
    x_host = graph_3d_params['x_host_key']
    y_det = graph_3d_params['y_det_key']
    y_host = graph_3d_params['y_host_key']
    z_det = graph_3d_params['z_det_key']

    x_range = [
        np.min([numerical_key_values[num_keys.index(x_det)][0],
                np.min(processing.data[x_host])]),
        np.max([numerical_key_values[num_keys.index(x_det)][1],
                np.max(processing.data[x_host])])]
    y_range = [
        np.min([numerical_key_values[num_keys.index(y_det)][0],
                np.min(processing.data[y_host])]),
        np.max([numerical_key_values[num_keys.index(y_det)][1],
                np.max(processing.data[y_host])])]
    z_range = numerical_key_values[num_keys.index(z_det)]
    c_range = [
        np.min(processing.data[color_key]),
        np.max(processing.data[color_key])
    ]

    graph_3d_params['x_range'] = x_range
    graph_3d_params['y_range'] = y_range
    graph_3d_params['z_range'] = z_range
    graph_3d_params['color_key'] = color_key
    graph_3d_params['color_label'] = color_label
    graph_3d_params['c_range'] = c_range

    if trigger_id == 'slider-frame' and not overlay_sw:
        if processing.get_frame_ready_index() >= slider_arg:
            fig = processing.get_frame(slider_arg)
            filter_trig = dash.no_update
        else:
            filterd_frame = processing.data[
                processing.data[slider_key] == processing.frame_idx[slider_arg]
            ]
            filterd_frame = filterd_frame.reset_index()

            filterd_frame = filter_all(
                filterd_frame,
                num_keys,
                numerical_key_values,
                cat_keys,
                categorical_key_values
            )
            fig = scatter3d_data(
                filterd_frame,
                graph_3d_params,
                keys_dict,
                'Index: ' + str(slider_arg) + ' (' + slider_label+')'
            )

            filter_trig = dash.no_update

    elif trigger_id == 'scatter3d' and visible_sw and click_data['points'][0]['curveNumber'] == 0:
        if processing.data['Visibility'][
            click_data['points'][0]['id']
        ] == 'visible':
            processing.data.at[click_data['points']
                               [0]['id'], 'Visibility'] = 'hidden'
        else:
            processing.data.at[click_data['points']
                               [0]['id'], 'Visibility'] = 'visible'

        if overlay_sw:
            filterd_frame = filter_all(
                processing.data,
                num_keys,
                numerical_key_values,
                cat_keys,
                categorical_key_values
            )

            task_queue.put_nowait(
                {
                    'trigger': 'filter',
                    'cat_keys': cat_keys,
                    'num_keys': num_keys,
                    'cat_values': categorical_key_values,
                    'num_values': numerical_key_values,
                    'graph_params': graph_3d_params,
                }
            )

            fig = fig = scatter3d_data(
                filterd_frame,
                graph_3d_params,
                keys_dict,
                'Index: ' + str(slider_arg) + ' (' + slider_label+')'
            )
            filter_trig = trigger_idx+1

        else:
            filterd_frame = processing.data[
                processing.data[slider_key] == processing.frame_idx[slider_arg]
            ]
            filterd_frame = filterd_frame.reset_index()

            filterd_frame = filter_all(
                filterd_frame,
                num_keys,
                numerical_key_values,
                cat_keys,
                categorical_key_values
            )

            processing.fig_list[slider_arg] = scatter3d_data(
                filterd_frame,
                graph_3d_params,
                keys_dict,
                'Index: ' + str(slider_arg) + ' (' + slider_label+')'
            )
            fig = processing.fig_list[slider_arg]
            filter_trig = trigger_idx+1

    elif trigger_id == 'left-hide-trigger':

        if overlay_sw:
            filterd_frame = filter_all(
                processing.data,
                num_keys,
                numerical_key_values,
                cat_keys,
                categorical_key_values
            )

            fig = scatter3d_data(
                filterd_frame,
                graph_3d_params,
                keys_dict,
                'Index: ' + str(slider_arg) + ' (' + slider_label+')'
            )
            filter_trig = dash.no_update

        else:
            filterd_frame = processing.data[
                processing.data[
                    ui_config['numerical']
                    [
                        ui_config['slider']
                    ]['key']] == processing.frame_idx[slider_arg]
            ]
            filterd_frame = filterd_frame.reset_index()

            filterd_frame = filter_all(
                filterd_frame,
                num_keys,
                numerical_key_values,
                cat_keys,
                categorical_key_values
            )

            fig = scatter3d_data(
                filterd_frame,
                graph_3d_params,
                keys_dict,
                'Index: ' + str(slider_arg) + ' (' + slider_label+')'
            )
            filter_trig = dash.no_update

    else:
        if None not in categorical_key_values:

            processing.filtering_ready = False
            task_queue.put_nowait(
                {
                    'trigger': 'filter',
                    'cat_keys': cat_keys,
                    'num_keys': num_keys,
                    'cat_values': categorical_key_values,
                    'num_values': numerical_key_values,
                    'graph_params': graph_3d_params,
                }
            )

            if overlay_sw:
                filterd_frame = filter_all(
                    processing.data,
                    num_keys,
                    numerical_key_values,
                    cat_keys,
                    categorical_key_values
                )
            else:
                filterd_frame = processing.data[
                    processing.data[
                        ui_config['numerical']
                        [
                            ui_config['slider']
                        ]['key']] == processing.frame_idx[slider_arg]
                ]
                filterd_frame = filterd_frame.reset_index()

                filterd_frame = filter_all(
                    filterd_frame,
                    num_keys,
                    numerical_key_values,
                    cat_keys,
                    categorical_key_values
                )
            fig = scatter3d_data(
                filterd_frame,
                graph_3d_params,
                keys_dict,
                'Index: ' + str(slider_arg) + ' (' + slider_label+')'
            )
            filter_trig = trigger_idx+1
        else:
            raise PreventUpdate

    return [fig,
            filter_trig,
            categorical_key_values,
            numerical_key_values,
            graph_3d_params]


@ app.callback(
    [
        Output('scatter2d-left', 'figure'),
        Output('x-scatter2d-left', 'disabled'),
        Output('y-scatter2d-left', 'disabled'),
        Output('color-scatter2d-left', 'disabled'),
    ],
    [
        Input('filter-trigger', 'children'),
        Input('left-hide-trigger', 'children'),
        Input('left-switch', 'on'),
        Input('x-scatter2d-left', 'value'),
        Input('y-scatter2d-left', 'value'),
        Input('color-scatter2d-left', 'value'),
    ],
    [
        State('keys-dict', 'data'),
        State('num-key-list', 'data'),
        State('cat-key-list', 'data'),
        State('cat-key-values', 'data'),
        State('num-key-values', 'data'),
    ]
)
def update_left_graph(
    trigger_idx,
    left_hide_trigger,
    left_sw,
    x_left,
    y_left,
    color_left,
    keys_dict,
    num_keys,
    cat_keys,
    categorical_key_values,
    numerical_key_values
):
    x_key = keys_dict[x_left]['key']
    y_key = keys_dict[y_left]['key']
    color_key = keys_dict[color_left]['key']
    x_label = keys_dict[x_left]['description']
    y_label = keys_dict[y_left]['description']
    color_label = keys_dict[color_left]['description']

    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if left_sw:
        if processing.is_filtering_ready() and trigger_id != 'filter-trigger' and trigger_id != 'left-hide-trigger':
            left_fig = get_2d_scatter(
                processing.get_filtered_data(),
                x_key,
                y_key,
                color_key,
                x_label,
                y_label,
                color_label
            )
        else:
            filtered_table = filter_all(
                processing.data,
                num_keys,
                numerical_key_values,
                cat_keys,
                categorical_key_values
            )

            left_fig = get_2d_scatter(
                filtered_table,
                x_key,
                y_key,
                color_key,
                x_label,
                y_label,
                color_label
            )
        left_x_disabled = False
        left_y_disabled = False
        left_color_disabled = False

    else:
        left_fig = {
            'data': [{'mode': 'markers', 'type': 'scattergl',
                      'x': [], 'y': []}
                     ],
            'layout': {
            }}
        left_x_disabled = True
        left_y_disabled = True
        left_color_disabled = True

    return [
        left_fig,
        left_x_disabled,
        left_y_disabled,
        left_color_disabled,
    ]


@ app.callback(
    [
        Output('scatter2d-right', 'figure'),
        Output('x-scatter2d-right', 'disabled'),
        Output('y-scatter2d-right', 'disabled'),
        Output('color-scatter2d-right', 'disabled'),
    ],
    [
        Input('filter-trigger', 'children'),
        Input('left-hide-trigger', 'children'),
        Input('right-switch', 'on'),
        Input('x-scatter2d-right', 'value'),
        Input('y-scatter2d-right', 'value'),
        Input('color-scatter2d-right', 'value'),
    ],
    [
        State('keys-dict', 'data'),
        State('num-key-list', 'data'),
        State('cat-key-list', 'data'),
        State('cat-key-values', 'data'),
        State('num-key-values', 'data'),
    ]
)
def update_right_graph(
    trigger_idx,
    left_hide_trigger,
    right_sw,
    x_right,
    y_right,
    color_right,
    keys_dict,
    num_keys,
    cat_keys,
    categorical_key_values,
    numerical_key_values
):
    x_key = keys_dict[x_right]['key']
    y_key = keys_dict[y_right]['key']
    color_key = keys_dict[color_right]['key']
    x_label = keys_dict[x_right]['description']
    y_label = keys_dict[y_right]['description']
    color_label = keys_dict[color_right]['description']

    if right_sw:
        if processing.is_filtering_ready():
            right_fig = get_2d_scatter(
                processing.get_filtered_data(),
                x_key,
                y_key,
                color_key,
                x_label,
                y_label,
                color_label
            )
        else:
            filtered_table = filter_all(
                processing.data,
                num_keys,
                numerical_key_values,
                cat_keys,
                categorical_key_values
            )

            right_fig = get_2d_scatter(
                filtered_table,
                x_key,
                y_key,
                color_key,
                x_label,
                y_label,
                color_label
            )
        right_x_disabled = False
        right_y_disabled = False
        right_color_disabled = False

    else:
        right_fig = {
            'data': [{'mode': 'markers', 'type': 'scattergl',
                      'x': [], 'y': []}
                     ],
            'layout': {
            }}

        right_x_disabled = True
        right_y_disabled = True
        right_color_disabled = True

    return [
        right_fig,
        right_x_disabled,
        right_y_disabled,
        right_color_disabled,
    ]


@ app.callback(
    [
        Output('histogram', 'figure'),
        Output('x-histogram', 'disabled'),
        Output('y-histogram', 'disabled'),
    ],
    [
        Input('filter-trigger', 'children'),
        Input('left-hide-trigger', 'children'),
        Input('histogram-switch', 'on'),
        Input('x-histogram', 'value'),
        Input('y-histogram', 'value'),
    ],
    [
        State('keys-dict', 'data'),
        State('num-key-list', 'data'),
        State('cat-key-list', 'data'),
        State('cat-key-values', 'data'),
        State('num-key-values', 'data'),
    ]
)
def update_histogram(
    trigger_idx,
    left_hide_trigger,
    histogram_sw,
    x_histogram,
    y_histogram,
    keys_dict,
    num_keys,
    cat_keys,
    categorical_key_values,
    numerical_key_values
):
    x_key = keys_dict[x_histogram]['key']
    x_label = keys_dict[x_histogram]['description']
    y_key = y_histogram

    if histogram_sw:
        if processing.is_filtering_ready():
            histogram_fig = get_histogram(
                processing.get_filtered_data(),
                x_key,
                x_label,
                y_key
            )
        else:
            filtered_table = filter_all(
                processing.data,
                num_keys,
                numerical_key_values,
                cat_keys,
                categorical_key_values
            )

            histogram_fig = get_histogram(
                filtered_table,
                x_key,
                x_label,
                y_key
            )
        histogram_x_disabled = False
        histogram_y_disabled = False
    else:
        histogram_fig = {
            'data': [{'type': 'histogram',
                      'x': []}
                     ],
            'layout': {
            }}
        histogram_x_disabled = True
        histogram_y_disabled = True

    return [
        histogram_fig,
        histogram_x_disabled,
        histogram_y_disabled,
    ]


@ app.callback(
    [
        Output('heatmap', 'figure'),
        Output('x-heatmap', 'disabled'),
        Output('y-heatmap', 'disabled'),
    ],
    [
        Input('filter-trigger', 'children'),
        Input('left-hide-trigger', 'children'),
        Input('heat-switch', 'on'),
        Input('x-heatmap', 'value'),
        Input('y-heatmap', 'value'),
    ],
    [
        State('keys-dict', 'data'),
        State('num-key-list', 'data'),
        State('cat-key-list', 'data'),
        State('cat-key-values', 'data'),
        State('num-key-values', 'data'),
    ]
)
def update_heatmap(
    trigger_idx,
    left_hide_trigger,
    heat_sw,
    x_heat,
    y_heat,
    keys_dict,
    num_keys,
    cat_keys,
    categorical_key_values,
    numerical_key_values
):
    x_key = keys_dict[x_heat]['key']
    x_label = keys_dict[x_heat]['description']
    y_key = keys_dict[y_heat]['key']
    y_label = keys_dict[y_heat]['description']

    if heat_sw:
        if processing.is_filtering_ready():
            heat_fig = get_heatmap(
                processing.get_filtered_data(),
                x_key,
                y_key,
                x_label,
                y_label,
            )
        else:
            filtered_table = filter_all(
                processing.data,
                num_keys,
                numerical_key_values,
                cat_keys,
                categorical_key_values
            )

            heat_fig = get_heatmap(
                filtered_table,
                x_key,
                y_key,
                x_label,
                y_label,
            )
        heat_x_disabled = False
        heat_y_disabled = False
    else:
        heat_fig = {
            'data': [{'type': 'histogram2dcontour',
                      'x': []}
                     ],
            'layout': {
            }}
        heat_x_disabled = True
        heat_y_disabled = True

    return [
        heat_fig,
        heat_x_disabled,
        heat_y_disabled,
    ]


@ app.callback(
    play_bar_callback_output +
    [
        Output('color-picker-3d', 'value'),
        Output('left-switch', 'on'),
        Output('right-switch', 'on'),
        Output('histogram-switch', 'on'),
        Output('heat-switch', 'on'),
        Output('dropdown-container', 'children'),
        Output('slider-container', 'children')
    ],
    [
        Input('data-file', 'value')
    ],
    [
        State('test-case', 'value'),
        State('config', 'data'),
        State('num-key-list', 'data'),
        State('cat-key-list', 'data'),
        State('keys-dict', 'data'),
        State('scatter3d-params', 'data'),
    ])
def data_file_selection(
        data_file_name,
        test_case,
        ui_config,
        num_keys,
        cat_keys,
        keys_dict,
        graph_3d_params,
):
    if data_file_name is not None and test_case is not None:
        new_data = pd.read_pickle(
            './data/'+test_case+'/'+data_file_name)

        new_data['_IDS_'] = new_data.index
        new_data['Visibility'] = 'visible'

        if os.path.exists('./data/'+test_case+'/config.json'):
            ui_config = load_config('./data/'+test_case+'/config.json')
        else:
            ui_config = load_config('ui.json')

        x_det = graph_3d_params['x_det_key']
        x_host = graph_3d_params['x_host_key']
        y_det = graph_3d_params['y_det_key']
        y_host = graph_3d_params['y_host_key']
        z_det = graph_3d_params['z_det_key']
        color_key = graph_3d_params['color_key']

        graph_3d_params['x_range'] = [
            np.min([np.min(new_data[x_det]),
                    np.min(new_data[x_host])]),
            np.max([np.max(new_data[x_det]),
                    np.max(new_data[x_host])])]
        graph_3d_params['y_range'] = [
            np.min([np.min(new_data[y_det]),
                    np.min(new_data[y_host])]),
            np.max([np.max(new_data[y_det]),
                    np.max(new_data[y_host])])]
        graph_3d_params['z_range'] = [
            np.min(new_data[z_det]),
            np.max(new_data[z_det])]
        graph_3d_params['c_range'] = [
            np.min(new_data[color_key]),
            np.max(new_data[color_key])
        ]

        frame_idx = new_data[
            keys_dict
            [ui_config['slider']]['key']].unique()
        output = [0, len(frame_idx)-1, 0]

        cat_values = []
        for idx, d_item in enumerate(ui_config['categorical']):
            var_list = new_data[ui_config['categorical']
                                [d_item]['key']].unique()

            if ui_config['categorical'][d_item]['key'] == 'Visibility':
                var_list = np.append(var_list, 'hidden')

            cat_values.append(var_list)

            options = []
            selection = []

            if ui_config['categorical'][d_item]['key'] == 'Visibility':
                for var in var_list:
                    options.append({'label': var, 'value': var})
                selection.append(np.array('visible'))
            else:
                for var in var_list:
                    options.append({'label': var, 'value': var})
                    selection.append(var)

        num_values = []
        for idx, s_item in enumerate(ui_config['numerical']):
            var_min = round(
                np.min(new_data[ui_config['numerical'][s_item]['key']]), 1)
            var_max = round(
                np.max(new_data[ui_config['numerical'][s_item]['key']]), 1)

            num_values.append([var_min, var_max])

        output.append(ui_config['graph_3d_detections']['default_color'])
        output.append(False)
        output.append(False)
        output.append(False)
        output.append(False)

        new_dropdown = []
        for idx, d_item in enumerate(ui_config['categorical']):
            var_list = new_data[ui_config['categorical']
                                [d_item]['key']].unique()
            if ui_config['categorical'][d_item]['key'] == 'Visibility':
                var_list = np.append(var_list, 'hidden')

            new_dropdown.append(
                html.Label(
                    ui_config['categorical'][d_item]['description'])
            )
            new_dropdown.append(
                dcc.Dropdown(
                    id={
                        'type': 'filter-dropdown',
                        'index': idx
                    },
                    options=[{'label': i, 'value': i}
                             for i in var_list],
                    value=var_list,
                    multi=True
                ))

        output.append(new_dropdown)

        new_slider = []
        for idx, s_item in enumerate(ui_config['numerical']):
            var_min = round(
                np.min(new_data[ui_config['numerical'][s_item]['key']])-0.1, 1)
            var_max = round(
                np.max(new_data[ui_config['numerical'][s_item]['key']])+0.1, 1)

            new_slider.append(
                html.Div(id=s_item+'_value',
                         children=ui_config['numerical'][s_item]['description']))
            new_slider.append(dcc.RangeSlider(
                id={
                    'type': 'filter-slider',
                    'index': idx
                },
                min=var_min,
                max=var_max,
                step=round((var_max-var_min)/100, 3),
                value=[var_min, var_max],
                tooltip={'always_visible': False}
            ))
        output.append(new_slider)

        task_queue.put_nowait(
            {
                'trigger': 'filter',
                'data': new_data,
                'num_keys': num_keys,
                'num_values': num_values,
                'cat_keys': cat_keys,
                'cat_values': cat_values,
                'graph_params': graph_3d_params,
            }
        )

        return output
    else:
        raise PreventUpdate


@ app.callback(
    Output('hidden-scatter2d-left', 'children'),
    Input('export-scatter2d-left', 'n_clicks'),
    State('scatter2d-left', 'figure')
)
def export_left_scatter_2d(btn, fig):
    if btn > 0:
        now = datetime.datetime.now()
        timestamp = now.strftime('%Y%m%d_%H%M%S')
        temp_fig = go.Figure(fig)
        temp_fig.write_image('images/'+timestamp+'_fig_left.png', scale=2)
    return 0


@ app.callback(
    Output('hidden-scatter2d-right', 'children'),
    Input('export-scatter2d-right', 'n_clicks'),
    State('scatter2d-right', 'figure')
)
def export_right_scatter_2d(btn, fig):
    if btn > 0:
        now = datetime.datetime.now()
        timestamp = now.strftime('%Y%m%d_%H%M%S')
        temp_fig = go.Figure(fig)
        temp_fig.write_image('images/'+timestamp+'_fig_right.png', scale=2)
    return 0


@ app.callback(
    Output('hidden-histogram', 'children'),
    Input('export-histogram', 'n_clicks'),
    State('histogram', 'figure')
)
def export_histogram(btn, fig):
    if btn > 0:
        now = datetime.datetime.now()
        timestamp = now.strftime('%Y%m%d_%H%M%S')
        temp_fig = go.Figure(fig)
        temp_fig.write_image('images/'+timestamp+'_histogram.png', scale=2)
    return 0


@ app.callback(
    Output('hidden-heatmap', 'children'),
    Input('export-heatmap', 'n_clicks'),
    State('heatmap', 'figure')
)
def export_heatmap(btn, fig):
    if btn > 0:
        now = datetime.datetime.now()
        timestamp = now.strftime('%Y%m%d_%H%M%S')
        temp_fig = go.Figure(fig)
        temp_fig.write_image('images/'+timestamp+'_heatmap.png', scale=2)
    return 0


@app.callback(
    Output('selected-data-left', 'data'),
    [Input('scatter2d-left', 'selectedData')])
def select_left_figure(selectedData):
    # print(selectedData)
    return selectedData


@app.callback(
    Output('left-hide-trigger', 'children'),
    [Input('hide-left', 'n_clicks')],
    [
        State('keys-dict', 'data'),
        State('num-key-list', 'data'),
        State('cat-key-list', 'data'),
        State('cat-key-values', 'data'),
        State('num-key-values', 'data'),
        State('selected-data-left', 'data'),
        State('left-hide-trigger', 'children'),
        State('scatter3d-params', 'data'),
    ]
)
def left_hide_button(
    btn,
    keys_dict,
    num_keys,
    cat_keys,
    categorical_key_values,
    numerical_key_values,
    selectedData,
    trigger_idx,
    graph_3d_params
):
    if btn > 0 and selectedData is not None:
        s_data = pd.DataFrame(selectedData['points'])
        idx = s_data['id']
        idx.index = idx

        vis_idx = idx[processing.data['Visibility'][idx] == 'visible']
        hid_idx = idx[processing.data['Visibility'][idx] == 'hidden']

        processing.data.loc[vis_idx, 'Visibility'] = 'hidden'
        processing.data.loc[hid_idx, 'Visibility'] = 'visible'

        processing.filtering_ready = False
        task_queue.put_nowait(
            {
                'trigger': 'filter',
                'cat_keys': cat_keys,
                'num_keys': num_keys,
                'cat_values': categorical_key_values,
                'num_values': numerical_key_values,
            }
        )

        return trigger_idx+1

    else:
        raise PreventUpdate


if __name__ == '__main__':

    processing.start()
    app.run_server(debug=True, threaded=True, processes=1, host='0.0.0.0')
