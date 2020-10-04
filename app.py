from threading import Thread, Event
from time import sleep

import json
import os

import dash
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

from viz import get_figure, get_2d_scatter

app = dash.Dash(__name__,
                meta_tags=[{
                    "name": "viewport",
                    "content": "width=device-width,initial-scale=1"
                }])
app.scripts.config.serve_locally = True
app.css.config.serve_locally = True
app.title = 'SensorView'

with open("ui.json", "r") as read_file:
    ui_config = json.load(read_file)


def gen_rangesliders(ui_config):
    s_list = []
    for idx, s_item in enumerate(ui_config['filter']):
        s_list.append(
            html.Div(id=s_item+'_value',
                     children=ui_config['filter'][s_item]['description']))
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
    for idx, d_item in enumerate(ui_config['picker']):
        d_list.append(html.Label(ui_config['picker'][d_item]['description']))
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

key_list = []
key_values = []

picker_callback = []
picker_input = []
for idx, d_item in enumerate(ui_config['picker']):
    picker_callback.append(
        dash.dependencies.Output(d_item+'_picker', 'options')
    )
    picker_callback.append(
        dash.dependencies.Output(d_item+'_picker', 'value')
    )
    picker_input.append(
        dash.dependencies.Input(d_item+'_picker', 'value')
    )
    key_list.append(ui_config['picker'][d_item]['key'])
    key_values.append([])


filter_callback = []
filter_input = []
for idx, s_item in enumerate(ui_config['filter']):
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

    key_list.append(ui_config['filter'][s_item]['key'])
    key_values.append([0, 0])


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

layout_params = {
    'x_range': [0, 0],
    'y_range': [0, 0],
    'z_range': [0, 0],
    'c_range': [0, 0],
    'color_assign': 'Speed',
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
            html.Label('Test Cases'),
            dcc.Dropdown(
                id='test_case_picker',
                options=[{'label': i, 'value': i} for i in test_cases],
                value=test_cases[0]
            ),
        ], className="pretty_container six column"),

        html.Div([
            html.Label('Data Files'),
            dcc.Dropdown(
                id='data_file_picker',
                options=[{'label': i, 'value': i} for i in data_files],
                value=data_files[0]
            ),
        ], className="pretty_container rix column"),
    ], className="row flex-display"),

    html.Div([

        html.Div([
            html.Label('Color assignment'),
            dcc.Dropdown(
                id='color_assign_picker',
                options=[
                    {'label': 'Speed', 'value': 'Speed'},
                    {'label': 'RCS', 'value': 'RCS'},
                    {'label': 'SNR', 'value': 'SNR'}
                ],
                value='Speed'
            ),
            html.Br(),

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

        html.Div([

            html.Div([
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
            ], className="pretty_container"),

            html.Div([

                html.Div([
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
                            html.Label('x-axis'),
                            dcc.Dropdown(
                                id='x_left',
                                options=[{
                                    'label': ui_config['filter'][f_item]['key'],
                                    'value': ui_config['filter'][f_item]['key']
                                }
                                    for idx, f_item in enumerate(ui_config['filter'])],
                                value=ui_config['graph_2d_left']['default_x']
                            ),
                        ], className="one-third column"),
                        html.Div([
                            html.Label('y-axis'),
                            dcc.Dropdown(
                                id='y_left',
                                options=[{'label': ui_config['filter'][f_item]['key'], 'value': ui_config['filter'][f_item]['key']}
                                         for idx, f_item in enumerate(ui_config['filter'])],
                                value=ui_config['graph_2d_left']['default_y']
                            ),
                        ], className="one-third column"),
                        html.Div([
                            html.Label('color'),
                            dcc.Dropdown(
                                id='color_left',
                                options=[{'label': ui_config['filter'][f_item]['key'], 'value': ui_config['filter'][f_item]['key']}
                                         for idx, f_item in enumerate(ui_config['filter'])],
                                value=ui_config['graph_2d_left']['default_color']
                            ),
                        ], className="one-third column"),
                    ], className="row flex-display")
                ], className="pretty_container six columns"),

                html.Div([
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
                            html.Label('x-axis'),
                            dcc.Dropdown(
                                id='x_right',
                                options=[{'label': ui_config['filter'][f_item]['key'], 'value': ui_config['filter'][f_item]['key']}
                                         for idx, f_item in enumerate(ui_config['filter'])],
                                value=ui_config['graph_2d_right']['default_x']
                            ),
                        ], className="one-third column"),
                        html.Div([
                            html.Label('y-axis'),
                            dcc.Dropdown(
                                id='y_right',
                                options=[{'label': ui_config['filter'][f_item]['key'], 'value': ui_config['filter'][f_item]['key']}
                                         for idx, f_item in enumerate(ui_config['filter'])],
                                value=ui_config['graph_2d_right']['default_y']
                            ),
                        ], className="one-third column"),
                        html.Div([
                            html.Label('color'),
                            dcc.Dropdown(
                                id='color_right',
                                options=[{'label': ui_config['filter'][f_item]['key'], 'value': ui_config['filter'][f_item]['key']}
                                         for idx, f_item in enumerate(ui_config['filter'])],
                                value=ui_config['graph_2d_right']['default_color']
                            ),
                        ], className="one-third column"),
                    ], className="row flex-display")
                ], className="pretty_container six columns"),
            ], className="row flex-display"),


        ], className="nine columns",
            # style={'display': 'inline-block',
            #        'overflow': 'auto'}
        ),


    ], className="row flex-display rows",
        # style={'min-height': '100vh',
        #        'max-height': '100vh'}
    ),

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


