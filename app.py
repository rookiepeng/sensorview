from logging import disable
from queue import Queue

from data_processing import DataProcessing, FigureProcessing

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

from viz import get_figure_data, get_figure_layout, get_host_data


def filter_range(data_frame, name, value):
    temp_frame = data_frame[data_frame[name] >= value[0]]
    return temp_frame[
        temp_frame[name] <= value[1]
    ].reset_index(drop=True)


def filter_picker(data_frame, name, value):
    return data_frame[pd.DataFrame(
        data_frame[name].tolist()
    ).isin(value).any(1)].reset_index(drop=True)


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

task_queue = Queue()
fig_task_queue = Queue()

processing = DataProcessing(ui_config, task_queue, fig_task_queue)
fig_processing = FigureProcessing(fig_task_queue)

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


left_figure_keys = [
    ui_config['numerical'][ui_config['graph_2d_left']['default_x']]['key'],
    ui_config['numerical'][ui_config['graph_2d_left']['default_y']]['key'],
    ui_config['numerical'][ui_config['graph_2d_left']['default_color']]['key'],
    ui_config['numerical'][ui_config['graph_2d_left']
                           ['default_x']]['description'],
    ui_config['numerical'][ui_config['graph_2d_left']
                           ['default_y']]['description'],
    ui_config['numerical'][
        ui_config['graph_2d_left']['default_color']
    ]['description']]

right_figure_keys = [
    ui_config['numerical'][ui_config['graph_2d_right']['default_x']]['key'],
    ui_config['numerical'][ui_config['graph_2d_right']
                           ['default_y']]['key'],
    ui_config['numerical'][ui_config['graph_2d_right']
                           ['default_color']]['key'],
    ui_config['numerical'][ui_config['graph_2d_right']['default_x']
                           ]['description'],
    ui_config['numerical'][ui_config['graph_2d_right']['default_y']
                           ]['description'],
    ui_config['numerical'][ui_config['graph_2d_right']['default_color']
                           ]['description']]

layout_params = {
    'x_range': [0, 0],
    'y_range': [0, 0],
    'z_range': [0, 0],
    'c_range': [0, 0],
    'color_key': ui_config['numerical'][
        ui_config['graph_3d_detections']['default_color']
    ]['key'],
    'color_label': ui_config['numerical'][
        ui_config['graph_3d_detections']['default_color']
    ]['description'],
    'db': False,
}

