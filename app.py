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


from logging import disable
from queue import Queue

from data_processing import filter_all
from data_processing import DataProcessing

import json
import os

import dash
import dash_daq as daq
from dash.dependencies import Input, Output, State
import dash_core_components as dcc
import dash_html_components as html
from dash.exceptions import PreventUpdate
import numpy as np
import pandas as pd
import os
import plotly.graph_objs as go
import plotly.io as pio

from viz.viz import get_figure_data, get_figure_layout, get_host_data
from viz.viz import get_2d_scatter, get_stat_plot, get_heatmap


def gen_rangesliders(ui_config):
    s_list = []
    for idx, s_item in enumerate(ui_config['numerical']):
        s_list.append(
            html.Div(id=s_item+'_value',
                     children=ui_config['numerical'][s_item]['description']))
        s_list.append(dcc.RangeSlider(
            id=s_item+'_filter',
            count=1,
            min=0,
            max=10,
            step=0.5,
            value=[0, 10],
            tooltip={'always_visible': False}
        ))
    return s_list


def gen_dropdowns(ui_config):
    d_list = []
    for idx, d_item in enumerate(ui_config['categorical']):
        d_list.append(html.Label(
            ui_config['categorical'][d_item]['description']))
        d_list.append(dcc.Dropdown(
            id=d_item+'_picker',
            multi=True
        ))

    return d_list


def load_config(json_file):
    with open(json_file, "r") as read_file:
        return json.load(read_file)


###############################################################
app = dash.Dash(__name__,
                meta_tags=[{
                    "name": "viewport",
                    "content": "width=device-width,initial-scale=1"
                }])
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


all_keys = {**ui_config['categorical'], **ui_config['numerical']}

task_queue = Queue()
processing = DataProcessing(ui_config, task_queue)


picker_callback_output = []
picker_callback_input = []
for idx, d_item in enumerate(ui_config['categorical']):
    picker_callback_output.append(
        Output(d_item+'_picker', 'options')
    )
    picker_callback_output.append(
        Output(d_item+'_picker', 'value')
    )
    picker_callback_input.append(
        Input(d_item+'_picker', 'value')
    )

slider_callback_output = []
slider_callback_input = []
for idx, s_item in enumerate(ui_config['numerical']):
    slider_callback_output.append(
        Output(s_item+'_filter', 'min')
    )
    slider_callback_output.append(
        Output(s_item+'_filter', 'max')
    )
    slider_callback_output.append(
        Output(s_item+'_filter', 'value')
    )
    slider_callback_input.append(
        Input(s_item+'_filter', 'value')
    )

play_bar_callback_output = [
    Output('slider', 'min'),
    Output('slider', 'max'),
    Output('slider', 'value'),
]

