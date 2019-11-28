from threading import Thread, Event
from time import sleep

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
app.title = 'Radar Viz'

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


filter_list = ['LookName', 'AFType', 'AzConf',
                           'ElConf', 'Longitude', 'Latitude',
                           'Height', 'Speed', 'Range', 'SNR',
                           'Azimuth', 'Elevation']
filter_values = [[], [], [], [], [0, 0], [0, 0],
                 [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]]

app.layout = html.Div([
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
                id='frame_slider',
                step=1,
                value=0,
                updatemode='drag',
            )], style={'box-sizing': 'border-box',
                       'width': '100%',
                       'display': 'inline-block',
                       'padding': '2rem 0rem'})
    ], style={'box-sizing': 'border-box',
              'width': '75%',
              'display': 'inline-block',
              'padding': '4rem 4rem',
              'max-height': '100vh',
              'overflow': 'auto', }),

    html.Div([
        html.H4("Radar Viz"),
        html.P("Radar detections visualization"),
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
        html.Label('Look Type'),
        dcc.Dropdown(
            id='look_type_picker',
            multi=True
        ),
        html.Label('AF Type'),
        dcc.Dropdown(
            id='af_type_picker',
            multi=True
        ),
        html.Label('AF Azimuth Confidence Level'),
        dcc.Dropdown(
            id='az_conf_picker',
            multi=True
        ),
        html.Label('AF Elevation Confidence Level'),
        dcc.Dropdown(
            id='el_conf_picker',
            multi=True
        ),
        html.Label(id='longitude_value',
                   children='Longitude Range'),
        dcc.RangeSlider(
            id='longitude_filter',
            count=1,
            min=0,
            max=10,
            step=0.5,
            value=[0, 10],
            tooltip={'always_visible': False}
        ),
        html.Label(id='latitude_value',
                   children='Latitude Range'),
        dcc.RangeSlider(
            id='latitude_filter',
            count=1,
            min=0,
            max=10,
            step=0.5,
            value=[0, 10],
            tooltip={'always_visible': False}
        ),
        html.Label(id='height_value',
                   children='Height Range'),
        dcc.RangeSlider(
            id='height_filter',
            count=1,
            min=0,
            max=10,
            step=0.5,
            value=[0, 10],
            tooltip={'always_visible': False}
        ),
        html.Label('Speed filter'),
        dcc.RangeSlider(
            id='speed_filter',
            count=1,
            min=0,
            max=10,
            step=0.5,
            value=[0, 10],
            tooltip={'always_visible': False}
        ),
        html.Label('Range filter'),
        dcc.RangeSlider(
            id='range_filter',
            count=1,
            min=0,
            max=10,
            step=0.5,
            value=[0, 10],
            tooltip={'always_visible': False}
        ),
        html.Label('SNR filter'),
        dcc.RangeSlider(
            id='snr_filter',
            count=1,
            min=0,
            max=10,
            step=0.5,
            value=[0, 10],
            tooltip={'always_visible': False}
        ),
        html.Label('Azimuth filter'),
        dcc.RangeSlider(
            id='az_filter',
            count=1,
            min=0,
            max=10,
            step=0.5,
            value=[0, 10],
            tooltip={'always_visible': False}
        ),
        html.Label('Elevation filter'),
        dcc.RangeSlider(
            id='el_filter',
            count=1,
            min=0,
            max=10,
            step=0.5,
            value=[0, 10],
            tooltip={'always_visible': False}
        ),
        # Hidden div inside the app that stores the intermediate value
        html.Div(id='trigger', style={'display': 'none'}),
        html.Div(id='dummy', style={'display': 'none'}),
    ], style={'box-sizing': 'border-box',
              'width': '25%',
              'display': 'inline-block',
              'vertical-align': 'top',
              'padding': '2rem 4rem',
              'margin': '0 0',
              'background-color': '#EEEEEE',
              'max-height': '100vh',
              'overflow': 'auto',
              })
], style={'border-width': '0',
          'box-sizing': 'border-box',
          'display': 'flex',
          'padding': '0rem 0rem',
          'background-color': '#111111',
          'min-height': '100vh',
          'max-height': '100vh',
          #   'overflow-y': 'scroll',
          #   'overflow': 'scroll'
          })


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
    [
        dash.dependencies.Input('color_assign_picker', 'value'),
        dash.dependencies.Input('frame_slider', 'value'),
        dash.dependencies.Input('look_type_picker', 'value'),
        dash.dependencies.Input('af_type_picker', 'value'),
        dash.dependencies.Input('az_conf_picker', 'value'),
        dash.dependencies.Input('el_conf_picker', 'value'),
        dash.dependencies.Input('longitude_filter', 'value'),
        dash.dependencies.Input('latitude_filter', 'value'),
        dash.dependencies.Input('height_filter', 'value'),
        dash.dependencies.Input('speed_filter', 'value'),
        dash.dependencies.Input('range_filter', 'value'),
        dash.dependencies.Input('snr_filter', 'value'),
        dash.dependencies.Input('az_filter', 'value'),
        dash.dependencies.Input('el_filter', 'value'),
    ],
    [
        dash.dependencies.State('det_grid', 'figure'),
        dash.dependencies.State('trigger', 'children')
    ])