app.layout = html.Div([
    html.Div([
        html.Div([], className="one-third column"),
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
                    dcc.Dropdown(
                        id='color_main',
                        options=[{
                            'label': ui_config[
                                'numerical'][f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                                ui_config['numerical'])],
                        value=ui_config['graph_3d_detections']['default_color']
                    ),
                ], className="two columns"),
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
        # style={'min-height': '100vh',
        #        'max-height': '100vh'}
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
                            'label': ui_config[
                                'numerical'][f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                                ui_config['numerical'])],
                        value=ui_config['graph_2d_left']['default_x'],
                        disabled=True
                    ),
                ], className="one-third column"),
                html.Div([
                    html.Label('y-axis'),
                    dcc.Dropdown(
                        id='y_left',
                        options=[{
                            'label': ui_config[
                                'numerical'][f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                                ui_config['numerical'])],
                        value=ui_config['graph_2d_left']['default_y'],
                        disabled=True
                    ),
                ], className="one-third column"),
                html.Div([
                    html.Label('color'),
                    dcc.Dropdown(
                        id='color_left',
                        options=[{
                            'label': ui_config[
                                'numerical'][f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                                ui_config['numerical'])],
                        value=ui_config['graph_2d_left']['default_color'],
                        disabled=True
                    ),
                ], className="one-third column"),
            ], className="row flex-display"),
            dcc.Graph(
                id='graph_2d_left',
                config={
                    "displaylogo": False
                },
                figure={
                    'data': [{'mode': 'markers', 'type': 'scatter',
                                      'x': [], 'y': []}
                             ],
                    'layout': {
                        'uirevision': 'no_change'
                    }
                },
            ),

            html.Div([
                html.Div([
                ], className="ten columns"),
                html.Div([
                    html.Button('Export', id='export_left', n_clicks=0),
                    html.Div(id="hidden_export_left",
                             style={"display": "none"}),
                ], className="two columns"),
            ], className="row flex-display"),

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
                            'label': ui_config[
                                'numerical'][f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                                ui_config['numerical'])],
                        value=ui_config['graph_2d_right']['default_x'],
                        disabled=True
                    ),
                ], className="one-third column"),
                html.Div([
                    html.Label('y-axis'),
                    dcc.Dropdown(
                        id='y_right',
                        options=[{
                            'label': ui_config[
                                'numerical'][f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                                ui_config['numerical'])],
                        value=ui_config['graph_2d_right']['default_y'],
                        disabled=True
                    ),
                ], className="one-third column"),
                html.Div([
                    html.Label('color'),
                    dcc.Dropdown(
                        id='color_right',
                        options=[{
                            'label': ui_config[
                                'numerical'][f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(
                                ui_config['numerical'])],
                        value=ui_config['graph_2d_right']['default_color'],
                        disabled=True
                    ),
                ], className="one-third column"),
            ], className="row flex-display"),
            dcc.Graph(
                id='graph_2d_right',
                config={
                    "displaylogo": False
                },
                figure={
                    'data': [{'mode': 'markers', 'type': 'scatter',
                                      'x': [], 'y': []}
                             ],
                    'layout': {
                        'uirevision': 'no_change'
                    }
                },
            ),

            html.Div([
                html.Div([
                ], className="ten columns"),
                html.Div([
                    html.Button('Export', id='export_right', n_clicks=0),
                    html.Div(id="hidden_export_right",
                             style={"display": "none"}),
                ], className="two columns"),
            ], className="row flex-display"),
        ], className="pretty_container six columns"),
    ], className="row flex-display"),

    # Hidden div inside the app that stores the intermediate value
    html.Div(id='trigger', style={'display': 'none'}),
    html.Div(id='dummy', style={'display': 'none'}),
    dcc.Interval(id='interval', interval=500),
], style={"display": "flex", "flex-direction": "column"},)