play_bar_callback_input = [
    Input('slider', 'value')
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
    'x_det_key': all_keys[
        ui_config['graph_3d_detections']['default_x']
    ]['key'],
    'y_det_key': all_keys[
        ui_config['graph_3d_detections']['default_y']
    ]['key'],
    'z_det_key': all_keys[
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
    'color_key': all_keys[
        ui_config['graph_3d_detections']['default_color']
    ]['key'],
    'color_label': all_keys[
        ui_config['graph_3d_detections']['default_color']
    ]['description'],
    'db': False,
}

app.layout = html.Div([
    dcc.Store(id='config', data=ui_config),
    dcc.Store(id='all_keys', data=all_keys),
    dcc.Store(id='graph_3d_params', data=graph_3d_params),
    dcc.Store(id='numerical_keys', data=num_keys),
    dcc.Store(id='categorical_keys', data=cat_keys),
    dcc.Store(id='categorical_key_values'),
    dcc.Store(id='numerical_key_values'),
    html.Div([
        html.Div([
            html.Img(
                src=app.get_asset_url("sensorview.svg"),
                id="sensorview-image",
                style={
                    "height": "100px",
                    "width": "auto",
                    "margin-bottom": "0px",
                },
            )
        ], className="one-third column"),
        html.Div([
            html.Div(
                [
                    html.H3(
                        "SensorView",
                        style={"margin-bottom": "0px"},
                    ),
                    html.H5(
                        "Sensor Data Visualization",
                        style={"margin-top": "0px"}),
                ]
            ),
        ],
            className="one-half columns",
            id="title",
        ),

        html.Div([], className="one-third column"),
    ], className="row flex-display",
        style={"margin-bottomm": "25px"}),

    html.Div([
        html.Div([
            html.H6('Test Case'),
            dcc.Dropdown(
                id='test_case_picker',
                options=[{'label': i, 'value': i} for i in test_cases],
                value=test_cases[0]
            ),
        ], className="pretty_container six column"),

        html.Div([
            html.H6('Data File'),
            dcc.Dropdown(
                id='data_file_picker',
                options=[{'label': i, 'value': i} for i in data_files],
                value=data_files[0]
            ),
        ], className="pretty_container rix column"),
    ], className="row flex-display"),

    html.Div([
        html.Div([
            html.H6('Filter'),

            html.Div(
                gen_dropdowns(ui_config)
            ),
            html.Div(
                gen_rangesliders(ui_config)
            ),
        ],
            className="pretty_container three columns",
        ),

        html.Div([
            html.Div([
                html.Div([
                    html.H6('3D View'),
                ], className="ten columns"),
                html.Div([
                    html.Div([
                        html.Label('Overlay: '),
                        daq.BooleanSwitch(
                            id='overlay-switch',
                            on=False
                        ),
                    ], className="column flex-display"
                    ),
                ], className="two columns"),
            ], className="row flex-display"),
            html.Div([
                html.Div([], className="ten columns"),
                html.Div([
                    dcc.Dropdown(
                        id='color_main',
                        options=[{
                            'label': all_keys[f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                                all_keys)],
                        value=ui_config['graph_3d_detections']['default_color']
                    ),
                ], className="two columns",
                    style={"margin-bottom": "10px"}),
            ], className="row flex-display"),
            dcc.Graph(
                id='det_grid',
                config={
                    "displaylogo": False,
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
                    id='slider',
                    step=1,
                    value=0,
                    updatemode='drag',
                )], style={'box-sizing': 'border-box',
                           'width': '100%',
                           'display': 'inline-block',
                           'padding': '2rem 0rem'})
        ], className="pretty_container nine columns"),

    ], className="row flex-display rows",
    ),

    html.Div([
        html.Div([
            html.Div([
                html.Div([
                    html.H6('2D View'),
                ], className="ten columns"),
                html.Div([
                    daq.BooleanSwitch(
                        id='left-switch',
                        on=False
                    ),
                ], className="two columns",
                    style={"margin-top": "10px"}),
            ], className="row flex-display"),

            html.Div([
                html.Div([
                    html.Label('x-axis'),
                    dcc.Dropdown(
                        id='x_left',
                        options=[{
                            'label': all_keys[f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                                all_keys)],
                        value=ui_config['graph_2d_left']['default_x'],
                        disabled=True
                    ),
                ], className="one-third column"),
                html.Div([
                    html.Label('y-axis'),
                    dcc.Dropdown(
                        id='y_left',
                        options=[{
                            'label': all_keys[f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                                all_keys)],
                        value=ui_config['graph_2d_left']['default_y'],
                        disabled=True
                    ),
                ], className="one-third column"),
                html.Div([
                    html.Label('color'),
                    dcc.Dropdown(
                        id='color_left',
                        options=[{
                            'label': all_keys[f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                                all_keys)],
                        value=ui_config['graph_2d_left']['default_color'],
                        disabled=True
                    ),
                ], className="one-third column"),
            ], className="row flex-display"),

            dcc.Loading(
                id="loading_left",
                children=[
                    dcc.Graph(
                        id='graph_2d_left',
                        config={
                            "displaylogo": False
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
                        ], className="nine columns"),
                        html.Div([
                            html.Button(
                                'Export', id='export_left', n_clicks=0),
                            html.Div(id="hidden_export_left",
                                     style={"display": "none"}),
                        ], className="two columns"),
                    ], className="row flex-display"),
                ],
                type="default",
            ),
        ], className="pretty_container six columns"),

        html.Div([
            html.Div([
                html.Div([
                    html.H6('2D View'),
                ], className="ten columns"),
                html.Div([
                    daq.BooleanSwitch(
                        id='right-switch',
                        on=False
                    ),
                ], className="two columns",
                    style={"margin-top": "10px"}),
            ], className="row flex-display"),

            html.Div([
                html.Div([
                    html.Label('x-axis'),
                    dcc.Dropdown(
                        id='x_right',
                        options=[{
                            'label': all_keys[f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                                all_keys)],
                        value=ui_config['graph_2d_right']['default_x'],
                        disabled=True
                    ),
                ], className="one-third column"),
                html.Div([
                    html.Label('y-axis'),
                    dcc.Dropdown(
                        id='y_right',
                        options=[{
                            'label': all_keys[f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                                all_keys)],
                        value=ui_config['graph_2d_right']['default_y'],
                        disabled=True
                    ),
                ], className="one-third column"),
                html.Div([
                    html.Label('color'),
                    dcc.Dropdown(
                        id='color_right',
                        options=[{
                            'label': all_keys[f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                                all_keys)],
                        value=ui_config['graph_2d_right']['default_color'],
                        disabled=True
                    ),
                ], className="one-third column"),
            ], className="row flex-display"),

            dcc.Loading(
                id="loading_right",
                children=[
                    dcc.Graph(
                        id='graph_2d_right',
                        config={
                            "displaylogo": False
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
                        ], className="nine columns"),
                        html.Div([
                            html.Button(
                                'Export', id='export_right', n_clicks=0),
                            html.Div(id="hidden_export_right",
                                     style={"display": "none"}),
                        ], className="two columns"),
                    ], className="row flex-display"),
                ],
                type="default",
            ),
        ], className="pretty_container six columns"),
    ], className="row flex-display"),

    html.Div([
        html.Div([
            html.Div([
                html.Div([
                    html.H6('Histogram'),
                ], className="ten columns"),
                html.Div([
                    daq.BooleanSwitch(
                        id='stat-switch',
                        on=False
                    ),
                ], className="two columns",
                    style={"margin-top": "10px"}),
            ], className="row flex-display"),

            html.Div([
                html.Div([
                    html.Label('x-axis'),
                    dcc.Dropdown(
                        id='x_stat',
                        options=[{
                            'label': all_keys[f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                            all_keys)],
                        value=ui_config['graph_2d_right']['default_x'],
                        disabled=True
                    ),
                ], className="one-third column"),
                html.Div([
                    html.Label('y-axis'),
                    dcc.Dropdown(
                        id='y_stat',
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
                ], className="one-third column"),
            ], className="row flex-display"),

            dcc.Loading(
                id="loading_histogram",
                children=[
                    dcc.Graph(
                        id='graph_stat',
                        config={
                            "displaylogo": False
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
                        ], className="nine columns"),
                        html.Div([
                            html.Button(
                                'Export', id='export_stat', n_clicks=0),
                            html.Div(id="hidden_export_stat",
                                     style={"display": "none"}),
                        ], className="two columns"),
                    ], className="row flex-display"),
                ],
                type="default",
            ),

        ], className="pretty_container six columns"),

        html.Div([
            html.Div([
                html.Div([
                    html.H6('Heatmap'),
                ], className="ten columns"),
                html.Div([
                    daq.BooleanSwitch(
                        id='heat-switch',
                        on=False
                    ),
                ], className="two columns",
                    style={"margin-top": "10px"}),
            ], className="row flex-display"),

            html.Div([
                html.Div([
                    html.Label('x-axis'),
                    dcc.Dropdown(
                        id='x_heat',
                        options=[{
                            'label': all_keys[f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                            all_keys)],
                        value=ui_config['graph_2d_right']['default_x'],
                        disabled=True
                    ),
                ], className="one-third column"),
                html.Div([
                    html.Label('y-axis'),
                    dcc.Dropdown(
                        id='y_heat',
                        options=[{
                            'label': all_keys[f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                            all_keys)],
                        value=ui_config['graph_2d_right']['default_y'],
                        disabled=True
                    ),
                ], className="one-third column"),
            ], className="row flex-display"),

            dcc.Loading(
                id="loading_heat",
                children=[
                    dcc.Graph(
                        id='graph_heat',
                        config={
                            "displaylogo": False
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
                        ], className="nine columns"),
                        html.Div([
                            html.Button(
                                'Export', id='export_heat', n_clicks=0),
                            html.Div(id="hidden_export_heat",
                                     style={"display": "none"}),
                        ], className="two columns"),
                    ], className="row flex-display"),
                ],
                type="default",
            ),
        ], className="pretty_container six columns"),
    ], className="row flex-display"),

    # Hidden div inside the app that stores the intermediate value
    html.Div(id='filter-trigger', children=0, style={'display': 'none'}),
    html.Div(id='trigger', style={'display': 'none'}),
    html.Div(id='dummy', style={'display': 'none'}),
], style={"display": "flex", "flex-direction": "column"},)


@ app.callback(
    [
        Output('data_file_picker', 'value'),
        Output('data_file_picker', 'options'),
    ],
    [
        Input('test_case_picker', 'value')
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
        Output('det_grid', 'figure'),
        Output('filter-trigger', 'children'),
        Output('categorical_key_values', 'data'),
        Output('numerical_key_values', 'data'),
    ],
    play_bar_callback_input +
    picker_callback_input +
    slider_callback_input +
    [
        Input('color_main', 'value'),
    ],
    [
        State('numerical_keys', 'data'),
        State('categorical_keys', 'data'),
        State('filter-trigger', 'children'),
        State('config', 'data'),
        State('graph_3d_params', 'data'),
    ])
def update_filter(*args):
    global task_queue

    # if processing.is_locked:
    #     raise PreventUpdate

    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    slider_arg = args[0]
    graph_3d_params = args[-1]
    ui_config = args[-2]
    trigger_idx = args[-3]
    cat_keys = args[-4]
    num_keys = args[-5]

    categorical_key_values = args[1:(1+len(cat_keys))]
    numerical_key_values = args[(1+len(cat_keys)):
                                (1+len(cat_keys) + len(num_keys))]
    color_key = ui_config['numerical'][
        args[1 + len(cat_keys) + len(num_keys)]]['key']
    color_label = ui_config['numerical'][
        args[1 + len(cat_keys) + len(num_keys)]]['description']

    if trigger_id == 'slider':
        if processing.get_frame_ready_index() > slider_arg:
            return [processing.get_frame(slider_arg),
                    trigger_idx+1,
                    categorical_key_values,
                    numerical_key_values]
        else:

            filterd_frame = processing.data[
                processing.data[
                    ui_config['numerical']
                    [
                        ui_config['slider']
                    ]['key']
                ] == processing.frame_idx[slider_arg]
            ]
            filterd_frame = filterd_frame.reset_index()

            filterd_frame = filter_all(
                filterd_frame,
                num_keys,
                numerical_key_values,
                cat_keys,
                categorical_key_values
            )

            return [dict(
                data=[get_figure_data(
                    det_list=filterd_frame,
                    x_key=graph_3d_params['x_det_key'],
                    y_key=graph_3d_params['y_det_key'],
                    z_key=graph_3d_params['z_det_key'],
                    color_key=graph_3d_params['color_key'],
                    color_label=graph_3d_params['color_label'],
                    name='Index: ' +
                    str(slider_arg) + ' (' +
                    ui_config['numerical'][ui_config['slider']
                                           ]['description']+')',
                    hover_dict={
                        **ui_config['numerical'], **ui_config['categorical']},
                    c_range=graph_3d_params['c_range'],
                    db=graph_3d_params['db']
                ),
                    get_host_data(
                    det_list=filterd_frame,
                    x_key=graph_3d_params['x_host_key'],
                    y_key=graph_3d_params['y_host_key'],
                )],
                layout=get_figure_layout(
                    x_range=graph_3d_params['x_range'],
                    y_range=graph_3d_params['y_range'],
                    z_range=graph_3d_params['z_range'])
            ),
                trigger_idx+1,
                categorical_key_values,
                numerical_key_values]
    else:
        if None not in categorical_key_values:
            x_det = graph_3d_params['x_det_key']
            x_host = graph_3d_params['x_host_key']
            y_det = graph_3d_params['y_det_key']
            y_host = graph_3d_params['y_host_key']
            z_det = graph_3d_params['z_det_key']

            graph_3d_params['x_range'] = [
                np.min([np.min(processing.data[x_det]),
                        np.min(processing.data[x_host])]),
                np.max([np.max(processing.data[x_det]),
                        np.max(processing.data[x_host])])]
            graph_3d_params['y_range'] = [
                np.min([np.min(processing.data[y_det]),
                        np.min(processing.data[y_host])]),
                np.max([np.max(processing.data[y_det]),
                        np.max(processing.data[y_host])])]
            graph_3d_params['z_range'] = [
                np.min(processing.data[z_det]),
                np.max(processing.data[z_det])]
            graph_3d_params['color_key'] = color_key
            graph_3d_params['color_label'] = color_label
            graph_3d_params['c_range'] = [
                np.min(processing.data[color_key]),
                np.max(processing.data[color_key])
            ]

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

            return [dict(
                data=[get_figure_data(
                    det_list=filterd_frame,
                    x_key=graph_3d_params['x_det_key'],
                    y_key=graph_3d_params['y_det_key'],
                    z_key=graph_3d_params['z_det_key'],
                    color_key=graph_3d_params['color_key'],
                    color_label=graph_3d_params['color_label'],
                    name='Index: ' +
                    str(slider_arg) + ' (' +
                    ui_config['numerical'][ui_config['slider']
                                           ]['description']+')',
                    hover_dict={
                        **ui_config['numerical'], **ui_config['categorical']},
                    c_range=graph_3d_params['c_range'],
                    db=graph_3d_params['db']
                ),
                    get_host_data(
                    det_list=filterd_frame,
                    x_key=graph_3d_params['x_host_key'],
                    y_key=graph_3d_params['y_host_key'],
                )],
                layout=get_figure_layout(
                    x_range=graph_3d_params['x_range'],
                    y_range=graph_3d_params['y_range'],
                    z_range=graph_3d_params['z_range'])
            ),
                trigger_idx+1,
                categorical_key_values,
                numerical_key_values]
        else:
            raise PreventUpdate


@ app.callback(
    [
        Output('graph_2d_left', 'figure'),
        Output('x_left', 'disabled'),
        Output('y_left', 'disabled'),
        Output('color_left', 'disabled'),
    ],
    [
        Input('filter-trigger', 'children'),
        Input('left-switch', 'on'),
        Input('x_left', 'value'),
        Input('y_left', 'value'),
        Input('color_left', 'value'),
    ],
    [
        State('all_keys', 'data'),
        State('categorical_key_values', 'data'),
        State('numerical_key_values', 'data'),
    ]
)
def update_left_graph(
    trigger_idx,
    left_sw,
    x_left,
    y_left,
    color_left,
    all_keys,
    categorical_key_values,
    numerical_key_values
):
    x_key = all_keys[x_left]['key']
    y_key = all_keys[y_left]['key']
    color_key = all_keys[color_left]['key']
    x_label = all_keys[x_left]['description']
    y_label = all_keys[y_left]['description']
    color_label = all_keys[color_left]['description']

    if left_sw:
        if processing.is_filtering_ready:
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
                processing.num_keys,
                numerical_key_values,
                processing.cat_keys,
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
                'uirevision': 'no_change'
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
        Output('graph_2d_right', 'figure'),
        Output('x_right', 'disabled'),
        Output('y_right', 'disabled'),
        Output('color_right', 'disabled'),
    ],
    [
        Input('filter-trigger', 'children'),
        Input('right-switch', 'on'),
        Input('x_right', 'value'),
        Input('y_right', 'value'),
        Input('color_right', 'value'),
    ],
    [
        State('all_keys', 'data'),
        State('categorical_key_values', 'data'),
        State('numerical_key_values', 'data'),
    ]
)
def update_right_graph(
    trigger_idx,
    right_sw,
    x_right,
    y_right,
    color_right,
    all_keys,
    categorical_key_values,
    numerical_key_values
):
    x_key = all_keys[x_right]['key']
    y_key = all_keys[y_right]['key']
    color_key = all_keys[color_right]['key']
    x_label = all_keys[x_right]['description']
    y_label = all_keys[y_right]['description']
    color_label = all_keys[color_right]['description']

    if right_sw:
        if processing.is_filtering_ready:
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
                processing.num_keys,
                numerical_key_values,
                processing.cat_keys,
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
                'uirevision': 'no_change'
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
        Output('graph_stat', 'figure'),
        Output('x_stat', 'disabled'),
        Output('y_stat', 'disabled'),
    ],
    [
        Input('filter-trigger', 'children'),
        Input('stat-switch', 'on'),
        Input('x_stat', 'value'),
        Input('y_stat', 'value'),
    ],
    [
        State('all_keys', 'data'),
        State('categorical_key_values', 'data'),
        State('numerical_key_values', 'data'),
    ]
)
def update_stat_graph(
    trigger_idx,
    stat_sw,
    x_stat,
    y_stat,
    all_keys,
    categorical_key_values,
    numerical_key_values
):
    x_key = all_keys[x_stat]['key']
    x_label = all_keys[x_stat]['description']
    y_key = y_stat

    if stat_sw:
        if processing.is_filtering_ready:
            stat_fig = get_stat_plot(
                processing.get_filtered_data(),
                x_key,
                x_label,
                y_key
            )
        else:
            filtered_table = filter_all(
                processing.data,
                processing.num_keys,
                numerical_key_values,
                processing.cat_keys,
                categorical_key_values
            )

            stat_fig = get_stat_plot(
                filtered_table,
                x_key,
                x_label,
                y_key
            )
        stat_x_disabled = False
        stat_y_disabled = False
    else:
        stat_fig = {
            'data': [{'type': 'histogram',
                      'x': []}
                     ],
            'layout': {
                'uirevision': 'no_change'
            }}
        stat_x_disabled = True
        stat_y_disabled = True

    return [
        stat_fig,
        stat_x_disabled,
        stat_y_disabled,
    ]