def filter_data(data_frame, name, value):
    if name in ['LookName', 'AFType', 'AzConf', 'ElConf']:
        return data_frame[pd.DataFrame(
            data_frame[name].tolist()
        ).isin(value).any(1)].reset_index(drop=True)
    else:
        temp_frame = data_frame[data_frame[name] >= value[0]]
        return temp_frame[
            temp_frame[name] <= value[1]
        ].reset_index(drop=True)


@app.callback(
    dash.dependencies.Output('det_grid', 'figure'),
    slider_input + picker_input + filter_input+[
        dash.dependencies.Input('x_left', 'value'),
        dash.dependencies.Input('y_left', 'value'),
        dash.dependencies.Input('color_left', 'value'),
        dash.dependencies.Input('x_right', 'value'),
        dash.dependencies.Input('y_right', 'value'),
        dash.dependencies.Input('color_right', 'value'),
        dash.dependencies.Input('color_assign_picker', 'value'),
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
    global key_list
    global key_values
    global layout_params

    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if trigger_id == 'slider':
        if fig_list_ready:
            return fig_list[args[0]]
        else:
            filterd_frame = det_frames[args[0]]
            for filter_idx, filter_name in enumerate(key_list):
                filterd_frame = filter_data(
                    filterd_frame, filter_name, key_values[filter_idx])

            return get_figure(filterd_frame,
                              layout_params['x_range'],
                              layout_params['y_range'],
                              layout_params['z_range'],
                              layout_params['color_assign'],
                              layout_params['c_range'],
                              layout_params['db'])
    else:
        if None not in args[0:len(ctx.inputs_list)]:
            key_values = args[1:(len(ctx.inputs_list)-1)]
            layout_params['x_range'] = [np.min([np.min(det_list['Latitude']),
                                                np.min(det_list['VehLat'])]),
                                        np.max([np.max(det_list['Latitude']),
                                                np.max(det_list['VehLat'])])]
            layout_params['y_range'] = [np.min([np.min(det_list['Longitude']),
                                                np.min(det_list['VehLong'])]),
                                        np.max([np.max(det_list['Longitude']),
                                                np.max(det_list['VehLong'])])]
            layout_params['z_range'] = [np.min(det_list['Height']),
                                        np.max(det_list['Height'])]
            layout_params['color_assign'] = args[len(ctx.inputs_list)-1]
            layout_params['c_range'] = [np.min(det_list[args[len(ctx.inputs_list)-1]]),
                                        np.max(det_list[args[len(ctx.inputs_list)-1]])]

            filter_trigger = True
            fig_list_ready = False

            filterd_frame = det_frames[args[0]]

            for filter_idx, filter_name in enumerate(key_list):
                filterd_frame = filter_data(
                    filterd_frame, filter_name, key_values[filter_idx])

            return get_figure(filterd_frame,
                              layout_params['x_range'],
                              layout_params['y_range'],
                              layout_params['z_range'],
                              layout_params['color_assign'],
                              layout_params['c_range'],
                              layout_params['db'])
        else:
            return args[-2]


@app.callback(
    [
        dash.dependencies.Output('graph_2d_left', 'figure'),
        dash.dependencies.Output('graph_2d_right', 'figure'),
        Output('interval', 'disabled')
    ],
    picker_input+filter_input+[
        dash.dependencies.Input('x_left', 'value'),
        dash.dependencies.Input('y_left', 'value'),
        dash.dependencies.Input('color_left', 'value'),
        dash.dependencies.Input('x_right', 'value'),
        dash.dependencies.Input('y_right', 'value'),
        dash.dependencies.Input('color_right', 'value'),
        Input('interval', 'n_intervals')
    ],
    [
        State('graph_2d_left', 'figure'),
        State('graph_2d_right', 'figure'),
    ]
)
def update_2d_graphs(*args):
    global det_list
    global fig_list
    global det_frames
    global fig_list_ready
    global filter_trigger
    global key_list
    global key_values
    global layout_params

    global filtered_det
    global filter_done

    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if trigger_id == 'interval':
        if filter_done:
            return [
                get_2d_scatter(
                    filtered_det, ctx.inputs['x_left.value'], ctx.inputs['y_left.value'], ctx.inputs['color_left.value']),
                get_2d_scatter(filtered_det, ctx.inputs['x_right.value'],
                               ctx.inputs['y_right.value'], ctx.inputs['color_right.value'],
                               ),
                True
            ]
        else:
            raise PreventUpdate()
    elif (trigger_id in ['x_left', 'y_left', 'color_left', 'x_right', 'y_right', 'color_right']):
        return [
            get_2d_scatter(
                filtered_det, ctx.inputs['x_left.value'], ctx.inputs['y_left.value'], ctx.inputs['color_left.value']),
            get_2d_scatter(filtered_det, ctx.inputs['x_right.value'],
                           ctx.inputs['y_right.value'], ctx.inputs['color_right.value'],
                           ),
            True
        ]
    else:
        return [
            args[-2],
            args[-1],
            False
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
    global filtered_det
    global det_frames
    global layout_params
    global key_values
    global fig_list_ready
    global filter_trigger

    if data_file_name is not None:
        det_list = pd.read_pickle('./data/'+test_case+'/'+data_file_name)
        filtered_det = det_list

        layout_params['x_range'] = [np.min([np.min(det_list['Latitude']),
                                            np.min(det_list['VehLat'])]),
                                    np.max([np.max(det_list['Latitude']),
                                            np.max(det_list['VehLat'])])]
        layout_params['y_range'] = [np.min([np.min(det_list['Longitude']),
                                            np.min(det_list['VehLong'])]),
                                    np.max([np.max(det_list['Longitude']),
                                            np.max(det_list['VehLong'])])]
        layout_params['z_range'] = [np.min(det_list['Height']),
                                    np.max(det_list['Height'])]
        layout_params['c_range'] = [
            np.min(det_list[layout_params['color_assign']]),
            np.max(det_list[layout_params['color_assign']])
        ]

        det_frames = []
        frame_list = det_list[ui_config['slider']].unique()
        for frame_idx in frame_list:
            filtered_list = det_list[det_list[ui_config['slider']] == frame_idx]
            filtered_list = filtered_list.reset_index()
            det_frames.append(filtered_list)

        output = [0, len(det_frames)-1, 0]

        key_values = []
        for idx, d_item in enumerate(ui_config['picker']):
            var_list = det_list[ui_config['picker'][d_item]['key']].unique()
            key_values.append(var_list)

            options = []
            selection = []
            for var in var_list:
                options.append({'label': var, 'value': var})
                selection.append(var)
            output.append(options)
            output.append(selection)

        for idx, s_item in enumerate(ui_config['filter']):
            var_min = round(
                np.min(det_list[ui_config['filter'][s_item]['key']]), 1)
            var_max = round(
                np.max(det_list[ui_config['filter'][s_item]['key']]), 1)

            output.append(var_min)
            output.append(var_max)
            output.append([var_min, var_max])

            key_values.append([var_min, var_max])

        fig_list_ready = False
        filter_trigger = True

        return output


class Filtering(Thread):
    def __init__(self):
        Thread.__init__(self)

    def run(self):
        global det_list
        global filtered_det
        global fig_list
        global fig_list_ready
        global filter_trigger
        global key_list
        global key_values
        global layout_params
        global filter_done

        while True:
            if filter_trigger:
                filter_done = False
                fig_list_ready = False
                is_skipped = False
                filter_trigger = False

                filtered_det = det_list
                for filter_idx, filter_name in enumerate(key_list):
                    filtered_det = filter_data(
                        filtered_det,
                        filter_name,
                        key_values[filter_idx])
                    if filter_trigger:
                        is_skipped = True
                        break

                fig_list = []
                frame_list = det_list['Frame'].unique()
                for idx, frame_idx in enumerate(frame_list):
                    filtered_list = filtered_det[
                        filtered_det['Frame'] == frame_idx
                    ]
                    filtered_list = filtered_list.reset_index()
                    fig_list.append(get_figure(filtered_list,
                                               layout_params['x_range'],
                                               layout_params['y_range'],
                                               layout_params['z_range'],
                                               layout_params['color_assign'],
                                               layout_params['c_range'],
                                               layout_params['db']))
                    if filter_trigger:
                        is_skipped = True
                        break

                if not is_skipped:
                    filter_done = True
                    fig_list_ready = True

            if not filter_trigger:
                sleep(1)


if __name__ == '__main__':
    plotting = Filtering()
    plotting.start()
    app.run_server(debug=True)