@app.callback(
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
        raise PreventUpdate()


@app.callback(
    Output('det_grid', 'figure'),
    play_bar_callback_input + picker_callback_input + slider_callback_input+[
        Input('color_main', 'value'),
    ],
    [
        State('det_grid', 'figure'),
        State('trigger', 'children')
    ])
def update_filter(*args):
    global layout_params

    global ui_config
    global task_queue

    if processing.is_locked:
        raise PreventUpdate()

    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    slider_arg = args[0]
    categorical_key_values = args[1:(1+len(processing.categorical_key_list))]
    numerical_key_values = args[
        (1+len(processing.categorical_key_list)):
        (1+len(processing.categorical_key_list) +
            len(processing.numerical_key_list))]
    color_key = ui_config['numerical'][
        args[1 + len(processing.categorical_key_list) +
             len(processing.numerical_key_list)]]['key']
    color_label = ui_config['numerical'][
        args[1 +
             len(processing.categorical_key_list) +
             len(processing.numerical_key_list)]]['description']

    if trigger_id == 'slider':
        if processing.get_frame_ready_index() > slider_arg:
            return processing.get_frame(slider_arg)
        else:

            filterd_frame = processing.data[
                processing.data[
                    ui_config['numerical']
                    [
                        ui_config['slider']
                    ]['key']] == processing.frame_idx[slider_arg]
            ]
            filterd_frame = filterd_frame.reset_index()

            for filter_idx, filter_name in enumerate(
                    processing.numerical_key_list):
                if filter_name is not None:
                    filterd_frame = filter_range(
                        filterd_frame,
                        filter_name,
                        numerical_key_values[filter_idx])

            for filter_idx, filter_name in enumerate(
                    processing.categorical_key_list):
                if filter_name is not None:
                    filterd_frame = filter_picker(
                        filterd_frame,
                        filter_name,
                        categorical_key_values[filter_idx])

            return dict(
                data=[get_figure_data(
                    det_list=filterd_frame,
                    x_key=ui_config['numerical'][
                        ui_config['graph_3d_detections']['default_x']
                    ]['key'],
                    y_key=ui_config['numerical'][
                        ui_config['graph_3d_detections']['default_y']
                    ]['key'],
                    z_key=ui_config['numerical'][
                        ui_config['graph_3d_detections']['default_z']
                    ]['key'],
                    color_key=layout_params['color_key'],
                    color_label=layout_params['color_label'],
                    name='Index: ' +
                    str(slider_arg) + ' (' +
                    ui_config['numerical'][ui_config['slider']
                                           ]['description']+')',
                    hover_dict={
                        **ui_config['numerical'], **ui_config['categorical']},
                    c_range=layout_params['c_range'],
                    db=layout_params['db']
                ),
                    get_host_data(
                    det_list=filterd_frame,
                    x_key=ui_config['host'][
                        ui_config['graph_3d_host']['default_x']
                    ]['key'],
                    y_key=ui_config['host'][
                        ui_config['graph_3d_host']['default_y']
                    ]['key'],
                )],
                layout=get_figure_layout(
                    x_range=layout_params['x_range'],
                    y_range=layout_params['y_range'],
                    z_range=layout_params['z_range'])
            )
    else:
        if None not in categorical_key_values:
            x_det = ui_config['numerical'][
                ui_config['graph_3d_detections']['default_x']
            ]['key']
            x_host = ui_config['host'][
                ui_config['graph_3d_host']['default_x']
            ]['key']
            y_det = ui_config['numerical'][
                ui_config['graph_3d_detections']['default_y']
            ]['key']
            y_host = ui_config['host'][
                ui_config['graph_3d_host']['default_y']
            ]['key']
            z_det = ui_config['numerical'][
                ui_config['graph_3d_detections']['default_z']
            ]['key']

            layout_params['x_range'] = [
                np.min([np.min(processing.data[x_det]),
                        np.min(processing.data[x_host])]),
                np.max([np.max(processing.data[x_det]),
                        np.max(processing.data[x_host])])]
            layout_params['y_range'] = [
                np.min([np.min(processing.data[y_det]),
                        np.min(processing.data[y_host])]),
                np.max([np.max(processing.data[y_det]),
                        np.max(processing.data[y_host])])]
            layout_params['z_range'] = [
                np.min(processing.data[z_det]),
                np.max(processing.data[z_det])]
            layout_params['color_key'] = color_key
            layout_params['color_label'] = color_label
            layout_params['c_range'] = [
                np.min(processing.data[color_key]),
                np.max(processing.data[color_key])
            ]

            fig_processing.set_left_outdated()
            fig_processing.set_right_outdated()

            task_queue.put_nowait(
                {
                    'trigger': 'filter',
                    'new_data': False,
                    'cat_values': categorical_key_values,
                    'num_values': numerical_key_values,
                    'layout': layout_params,
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

            for filter_idx, filter_name in enumerate(
                    processing.numerical_key_list):
                if filter_name is not None:
                    filterd_frame = filter_range(
                        filterd_frame,
                        filter_name,
                        numerical_key_values[filter_idx])

            for filter_idx, filter_name in enumerate(
                    processing.categorical_key_list):
                if filter_name is not None:
                    filterd_frame = filter_picker(
                        filterd_frame,
                        filter_name,
                        categorical_key_values[filter_idx])

            return dict(
                data=[get_figure_data(
                    det_list=filterd_frame,
                    x_key=ui_config['numerical'][
                        ui_config['graph_3d_detections']['default_x']
                    ]['key'],
                    y_key=ui_config['numerical'][
                        ui_config['graph_3d_detections']['default_y']
                    ]['key'],
                    z_key=ui_config['numerical'][
                        ui_config['graph_3d_detections']['default_z']
                    ]['key'],
                    color_key=layout_params['color_key'],
                    color_label=layout_params['color_label'],
                    name='Index: ' +
                    str(slider_arg) + ' (' +
                    ui_config['numerical'][ui_config['slider']
                                           ]['description']+')',
                    hover_dict={
                        **ui_config['numerical'], **ui_config['categorical']},
                    c_range=layout_params['c_range'],
                    db=layout_params['db']
                ),
                    get_host_data(
                    det_list=filterd_frame,
                    x_key=ui_config['host'][
                        ui_config['graph_3d_host']['default_x']
                    ]['key'],
                    y_key=ui_config['host'][
                        ui_config['graph_3d_host']['default_y']
                    ]['key'],
                )],
                layout=get_figure_layout(
                    x_range=layout_params['x_range'],
                    y_range=layout_params['y_range'],
                    z_range=layout_params['z_range'])
            )
        else:
            return args[-2]


@app.callback(
    [
        Output('graph_2d_left', 'figure'),
        Output('graph_2d_right', 'figure'),
        Output('interval', 'disabled'),
        Output('x_left', 'disabled'),
        Output('y_left', 'disabled'),
        Output('color_left', 'disabled'),
        Output('x_right', 'disabled'),
        Output('y_right', 'disabled'),
        Output('color_right', 'disabled'),
    ],
    picker_callback_input +
    slider_callback_input +
    [
        Input('left-switch', 'on'),
        Input('x_left', 'value'),
        Input('y_left', 'value'),
        Input('color_left', 'value'),
        Input('right-switch', 'on'),
        Input('x_right', 'value'),
        Input('y_right', 'value'),
        Input('color_right', 'value'),
        Input('interval', 'n_intervals')
    ],
    [
        State('left-switch', 'on'),
        State('right-switch', 'on'),
        State('graph_2d_left', 'figure'),
        State('graph_2d_right', 'figure'),
    ]
)
def update_2d_graphs(*args):
    global left_figure_keys
    global right_figure_keys

    global ui_config

    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    left_fig = args[-2]
    right_fig = args[-1]
    interval_flag = False

    if trigger_id == 'interval' or \
        trigger_id == 'left-switch' or \
            trigger_id == 'right-switch':
        if args[-4] and fig_processing.is_left_figure_ready():
            left_fig = fig_processing.get_left_figure()
        else:
            left_fig = {
                'data': [{'mode': 'markers', 'type': 'scatter',
                          'x': [], 'y': []}
                         ],
                'layout': {
                    'uirevision': 'no_change'
                }}

        if args[-3] and fig_processing.is_right_figure_ready():
            right_fig = fig_processing.get_right_figure()
        else:
            right_fig = {
                'data': [{'mode': 'markers', 'type': 'scatter',
                          'x': [], 'y': []}
                         ],
                'layout': {
                    'uirevision': 'no_change'
                }}

        if fig_processing.is_left_figure_ready() and \
                fig_processing.is_right_figure_ready():
            interval_flag = True
        else:
            interval_flag = False

    elif (trigger_id in ['x_left', 'y_left', 'color_left']) and args[-4]:
        fig_processing.set_left_outdated()

        left_figure_keys = [
            ui_config['numerical'][ctx.inputs['x_left.value']]['key'],
            ui_config['numerical'][ctx.inputs['y_left.value']]['key'],
            ui_config['numerical'][ctx.inputs['color_left.value']]['key'],
            ui_config['numerical'][ctx.inputs['x_left.value']
                                   ]['description'],
            ui_config['numerical'][ctx.inputs['y_left.value']
                                   ]['description'],
            ui_config['numerical'][ctx.inputs['color_left.value']
                                   ]['description']]

        fig_processing.set_left_figure_keys(left_figure_keys)

        fig_task_queue.put_nowait(
            {
                'trigger': 'left_figure',
                'data': processing.get_filtered_data()
            }
        )

        left_fig = {
            'data': [{'mode': 'markers', 'type': 'scatter',
                      'x': [], 'y': []}
                     ],
            'layout': {
                'uirevision': 'no_change'
            }}

        interval_flag = False

    elif (trigger_id in ['x_right', 'y_right', 'color_right']) and args[-3]:
        fig_processing.set_right_outdated()

        right_figure_keys = [
            ui_config['numerical'][
                ctx.inputs['x_right.value']]['key'],
            ui_config['numerical'][
                ctx.inputs['y_right.value']]['key'],
            ui_config['numerical'][
                ctx.inputs['color_right.value']]['key'],
            ui_config['numerical'][
                ctx.inputs['x_right.value']]['description'],
            ui_config['numerical'][
                ctx.inputs['y_right.value']]['description'],
            ui_config['numerical'][
                ctx.inputs['color_right.value']]['description']
        ]

        fig_processing.set_right_figure_keys(right_figure_keys)

        fig_task_queue.put_nowait(
            {
                'trigger': 'right_figure',
                'data': processing.get_filtered_data()
            }
        )
        right_fig = {
            'data': [{'mode': 'markers', 'type': 'scatter',
                      'x': [], 'y': []}
                     ],
            'layout': {
                'uirevision': 'no_change'
            }}

        interval_flag = False

    else:

        left_fig = {
            'data': [{'mode': 'markers', 'type': 'scatter',
                      'x': [], 'y': []}
                     ],
            'layout': {
                'uirevision': 'no_change'
            }}
        right_fig = {
            'data': [{'mode': 'markers', 'type': 'scatter',
                      'x': [], 'y': []}
                     ],
            'layout': {
                'uirevision': 'no_change'
            }}

        interval_flag = False

    if args[-4]:
        left_x_disabled = False
        left_y_disabled = False
        left_color_disabled = False
    else:
        left_x_disabled = True
        left_y_disabled = True
        left_color_disabled = True

    if args[-3]:
        right_x_disabled = False
        right_y_disabled = False
        right_color_disabled = False
    else:
        right_x_disabled = True
        right_y_disabled = True
        right_color_disabled = True

    return [
        left_fig,
        right_fig,
        interval_flag,
        left_x_disabled,
        left_y_disabled,
        left_color_disabled,
        right_x_disabled,
        right_y_disabled,
        right_color_disabled,
    ]


@app.callback(
    play_bar_callback_output +
    picker_callback_output +
    slider_callback_output +
    [
        Output('color_main', 'value'),
        Output('left-switch', 'on'),
        Output('right-switch', 'on'),
    ],
    [
        Input('data_file_picker', 'value')
    ],
    [
        State('test_case_picker', 'value')
    ])
def data_file_selection(data_file_name, test_case):
    global ui_config

    global layout_params

    if data_file_name is not None and test_case is not None:
        new_data = pd.read_pickle(
            './data/'+test_case+'/'+data_file_name)

        layout_params['color_key'] = ui_config['numerical'][
            ui_config['graph_3d_detections']['default_color']
        ]['key']

        layout_params['color_label'] = ui_config['numerical'][
            ui_config['graph_3d_detections']['default_color']
        ]['description']

        layout_params['db'] = False

        x_det = ui_config['numerical'][
            ui_config['graph_3d_detections']['default_x']
        ]['key']
        x_host = ui_config['host'][
            ui_config['graph_3d_host']['default_x']
        ]['key']
        y_det = ui_config['numerical'][
            ui_config['graph_3d_detections']['default_y']
        ]['key']
        y_host = ui_config['host'][
            ui_config['graph_3d_host']['default_y']
        ]['key']
        z_det = ui_config['numerical'][
            ui_config['graph_3d_detections']['default_z']
        ]['key']

        layout_params['x_range'] = [
            np.min([np.min(new_data[x_det]),
                    np.min(new_data[x_host])]),
            np.max([np.max(new_data[x_det]),
                    np.max(new_data[x_host])])]
        layout_params['y_range'] = [
            np.min([np.min(new_data[y_det]),
                    np.min(new_data[y_host])]),
            np.max([np.max(new_data[y_det]),
                    np.max(new_data[y_host])])]
        layout_params['z_range'] = [
            np.min(new_data[z_det]),
            np.max(new_data[z_det])]
        layout_params['c_range'] = [
            np.min(new_data[layout_params['color_key']]),
            np.max(new_data[layout_params['color_key']])
        ]

        frame_idx = new_data[
            ui_config['numerical']
            [ui_config['slider']]['key']].unique()
        output = [0, len(frame_idx)-1, 0]

        for idx, d_item in enumerate(ui_config['categorical']):
            var_list = new_data[ui_config['categorical']
                                [d_item]['key']].unique()

            options = []
            selection = []
            for var in var_list:
                options.append({'label': var, 'value': var})
                selection.append(var)
            output.append(options)
            output.append(selection)

        for idx, s_item in enumerate(ui_config['numerical']):
            var_min = round(
                np.min(new_data[ui_config['numerical'][s_item]['key']]), 1)
            var_max = round(
                np.max(new_data[ui_config['numerical'][s_item]['key']]), 1)

            output.append(var_min)
            output.append(var_max)
            output.append([var_min, var_max])

        output.append(ui_config['graph_3d_detections']['default_color'])
        output.append(False)
        output.append(False)

        left_figure_keys = [
            ui_config['numerical'][ui_config['graph_2d_left']
                                   ['default_x']]['key'],
            ui_config['numerical'][ui_config['graph_2d_left']
                                   ['default_y']]['key'],
            ui_config['numerical'][ui_config['graph_2d_left']
                                   ['default_color']]['key'],
            ui_config['numerical'][ui_config['graph_2d_left']['default_x']
                                   ]['description'],
            ui_config['numerical'][ui_config['graph_2d_left']['default_y']
                                   ]['description'],
            ui_config['numerical'][ui_config['graph_2d_left']['default_color']
                                   ]['description']]

        right_figure_keys = [
            ui_config['numerical'][ui_config['graph_2d_right']
                                   ['default_x']]['key'],
            ui_config['numerical'][ui_config['graph_2d_right']
                                   ['default_y']]['key'],
            ui_config['numerical'][ui_config['graph_2d_right']
                                   ['default_color']]['key'],
            ui_config['numerical'][ui_config['graph_2d_right']['default_x']
                                   ]['description'],
            ui_config['numerical'][ui_config['graph_2d_right']['default_y']
                                   ]['description'],
            ui_config['numerical'][ui_config['graph_2d_right']['default_color']
                                   ]['description']]

        fig_processing.set_left_figure_keys(left_figure_keys)
        fig_processing.set_right_figure_keys(right_figure_keys)

        task_queue.put_nowait(
            {
                'trigger': 'filter',
                'new_data': True,
                'data': new_data,
                'layout': layout_params,
            }
        )

        return output
    else:
        raise PreventUpdate()


@app.callback(
    Output('hidden_export_left', 'children'),
    Input('export_left', 'n_clicks'),
    State('graph_2d_left', 'figure')
)
def export_left_fig(btn, fig):
    if btn > 0:
        temp_fig = go.Figure(fig)
        temp_fig.write_image("images/fig_left.png", scale=2)
    return 0


@app.callback(
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
    fig_processing.start()
    app.run_server(debug=True, threaded=True, processes=1)