@ app.callback(
    [
        Output('graph_heat', 'figure'),
        Output('x_heat', 'disabled'),
        Output('y_heat', 'disabled'),
    ],
    [
        Input('filter-trigger', 'children'),
        Input('heat-switch', 'on'),
        Input('x_heat', 'value'),
        Input('y_heat', 'value'),
    ],
    [
        State('all_keys', 'data'),
        State('categorical_key_values', 'data'),
        State('numerical_key_values', 'data'),
    ]
)
def update_heatmap(
    trigger_idx,
    heat_sw,
    x_heat,
    y_heat,
    all_keys,
    categorical_key_values,
    numerical_key_values
):
    x_key = all_keys[x_heat]['key']
    x_label = all_keys[x_heat]['description']
    y_key = all_keys[y_heat]['key']
    y_label = all_keys[y_heat]['description']

    if heat_sw:
        if processing.is_filtering_ready:
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
                processing.num_keys,
                numerical_key_values,
                processing.cat_keys,
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
                'uirevision': 'no_change'
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
    picker_callback_output +
    slider_callback_output +
    [
        Output('color_main', 'value'),
        Output('left-switch', 'on'),
        Output('right-switch', 'on'),
        Output('stat-switch', 'on'),
        Output('heat-switch', 'on'),
        Output('graph_3d_params', 'data'),
    ],
    [
        Input('data_file_picker', 'value')
    ],
    [
        State('test_case_picker', 'value'),
        State('config', 'data'),
        State('numerical_keys', 'data'),
        State('categorical_keys', 'data'),
        State('all_keys', 'data'),
        State('graph_3d_params', 'data'),
    ])
