from threading import Thread, Event
from queue import Queue
from time import sleep

from pandas.core.frame import DataFrame

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
from numpy.lib.function_base import append
import pandas as pd
import os
import plotly.graph_objs as go
import plotly.io as pio

from viz import get_2d_scatter, get_figure_data, get_figure_layout, get_host_data


def filter_data(data_frame, name, value):
    if name in ['LookType', 'AFType', 'AzConf', 'ElConf']:
        return data_frame[pd.DataFrame(
            data_frame[name].tolist()
        ).isin(value).any(1)].reset_index(drop=True)
    else:
        temp_frame = data_frame[data_frame[name] >= value[0]]
        return temp_frame[
            temp_frame[name] <= value[1]
        ].reset_index(drop=True)


app = dash.Dash(__name__,
                meta_tags=[{
                    "name": "viewport",
                    "content": "width=device-width,initial-scale=1"
                }])
app.scripts.config.serve_locally = True
app.css.config.serve_locally = True
app.title = 'SensorView'

task_queue = Queue()
fig_task_queue = Queue()

processing = DataProcessing(task_queue, fig_task_queue)
fig_processing = FigureProcessing(fig_task_queue)

with open("ui.json", "r") as read_file:
    ui_config = json.load(read_file)


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


slider_callback = [
    dash.dependencies.Output('slider', 'min'),
    dash.dependencies.Output('slider', 'max'),
    dash.dependencies.Output('slider', 'value'),
]

slider_input = [
    dash.dependencies.Input('slider', 'value')
]


categorical_key_list = []
numerical_key_list = []
key_list = []
key_values = []

picker_callback = []
picker_input = []
for idx, d_item in enumerate(ui_config['categorical']):
    picker_callback.append(
        dash.dependencies.Output(d_item+'_picker', 'options')
    )
    picker_callback.append(
        dash.dependencies.Output(d_item+'_picker', 'value')
    )
    picker_input.append(
        dash.dependencies.Input(d_item+'_picker', 'value')
    )
    key_list.append(ui_config['categorical'][d_item]['key'])
    key_values.append([])

    categorical_key_list.append(ui_config['categorical'][d_item]['key'])


filter_callback = []
filter_input = []
for idx, s_item in enumerate(ui_config['numerical']):
    filter_callback.append(
        dash.dependencies.Output(s_item+'_filter', 'min')
    )
    filter_callback.append(
        dash.dependencies.Output(s_item+'_filter', 'max')
    )
    filter_callback.append(
        dash.dependencies.Output(s_item+'_filter', 'value')
    )
    filter_input.append(
        dash.dependencies.Input(s_item+'_filter', 'value')
    )

    key_list.append(ui_config['numerical'][s_item]['key'])
    key_values.append([0, 0])

    numerical_key_list.append(ui_config['numerical'][s_item]['key'])


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

det_list = pd.DataFrame()
filtered_det = pd.DataFrame()
det_frames = []
fig_list = []
fig_list_ready = False
filter_trigger = False
filter_done = False


left_figure = {
    'data': [{'mode': 'markers', 'type': 'scatter',
              'x': [], 'y': []}
             ],
    'layout': {
        'uirevision': 'no_change'
    }}
left_figure_keys = [
    ui_config['numerical'][ui_config['graph_2d_left']['default_x']]['key'],
    ui_config['numerical'][ui_config['graph_2d_left']['default_y']]['key'],
    ui_config['numerical'][ui_config['graph_2d_left']['default_color']]['key'],
    ui_config['numerical'][ui_config['graph_2d_left']
                           ['default_x']]['description'],
    ui_config['numerical'][ui_config['graph_2d_left']
                           ['default_y']]['description'],
    ui_config['numerical'][ui_config['graph_2d_left']['default_color']]['description']]
