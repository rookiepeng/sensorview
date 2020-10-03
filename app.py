from threading import Thread, Event
from time import sleep

import json
import os

import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.exceptions import PreventUpdate
import numpy as np
import pandas as pd
import os
import plotly.graph_objs as go
import plotly.io as pio

from viz import get_figure

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
det_frames = []
fig_list = []
fig_list_ready = False
filter_trigger = False

layout_params = {
    'x_range': [0, 0],
    'y_range': [0, 0],
    'z_range': [0, 0],
    'c_range': [0, 0],
    'color_assign': 'Speed',
    'db': False,
}


# key_list = ['LookName', 'AFType', 'AzConf',
#                            'ElConf', 'Longitude', 'Latitude',
#                            'Height', 'Speed', 'Range', 'SNR',
#                            'Azimuth', 'Elevation']
# key_values = [[], [], [], [], [0, 0], [0, 0],
#                  [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]]


app.layout = html.Div([
    html.Div([
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
            ], className="pretty_container twelve columns"),
        ], className="row flex-display rows"),
    ], className="eight columns",
        # style={'display': 'inline-block',
        #        'overflow': 'auto'}
    ),

    html.Div([
        html.H4("SensorView"),
        html.P("Sensor detections visualization"),
        html.Br(),
        html.Label('Test Cases'),
        dcc.Dropdown(
            id='test_case_picker',
            options=[{'label': i, 'value': i} for i in test_cases],
            value=test_cases[0]
        ),
        html.Label('Data Files'),
        dcc.Dropdown(
            id='data_file_picker',
            options=[{'label': i, 'value': i} for i in data_files],
            value=data_files[0]
        ),
        html.Br(),
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

        # Hidden div inside the app that stores the intermediate value
        html.Div(id='trigger', style={'display': 'none'}),
        html.Div(id='dummy', style={'display': 'none'}),

    ],
        className="pretty_container four columns",
        # style={'display': 'inline-block',
        #        'overflow': 'auto'}
    )
], className="row flex-display",
    # style={'min-height': '100vh',
    #        'max-height': '100vh'}
)


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
        dash.dependencies.Input('color_assign_picker', 'value'),
    ],
    [
        dash.dependencies.State('det_grid', 'figure'),
        dash.dependencies.State('trigger', 'children')
    ])
# def update_filter(color_assign,
#                   slider_value,
#                   look_type,
#                   rng,
#                   speed,
#                   az,
#                   el,
#                   longitude,
#                   latitude,
#                   height,
#                   snr,
#                   fig,
#                   trigger_state):
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
    slider_callback+picker_callback+filter_callback,
    [
        dash.dependencies.Input('data_file_picker', 'value')
    ],
    [
        dash.dependencies.State('test_case_picker', 'value')
    ])
def update_data_file(data_file_name, test_case):
    global det_list
    global det_frames
    global layout_params
    global key_values
    global fig_list_ready
    global filter_trigger

    look_options = []
    look_selection = []
    af_type_options = []
    af_type_selection = []
    az_conf_options = []
    az_conf_selection = []
    el_conf_options = []
    el_conf_selection = []
    if data_file_name is not None:
        det_list = pd.read_pickle('./data/'+test_case+'/'+data_file_name)

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
        frame_list = det_list['Frame'].unique()
        for frame_idx in frame_list:
            filtered_list = det_list[det_list['Frame'] == frame_idx]
            filtered_list = filtered_list.reset_index()
            det_frames.append(filtered_list)

        look_types = det_list['LookName'].unique()
        for look_name in look_types:
            look_options.append({'label': look_name, 'value': look_name})
            look_selection.append(look_name)

        af_types = det_list['AFType'].unique()
        for af_type in af_types:
            af_type_options.append({'label': af_type, 'value': af_type})
            af_type_selection.append(af_type)

        az_conf = det_list['AzConf'].unique()
        for az_c in az_conf:
            az_conf_options.append({'label': az_c, 'value': az_c})
            az_conf_selection.append(az_c)

        el_conf = det_list['ElConf'].unique()
        for el_c in el_conf:
            el_conf_options.append({'label': el_c, 'value': el_c})
            el_conf_selection.append(el_c)

        longitude_min = round(np.min(det_list['Longitude']), 1)
        longitude_max = round(np.max(det_list['Longitude']), 1)
        latitude_min = round(np.min(det_list['Latitude']), 1)
        latitude_max = round(np.max(det_list['Latitude']), 1)
        height_min = round(np.min(det_list['Height']), 1)
        height_max = round(np.max(det_list['Height']), 1)
        speed_min = round(np.min(det_list['Speed']), 1)
        speed_max = round(np.max(det_list['Speed']), 1)
        range_min = round(np.min(det_list['Range']), 1)
        range_max = round(np.max(det_list['Range']), 1)
        snr_min = round(np.min(det_list['SNR']), 1)
        snr_max = round(np.max(det_list['SNR']), 1)
        az_min = round(np.min(det_list['Azimuth']), 1)
        az_max = round(np.max(det_list['Azimuth']), 1)
        el_min = round(np.min(det_list['Elevation']), 1)
        el_max = round(np.max(det_list['Elevation']), 1)

        key_values = [look_types, [longitude_min, longitude_max],
                      [latitude_min, latitude_max],
                      [height_min, height_max], [speed_min, speed_max],
                      [range_min, range_max], [snr_min, snr_max],
                      [az_min, az_max], [el_min, el_max]]
        fig_list_ready = False
        filter_trigger = True

        return [0,
                len(det_frames)-1,
                0,
                look_options,
                look_selection,
                range_min,
                range_max,
                [range_min, range_max],
                speed_min,
                speed_max,
                [speed_min, speed_max],
                az_min,
                az_max,
                [az_min, az_max],
                el_min,
                el_max,
                [el_min, el_max],
                longitude_min,
                longitude_max,
                [longitude_min, longitude_max],
                latitude_min,
                latitude_max,
                [latitude_min, latitude_max],
                height_min,
                height_max,
                [height_min, height_max],
                snr_min,
                snr_max,
                [snr_min, snr_max]]


class Filtering(Thread):
    def __init__(self):
        Thread.__init__(self)

    def run(self):
        global det_list
        global fig_list
        global fig_list_ready
        global filter_trigger
        global key_list
        global key_values
        global layout_params

        while True:
            if filter_trigger:
                fig_list_ready = False
                is_skipped = False
                filter_trigger = False

                filterd_det_list = det_list
                for filter_idx, filter_name in enumerate(key_list):
                    filterd_det_list = filter_data(
                        filterd_det_list,
                        filter_name,
                        key_values[filter_idx])
                    if filter_trigger:
                        is_skipped = True
                        break

                fig_list = []
                frame_list = det_list['Frame'].unique()
                for idx, frame_idx in enumerate(frame_list):
                    filtered_list = filterd_det_list[
                        filterd_det_list['Frame'] == frame_idx
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
                    fig_list_ready = True

            if not filter_trigger:
                sleep(1)


if __name__ == '__main__':
    plotting = Filtering()
    plotting.start()
    app.run_server(debug=True)