def data_file_selection(
        data_file_name,
        test_case,
        ui_config,
        num_keys,
        cat_keys,
        all_keys,
        graph_3d_params,
):
    if data_file_name is not None and test_case is not None:
        new_data = pd.read_pickle(
            './data/'+test_case+'/'+data_file_name)

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
            all_keys
            [ui_config['slider']]['key']].unique()
        output = [0, len(frame_idx)-1, 0]

        cat_values = []
        for idx, d_item in enumerate(ui_config['categorical']):
            var_list = new_data[ui_config['categorical']
                                [d_item]['key']].unique()
            cat_values.append(var_list)

            options = []
            selection = []
            for var in var_list:
                options.append({'label': var, 'value': var})
                selection.append(var)
            output.append(options)
            output.append(selection)

        num_values = []
        for idx, s_item in enumerate(ui_config['numerical']):
            var_min = round(
                np.min(new_data[ui_config['numerical'][s_item]['key']]), 1)
            var_max = round(
                np.max(new_data[ui_config['numerical'][s_item]['key']]), 1)

            num_values.append([var_min, var_max])

            output.append(var_min)
            output.append(var_max)
            output.append([var_min, var_max])

        output.append(ui_config['graph_3d_detections']['default_color'])
        output.append(False)
        output.append(False)
        output.append(False)
        output.append(False)

        output.append(graph_3d_params)

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
    Output('hidden_export_left', 'children'),
    Input('export_left', 'n_clicks'),
    State('graph_2d_left', 'figure')
)
def export_left_fig(btn, fig):
    if btn > 0:
        temp_fig = go.Figure(fig)
        temp_fig.write_image("images/fig_left.png", scale=2)
    return 0


@ app.callback(
    Output('hidden_export_right', 'children'),
    Input('export_right', 'n_clicks'),
    State('graph_2d_right', 'figure')
)
def export_right_fig(btn, fig):
    if btn > 0:
        temp_fig = go.Figure(fig)
        temp_fig.write_image("images/fig_right.png", scale=2)
    return 0


if __name__ == '__main__':

    processing.start()
    app.run_server(debug=True, threaded=True, processes=1)