right_figure = {
    'data': [{'mode': 'markers', 'type': 'scatter',
              'x': [], 'y': []}
             ],
    'layout': {
        'uirevision': 'no_change'
    }}
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
left_figure_ready = True
right_figure_ready = True

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
            # style={'display': 'inline-block',
            #        'overflow': 'auto'}
        ),

        # html.Div([

        html.Div([

            html.Div([
                html.Div([
                    html.H6('3D View'),
                ], className="ten columns"),
                html.Div([
                    dcc.Dropdown(
                        id='color_main',
                        options=[{
                            'label': ui_config['numerical'][f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(ui_config['numerical'])],
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

        # ], className="nine columns",
        #     # style={'display': 'inline-block',
        #     #        'overflow': 'auto'}
        # ),

    ], className="row flex-display rows",
        # style={'min-height': '100vh',
        #        'max-height': '100vh'}
    ),

    html.Div([
        html.Div([
            daq.BooleanSwitch(
                id='left-switch',
                on=False
            ),
            html.Div([
                html.Div([
                    html.Label('x-axis'),
                    dcc.Dropdown(
                        id='x_left',
                        options=[{
                            'label': ui_config['numerical'][f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(ui_config['numerical'])],
                        value=ui_config['graph_2d_left']['default_x']
                    ),
                ], className="one-third column"),
                html.Div([
                    html.Label('y-axis'),
                    dcc.Dropdown(
                        id='y_left',
                        options=[{
                            'label': ui_config['numerical'][f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(ui_config['numerical'])],
                        value=ui_config['graph_2d_left']['default_y']
                    ),
                ], className="one-third column"),
                html.Div([
                    html.Label('color'),
                    dcc.Dropdown(
                        id='color_left',
                        options=[{
                            'label': ui_config['numerical'][f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(ui_config['numerical'])],
                        value=ui_config['graph_2d_left']['default_color']
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
            daq.BooleanSwitch(
                id='right-switch',
                on=False
            ),
            html.Div([
                html.Div([
                    html.Label('x-axis'),
                    dcc.Dropdown(
                        id='x_right',
                        options=[{
                            'label': ui_config['numerical'][f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(ui_config['numerical'])],
                        value=ui_config['graph_2d_right']['default_x']
                    ),
                ], className="one-third column"),
                html.Div([
                    html.Label('y-axis'),
                    dcc.Dropdown(
                        id='y_right',
                        options=[{
                            'label': ui_config['numerical'][f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(ui_config['numerical'])],
                        value=ui_config['graph_2d_right']['default_y']
                    ),
                ], className="one-third column"),
                html.Div([
                    html.Label('color'),
                    dcc.Dropdown(
                        id='color_right',
                        options=[{
                            'label': ui_config['numerical'][f_item]['description'],
                            'value': f_item
                        }
                            for idx, f_item in enumerate(ui_config['numerical'])],
                        value=ui_config['graph_2d_right']['default_color']
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
        dash.dependencies.Output('data_file_picker', 'value'),
        dash.dependencies.Output('data_file_picker', 'options'),
    ],
    [
        dash.dependencies.Input('test_case_picker', 'value')
    ])
def update_test_case(test_case):
    data_files = []
    for r, d, f in os.walk('./data/'+test_case):
        for file in f:
            if '.pkl' in file:
                data_files.append(file)
        break

    return data_files[0], [{'label': i, 'value': i} for i in data_files]


@app.callback(
    dash.dependencies.Output('det_grid', 'figure'),
    slider_input + picker_input + filter_input+[
        dash.dependencies.Input('color_main', 'value'),
    ],
    [
        dash.dependencies.State('det_grid', 'figure'),
        dash.dependencies.State('trigger', 'children')
    ])
def update_filter(*args):
    global fig_list
    global det_frames
    global fig_list_ready
    global filter_trigger

    global numerical_key_list
    global categorical_key_list
    global key_list
    global key_values
    global layout_params

    global ui_config
    global task_queue

    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    slider_arg = args[0]
    categorical_args = args[1:(1+len(categorical_key_list))]
    numerical_args = args[
        (1+len(categorical_key_list)):
        (1+len(categorical_key_list)+len(numerical_key_list))]
    color_key = ui_config['numerical'][
        args[1 + len(categorical_key_list)+len(numerical_key_list)]]['key']
    color_label = ui_config['numerical'][
        args[1 + len(categorical_key_list)+len(numerical_key_list)]]['description']

    if trigger_id == 'slider':
        if processing.is_frame_list_ready():
            print('get frame '+str(slider_arg))
            return processing.get_frame(slider_arg)
        else:
            filterd_frame = det_frames[slider_arg]
            for filter_idx, filter_name in enumerate(key_list):
                filterd_frame = filter_data(
                    filterd_frame, filter_name, key_values[filter_idx])

            return dict(
                data=[get_figure_data(
                    det_list=filterd_frame,
                    x_key='Latitude',
                    y_key='Longitude',
                    z_key='Height',
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
                    x_key='HostLatitude',
                    y_key='HostLongitude',
                )],
                layout=get_figure_layout(
                    x_range=layout_params['x_range'],
                    y_range=layout_params['y_range'],
                    z_range=layout_params['z_range'])
            )
    else:
        if None not in categorical_args:
            key_values = categorical_args+numerical_args
            layout_params['x_range'] = [np.min([np.min(det_list['Latitude']),
                                                np.min(det_list['HostLatitude'])]),
                                        np.max([np.max(det_list['Latitude']),
                                                np.max(det_list['HostLatitude'])])]
            layout_params['y_range'] = [np.min([np.min(det_list['Longitude']),
                                                np.min(det_list['HostLongitude'])]),
                                        np.max([np.max(det_list['Longitude']),
                                                np.max(det_list['HostLongitude'])])]
            layout_params['z_range'] = [np.min(det_list['Height']),
                                        np.max(det_list['Height'])]
            layout_params['color_key'] = color_key
            layout_params['color_label'] = color_label
            layout_params['c_range'] = [
                np.min(det_list[color_key]),
                np.max(det_list[color_key])
            ]

            filter_trigger = True
            fig_list_ready = False

            fig_processing.set_left_outdated()
            fig_processing.set_right_outdated()

            task_queue.put_nowait(
                {
                    'trigger': 'filter',
                    'data': det_list,
                    'key_list': key_list,
                    'key_values': key_values,
                    'layout': layout_params,
                    'config': ui_config
                }
            )

            filterd_frame = det_frames[slider_arg]

            for filter_idx, filter_name in enumerate(key_list):
                filterd_frame = filter_data(
                    filterd_frame, filter_name, key_values[filter_idx])

            return dict(
                data=[get_figure_data(
                    det_list=filterd_frame,
                    x_key='Latitude',
                    y_key='Longitude',
                    z_key='Height',
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
                    x_key='HostLatitude',
                    y_key='HostLongitude',
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
        dash.dependencies.Output('graph_2d_left', 'figure'),
        dash.dependencies.Output('graph_2d_right', 'figure'),
        Output('interval', 'disabled')
    ],
    picker_input+filter_input+[
        Input('left-switch', 'on'),
        dash.dependencies.Input('x_left', 'value'),
        dash.dependencies.Input('y_left', 'value'),
        dash.dependencies.Input('color_left', 'value'),
        Input('right-switch', 'on'),
        dash.dependencies.Input('x_right', 'value'),
        dash.dependencies.Input('y_right', 'value'),
        dash.dependencies.Input('color_right', 'value'),
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

    if trigger_id == 'interval' or trigger_id == 'left-switch' or trigger_id == 'right-switch':
        if not fig_processing.is_left_outdated():
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

            if fig_processing.is_left_figure_ready() and fig_processing.is_right_figure_ready():
                interval_flag = True
            else:
                interval_flag = False

    elif (trigger_id in ['x_left', 'y_left', 'color_left']) and args[-4]:
        fig_processing.set_left_outdated()
        fig_processing.set_right_outdated()
        # if processing.is_filtering_ready():
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

        fig_processing.set_left_outdated()
        fig_processing.set_right_outdated()
        # if processing.is_filtering_ready():
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

        fig_processing.set_right_figure_keys(keys)

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

    return [
        left_fig,
        right_fig,
        interval_flag
    ]


@app.callback(
    slider_callback+picker_callback+filter_callback,
    [
        dash.dependencies.Input('data_file_picker', 'value')
    ],
    [
        dash.dependencies.State('test_case_picker', 'value')
    ])
def update_data_file(data_file_name, test_case):
    global ui_config
    global det_list
    global det_frames
    global layout_params
    global key_list
    global key_values
    global ui_config

    if data_file_name is not None:
        det_list = pd.read_pickle('./data/'+test_case+'/'+data_file_name)

        layout_params['x_range'] = [np.min([np.min(det_list['Latitude']),
                                            np.min(det_list['HostLatitude'])]),
                                    np.max([np.max(det_list['Latitude']),
                                            np.max(det_list['HostLatitude'])])]
        layout_params['y_range'] = [np.min([np.min(det_list['Longitude']),
                                            np.min(det_list['HostLongitude'])]),
                                    np.max([np.max(det_list['Longitude']),
                                            np.max(det_list['HostLongitude'])])]
        layout_params['z_range'] = [np.min(det_list['Height']),
                                    np.max(det_list['Height'])]
        layout_params['c_range'] = [
            np.min(det_list[layout_params['color_key']]),
            np.max(det_list[layout_params['color_key']])
        ]

        det_frames = []
        frame_list = det_list[ui_config['numerical']
                              [ui_config['slider']]['key']].unique()
        for frame_idx in frame_list:
            filtered_list = det_list[
                det_list[ui_config['numerical']
                         [ui_config['slider']]['key']] == frame_idx
            ]
            filtered_list = filtered_list.reset_index()
            det_frames.append(filtered_list)

        output = [0, len(det_frames)-1, 0]

        key_values = []
        for idx, d_item in enumerate(ui_config['categorical']):
            var_list = det_list[ui_config['categorical']
                                [d_item]['key']].unique()
            key_values.append(var_list)

            options = []
            selection = []
            for var in var_list:
                options.append({'label': var, 'value': var})
                selection.append(var)
            output.append(options)
            output.append(selection)

        for idx, s_item in enumerate(ui_config['numerical']):
            var_min = round(
                np.min(det_list[ui_config['numerical'][s_item]['key']]), 1)
            var_max = round(
                np.max(det_list[ui_config['numerical'][s_item]['key']]), 1)

            output.append(var_min)
            output.append(var_max)
            output.append([var_min, var_max])

            key_values.append([var_min, var_max])

        left_figure_keys = [ui_config['numerical'][ui_config['graph_2d_left']['default_x']]['key'],
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

        right_figure_keys = [ui_config['numerical'][ui_config['graph_2d_right']['default_x']]['key'],
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
                'data': det_list,
                'key_list': key_list,
                'key_values': key_values,
                'layout': layout_params,
                'config': ui_config
            }
        )

        return output


@app.callback(
    Output('hidden_export_left', 'children'),
    Input('export_left', 'n_clicks'),
    State('graph_2d_left', 'figure')
)
def export_left_fig(btn, fig):
    temp_fig = go.Figure(fig)
    temp_fig.write_image("images/fig_left.png", scale=2)
    return 0


@app.callback(
    Output('hidden_export_right', 'children'),
    Input('export_right', 'n_clicks'),
    State('graph_2d_right', 'figure')
)
def export_right_fig(btn, fig):
    temp_fig = go.Figure(fig)
    temp_fig.write_image("images/fig_right.png", scale=2)
    return 0


if __name__ == '__main__':

    processing.start()
    fig_processing.start()
    app.run_server(debug=True, threaded=True, processes=1)