def update_filter(color_assign,
                  frame_slider_value,
                  look_type,
                  af_type,
                  az_conf,
                  el_conf,
                  longitude,
                  latitude,
                  height,
                  speed,
                  rng,
                  snr,
                  az,
                  el,
                  fig,
                  trigger_state):
    global fig_list
    global det_frames
    global fig_list_ready
    global filter_trigger
    global filter_list
    global filter_values
    global layout_params

    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if trigger_id == 'frame_slider':
        if fig_list_ready:
            return fig_list[frame_slider_value]
        else:
            filterd_frame = det_frames[frame_slider_value]
            for filter_idx, filter_name in enumerate(filter_list):
                filterd_frame = filter_data(
                    filterd_frame, filter_name, filter_values[filter_idx])

            return get_figure(filterd_frame,
                              layout_params['x_range'],
                              layout_params['y_range'],
                              layout_params['z_range'],
                              layout_params['color_assign'],
                              layout_params['c_range'],
                              layout_params['db'])
    else:
        if None not in [look_type, af_type, az_conf, el_conf]:
            filter_values = [look_type, af_type,
                             az_conf, el_conf, longitude, latitude,
                             height, speed, rng, snr, az, el]
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
            layout_params['color_assign'] = color_assign
            layout_params['c_range'] = [np.min(det_list[color_assign]),
                                        np.max(det_list[color_assign])]

            filter_trigger = True
            fig_list_ready = False

            filterd_frame = det_frames[frame_slider_value]

            for filter_idx, filter_name in enumerate(filter_list):
                filterd_frame = filter_data(
                    filterd_frame, filter_name, filter_values[filter_idx])

            return get_figure(filterd_frame,
                              layout_params['x_range'],
                              layout_params['y_range'],
                              layout_params['z_range'],
                              layout_params['color_assign'],
                              layout_params['c_range'],
                              layout_params['db'])
        else:
            return fig


@app.callback(
    [
        dash.dependencies.Output('frame_slider', 'min'),
        dash.dependencies.Output('frame_slider', 'max'),
        dash.dependencies.Output('frame_slider', 'value'),
        dash.dependencies.Output('look_type_picker', 'options'),
        dash.dependencies.Output('look_type_picker', 'value'),
        dash.dependencies.Output('af_type_picker', 'options'),
        dash.dependencies.Output('af_type_picker', 'value'),
        dash.dependencies.Output('az_conf_picker', 'options'),
        dash.dependencies.Output('az_conf_picker', 'value'),
        dash.dependencies.Output('el_conf_picker', 'options'),
        dash.dependencies.Output('el_conf_picker', 'value'),
        dash.dependencies.Output('longitude_filter', 'min'),
        dash.dependencies.Output('longitude_filter', 'max'),
        dash.dependencies.Output('longitude_filter', 'value'),
        dash.dependencies.Output('latitude_filter', 'min'),
        dash.dependencies.Output('latitude_filter', 'max'),
        dash.dependencies.Output('latitude_filter', 'value'),
        dash.dependencies.Output('height_filter', 'min'),
        dash.dependencies.Output('height_filter', 'max'),
        dash.dependencies.Output('height_filter', 'value'),
        dash.dependencies.Output('speed_filter', 'min'),
        dash.dependencies.Output('speed_filter', 'max'),
        dash.dependencies.Output('speed_filter', 'value'),
        dash.dependencies.Output('range_filter', 'min'),
        dash.dependencies.Output('range_filter', 'max'),
        dash.dependencies.Output('range_filter', 'value'),
        dash.dependencies.Output('snr_filter', 'min'),
        dash.dependencies.Output('snr_filter', 'max'),
        dash.dependencies.Output('snr_filter', 'value'),
        dash.dependencies.Output('az_filter', 'min'),
        dash.dependencies.Output('az_filter', 'max'),
        dash.dependencies.Output('az_filter', 'value'),
        dash.dependencies.Output('el_filter', 'min'),
        dash.dependencies.Output('el_filter', 'max'),
        dash.dependencies.Output('el_filter', 'value'),
    ],
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

        filter_values = [look_types, af_types,
                         az_conf, el_conf, [longitude_min, longitude_max],
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
                af_type_options,
                af_type_selection,
                az_conf_options,
                az_conf_selection,
                el_conf_options,
                el_conf_selection,
                longitude_min,
                longitude_max,
                [longitude_min, longitude_max],
                latitude_min,
                latitude_max,
                [latitude_min, latitude_max],
                height_min,
                height_max,
                [height_min, height_max],
                speed_min,
                speed_max,
                [speed_min, speed_max],
                range_min,
                range_max,
                [range_min, range_max],
                snr_min,
                snr_max,
                [snr_min, snr_max],
                az_min,
                az_max,
                [az_min, az_max],
                el_min,
                el_max,
                [el_min, el_max]]


class Filtering(Thread):
    def __init__(self):
        Thread.__init__(self)

    def run(self):
        global det_list
        global fig_list
        global fig_list_ready
        global filter_trigger
        global filter_list
        global filter_values
        global layout_params

        while True:
            if filter_trigger:
                fig_list_ready = False
                is_skipped = False
                filter_trigger = False

                filterd_det_list = det_list
                for filter_idx, filter_name in enumerate(filter_list):
                    filterd_det_list = filter_data(
                        filterd_det_list,
                        filter_name,
                        filter_values[filter_idx])
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
