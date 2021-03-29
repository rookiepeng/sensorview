"""

    Copyright (C) 2019 - 2021  Zhengyu Peng
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


import datetime

import redis
import pyarrow as pa

from filter import filter_all

import json
import os

import dash
from dash.dependencies import Input, Output, State, MATCH, ALL
from dash.exceptions import PreventUpdate
import dash_core_components as dcc
import dash_html_components as html

import base64

import numpy as np
import pandas as pd
import os
import plotly.graph_objs as go


from layout import get_app_layout

from viz.viz import get_figure_data, get_figure_layout, get_host_data
from viz.viz import get_2d_scatter, get_histogram, get_heatmap
from viz.viz import get_animation_data


def scatter3d_data(det_list,
                   x,
                   y,
                   z,
                   x_ref,
                   y_ref,
                   layout,
                   keys_dict,
                   name,
                   image=None):

    return dict(
        data=[get_figure_data(
            det_list=det_list,
            x_key=x,
            y_key=y,
            z_key=z,
            color_key=layout['color_key'],
            color_label=layout['color_label'],
            name=name,
            hover_dict=keys_dict,
            c_range=layout['c_range']
        ),
            get_host_data(
            det_list=det_list,
            x_key=x_ref,
            y_key=y_ref,
        )],
        layout=get_figure_layout(
            x_range=layout['x_range'],
            y_range=layout['y_range'],
            z_range=layout['z_range'],
            image=image)
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

redis_instance = redis.StrictRedis.from_url(
    os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379'))

REDIS_HASH_NAME = os.environ.get("DASH_APP_NAME", "SensorView")
REDIS_KEYS = {"DATASET": "DATASET",
              "FRAME_IDX": "FRAME_IDX",
              "VIS": "VIS"}
EXPIRATION = 172800  # a week in seconds

app.layout = get_app_layout(app)

dropdown_options = [
    Output('color-picker-3d', 'options'),
    Output('x-scatter2d-left', 'options'),
    Output('y-scatter2d-left', 'options'),
    Output('color-scatter2d-left', 'options'),
    Output('x-scatter2d-right', 'options'),
    Output('y-scatter2d-right', 'options'),
    Output('color-scatter2d-right', 'options'),
    Output('x-histogram', 'options'),
    Output('x-heatmap', 'options'),
    Output('y-heatmap', 'options'),
]

dropdown_values = [
    Output('color-picker-3d', 'value'),
    Output('x-scatter2d-left', 'value'),
    Output('y-scatter2d-left', 'value'),
    Output('color-scatter2d-left', 'value'),
    Output('x-scatter2d-right', 'value'),
    Output('y-scatter2d-right', 'value'),
    Output('color-scatter2d-right', 'value'),
    Output('x-histogram', 'value'),
    Output('x-heatmap', 'value'),
    Output('y-heatmap', 'value'),
]


@ app.callback(
    [
        Output('test-case', 'options'),
        Output('test-case', 'value'),
    ],
    Input('refresh-case', 'n_clicks')
)
def test_case_refresh(n_clicks):
    options = []
    obj = os.scandir('./data')
    for entry in obj:
        if entry.is_dir():
            options.append({'label': entry.name, 'value': entry.name})

    return [options, options[0]['value']]


@ app.callback([
    Output('data-file', 'value'),
    Output('data-file', 'options'),
    Output('config', 'data'),
    Output('keys-dict', 'data'),
    Output('num-key-list', 'data'),
    Output('cat-key-list', 'data')
] + dropdown_options + dropdown_values,
    [Input('test-case', 'value')])
def test_case_selection(test_case):
    if test_case is not None:
        data_files = []
        obj = os.scandir('./data/'+test_case)
        for entry in obj:
            if entry.is_file():
                if '.pkl' in entry.name:
                    data_files.append({
                        'label': entry.name,
                        'value': entry.name})

        if os.path.exists('./data/'+test_case+'/config.json'):
            ui_config = load_config('./data/'+test_case+'/config.json')
        else:
            ui_config = load_config('config.json')

        keys_dict = ui_config['keys']

        num_keys = []
        cat_keys = []
        for _, s_item in enumerate(keys_dict):
            if keys_dict[s_item].get('type', 'numerical') == 'numerical':
                num_keys.append(s_item)
            else:
                cat_keys.append(s_item)

        options = [[{
            'label': keys_dict[f_item].get('description', f_item),
            'value': f_item}
            for _, f_item in enumerate(keys_dict)
        ]]*len(dropdown_options)

        return [
            data_files[0]['value'],
            data_files,
            ui_config,
            keys_dict,
            num_keys,
            cat_keys]+options+[
            ui_config.get('c_3d', num_keys[2]),
            ui_config.get('x_2d_l', num_keys[0]),
            ui_config.get('y_2d_l', num_keys[1]),
            ui_config.get('c_2d_l', num_keys[2]),
            ui_config.get('x_2d_r', num_keys[0]),
            ui_config.get('y_2d_r', num_keys[1]),
            ui_config.get('c_2d_r', num_keys[2]),
            ui_config.get('x_hist', num_keys[0]),
            ui_config.get('x_heatmap', num_keys[0]),
            ui_config.get('y_heatmap', num_keys[1]),
        ]
    else:
        raise PreventUpdate


@ app.callback(
    [
        Output('slider-frame', 'min'),
        Output('slider-frame', 'max'),
        Output('dropdown-container', 'children'),
        Output('slider-container', 'children'),
    ],
    [
        Input('data-file', 'value'),
    ],
    [
        State('test-case', 'value'),
        State('keys-dict', 'data'),
        State('config', 'data'),
        State('session-id', 'data'),
        State('num-key-list', 'data'),
        State('cat-key-list', 'data'),
    ])
def data_file_selection(
        data_file_name,
        test_case,
        keys_dict,
        ui_config,
        session_id,
        num_keys,
        cat_keys
):
    if data_file_name is not None and test_case is not None:
        new_data = pd.read_pickle(
            './data/'+test_case+'/'+data_file_name)

        vis_table = pd.DataFrame()
        vis_table['_IDS_'] = new_data.index
        vis_table['_VIS_'] = 'visible'

        context = pa.default_serialization_context()
        redis_instance.set(
            REDIS_KEYS["DATASET"]+session_id,
            context.serialize(new_data).to_buffer().to_pybytes(),
            ex=EXPIRATION
        )

        redis_instance.set(
            REDIS_KEYS["VIS"]+session_id,
            context.serialize(vis_table).to_buffer().to_pybytes(),
            ex=EXPIRATION
        )

        frame_idx = new_data[ui_config['slider']].unique()
        frame_idx = np.sort(frame_idx)

        redis_instance.set(
            REDIS_KEYS["FRAME_IDX"]+session_id,
            context.serialize(frame_idx).to_buffer().to_pybytes(),
            ex=EXPIRATION
        )

        output = [0, len(frame_idx)-1]

        cat_values = []
        new_dropdown = []

        for idx, d_item in enumerate(cat_keys):
            var_list = new_data[d_item].unique()
            value_list = var_list

            new_dropdown.append(
                html.Label(
                    keys_dict[d_item]['description']
                )
            )
            new_dropdown.append(
                dcc.Dropdown(
                    id={
                        'type': 'filter-dropdown',
                        'index': idx
                    },
                    options=[{'label': i, 'value': i}
                             for i in var_list],
                    value=value_list,
                    multi=True
                ))

            cat_values.append(value_list)

        num_values = []
        new_slider = []
        for idx, s_item in enumerate(num_keys):
            var_min = round(
                np.min(new_data[s_item]), 1)
            var_max = round(
                np.max(new_data[s_item]), 1)

            new_slider.append(
                html.Label(
                    keys_dict[s_item]['description']
                )
            )
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

            num_values.append([var_min, var_max])

        output.append(new_dropdown)
        output.append(new_slider)

        return output
    else:
        raise PreventUpdate


@ app.callback(
    Output('slider-frame', 'value'),
    [
        Input('slider-frame', 'max'),
        Input('left-frame', 'n_clicks'),
        Input('right-frame', 'n_clicks'),
    ],
    [
        State('slider-frame', 'min'),
        State('slider-frame', 'value'),
    ])
def slider_value_change(
        max_val,
        left_btn,
        right_btn,
        min_val,
        val):
    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if trigger_id == 'left-frame':
        if left_btn > 0 and val > min_val:
            return val-1
        else:
            raise PreventUpdate
    elif trigger_id == 'right-frame':
        if right_btn > 0 and val < max_val:
            return val+1
        else:
            raise PreventUpdate
    elif trigger_id == 'slider-frame':
        return 0


@ app.callback(
    [
        Output('left-switch', 'on'),
        Output('right-switch', 'on'),
        Output('histogram-switch', 'on'),
        Output('heat-switch', 'on'),
    ],
    Input('data-file', 'value'),
    State('test-case', 'value'))
def reset_switch_state(
        data_file_name,
        test_case
):
    if data_file_name is not None and test_case is not None:
        return [False, False, False, False]
    else:
        raise PreventUpdate


@ app.callback(
    [
        Output('cat-key-values', 'data'),
        Output('num-key-values', 'data'),
    ],
    [
        Input({'type': 'filter-dropdown', 'index': ALL}, 'value'),
        Input({'type': 'filter-slider', 'index': ALL}, 'value'),
    ])
def update_filter_values(
    cat_key_values,
    num_key_values,
):
    return [cat_key_values, num_key_values]


@ app.callback(
    [
        Output('scatter3d', 'figure'),
        Output('filter-trigger', 'children'),
    ],
    [
        Input('slider-frame', 'value'),
        Input({'type': 'filter-dropdown', 'index': ALL}, 'value'),
        Input({'type': 'filter-slider', 'index': ALL}, 'value'),
        Input('vis-picker', 'value'),
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
        State('session-id', 'data'),
        State('test-case', 'value'),
        State('data-file', 'value'),
    ])
def update_filter(
    slider_arg,
    categorical_key_values,
    numerical_key_values,
    vis_picker,
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
    session_id,
    test_case,
    data_file,
):
    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    color_key = color_picker
    color_label = keys_dict[color_picker]['description']

    slider_key = ui_config['slider']
    slider_label = keys_dict[ui_config['slider']
                             ]['description']

    x_det = ui_config.get('x_3d', num_keys[0])
    y_det = ui_config.get('y_3d', num_keys[1])
    z_det = ui_config.get('z_3d', num_keys[2])
    x_host = ui_config.get('x_ref', None)
    y_host = ui_config.get('y_ref', None)

    context = pa.default_serialization_context()
    data = context.deserialize(redis_instance.get("DATASET"+session_id))
    vis_table = context.deserialize(redis_instance.get("VIS"+session_id))
    frame_idx = context.deserialize(redis_instance.get("FRAME_IDX"+session_id))

    x_range = [
        np.min([numerical_key_values[num_keys.index(x_det)][0],
                np.min(data[x_host])]),
        np.max([numerical_key_values[num_keys.index(x_det)][1],
                np.max(data[x_host])])]
    y_range = [
        np.min([numerical_key_values[num_keys.index(y_det)][0],
                np.min(data[y_host])]),
        np.max([numerical_key_values[num_keys.index(y_det)][1],
                np.max(data[y_host])])]
    z_range = numerical_key_values[num_keys.index(z_det)]
    c_range = [
        np.min(data[color_key]),
        np.max(data[color_key])
    ]

    scatter3d_layout = dict(
        x_range=x_range,
        y_range=y_range,
        z_range=z_range,
        c_range=c_range,
        color_key=color_key,
        color_label=color_label,
    )

    if trigger_id == 'slider-frame' and not overlay_sw:
        filterd_frame = data[data[slider_key] == frame_idx[slider_arg]]

        img = './data/'+test_case+'/imgs/' + \
            data_file[0:-4]+str(slider_arg)+'.png'

        try:
            encoded_image = base64.b64encode(open(img, 'rb').read())
            source_encoded = 'data:image/png;base64,{}'.format(
                encoded_image.decode())
        except FileNotFoundError:
            source_encoded = None

        filterd_frame = filter_all(
            filterd_frame,
            num_keys,
            numerical_key_values,
            cat_keys,
            categorical_key_values,
            vis_table,
            vis_picker
        )

        fig = scatter3d_data(
            filterd_frame,
            x_det,
            y_det,
            z_det,
            x_host,
            y_host,
            scatter3d_layout,
            keys_dict,
            'Index: ' + str(slider_arg) + ' (' + slider_label+')',
            image=source_encoded
        )

        filter_trig = dash.no_update

    elif trigger_id == 'scatter3d' and visible_sw and \
            click_data['points'][0]['curveNumber'] == 0:

        if vis_table['_VIS_'][
            click_data['points'][0]['id']
        ] == 'visible':
            vis_table.at[click_data['points']
                         [0]['id'], '_VIS_'] = 'hidden'
        else:
            vis_table.at[click_data['points']
                         [0]['id'], '_VIS_'] = 'visible'

        context = pa.default_serialization_context()
        redis_instance.set(
            REDIS_KEYS["VIS"]+session_id,
            context.serialize(vis_table).to_buffer().to_pybytes(),
            ex=EXPIRATION
        )

        if overlay_sw:
            filterd_frame = filter_all(
                data,
                num_keys,
                numerical_key_values,
                cat_keys,
                categorical_key_values,
                vis_table,
                vis_picker
            )

            fig = scatter3d_data(
                filterd_frame,
                x_det,
                y_det,
                z_det,
                x_host,
                y_host,
                scatter3d_layout,
                keys_dict,
                'Index: ' + str(slider_arg) + ' (' + slider_label+')'
            )
            filter_trig = trigger_idx+1

        else:
            filterd_frame = data[
                data[slider_key] == frame_idx[slider_arg]
            ]

            img = './data/'+test_case+'/imgs/' + \
                data_file[0:-4]+str(slider_arg)+'.png'

            try:
                encoded_image = base64.b64encode(open(img, 'rb').read())
                source_encoded = 'data:image/png;base64,{}'.format(
                    encoded_image.decode())
            except FileNotFoundError:
                source_encoded = None

            filterd_frame = filter_all(
                filterd_frame,
                num_keys,
                numerical_key_values,
                cat_keys,
                categorical_key_values,
                vis_table,
                vis_picker
            )

            fig = scatter3d_data(
                filterd_frame,
                x_det,
                y_det,
                z_det,
                x_host,
                y_host,
                scatter3d_layout,
                keys_dict,
                'Index: ' + str(slider_arg) + ' (' + slider_label+')',
                image=source_encoded
            )
            filter_trig = trigger_idx+1

    elif trigger_id == 'left-hide-trigger':

        if overlay_sw:
            filterd_frame = filter_all(
                data,
                num_keys,
                numerical_key_values,
                cat_keys,
                categorical_key_values,
                vis_table,
                vis_picker
            )

            fig = scatter3d_data(
                filterd_frame,
                x_det,
                y_det,
                z_det,
                x_host,
                y_host,
                scatter3d_layout,
                keys_dict,
                'Index: ' + str(slider_arg) + ' (' + slider_label+')'
            )
            filter_trig = dash.no_update

        else:
            filterd_frame = data[
                data[ui_config['slider']] == frame_idx[slider_arg]
            ]

            filterd_frame = filter_all(
                filterd_frame,
                num_keys,
                numerical_key_values,
                cat_keys,
                categorical_key_values,
                vis_table,
                vis_picker
            )

            img = './data/'+test_case+'/imgs/' + \
                data_file[0:-4]+str(slider_arg)+'.png'

            try:
                encoded_image = base64.b64encode(open(img, 'rb').read())
                source_encoded = 'data:image/png;base64,{}'.format(
                    encoded_image.decode())
            except FileNotFoundError:
                source_encoded = None

            fig = scatter3d_data(
                filterd_frame,
                x_det,
                y_det,
                z_det,
                x_host,
                y_host,
                scatter3d_layout,
                keys_dict,
                'Index: ' + str(slider_arg) + ' (' + slider_label+')',
                image=source_encoded
            )
            filter_trig = dash.no_update

    else:
        if None not in categorical_key_values:

            if overlay_sw:
                filterd_frame = filter_all(
                    data,
                    num_keys,
                    numerical_key_values,
                    cat_keys,
                    categorical_key_values,
                    vis_table,
                    vis_picker
                )

                source_encoded = None
            else:
                filterd_frame = data[
                    data[ui_config['slider']] == frame_idx[slider_arg]
                ]

                img = './data/'+test_case+'/imgs/' + \
                    data_file[0:-4]+str(slider_arg)+'.png'

                try:
                    encoded_image = base64.b64encode(open(img, 'rb').read())
                    source_encoded = 'data:image/png;base64,{}'.format(
                        encoded_image.decode())
                except FileNotFoundError:
                    source_encoded = None

                filterd_frame = filter_all(
                    filterd_frame,
                    num_keys,
                    numerical_key_values,
                    cat_keys,
                    categorical_key_values,
                    vis_table,
                    vis_picker
                )
            fig = scatter3d_data(
                filterd_frame,
                x_det,
                y_det,
                z_det,
                x_host,
                y_host,
                scatter3d_layout,
                keys_dict,
                'Index: ' + str(slider_arg) + ' (' + slider_label+')',
                image=source_encoded
            )
            filter_trig = trigger_idx+1
        else:
            raise PreventUpdate

    return [fig, filter_trig]


@ app.callback(
    [
        Output('scatter2d-left', 'figure'),
        Output('x-scatter2d-left', 'disabled'),
        Output('y-scatter2d-left', 'disabled'),
        Output('color-scatter2d-left', 'disabled'),
        Output('colormap-scatter2d-left', 'disabled'),
    ],
    [
        Input('filter-trigger', 'children'),
        Input('left-hide-trigger', 'children'),
        Input('left-switch', 'on'),
        Input('x-scatter2d-left', 'value'),
        Input('y-scatter2d-left', 'value'),
        Input('color-scatter2d-left', 'value'),
        Input('colormap-scatter2d-left', 'value'),
    ],
    [
        State('keys-dict', 'data'),
        State('num-key-list', 'data'),
        State('cat-key-list', 'data'),
        State('cat-key-values', 'data'),
        State('num-key-values', 'data'),
        State('session-id', 'data'),
        State('vis-picker', 'value')
    ]
)
def update_left_graph(
    trigger_idx,
    left_hide_trigger,
    left_sw,
    x_left,
    y_left,
    color_left,
    colormap,
    keys_dict,
    num_keys,
    cat_keys,
    categorical_key_values,
    numerical_key_values,
    session_id,
    vis_picker
):
    x_key = x_left
    y_key = y_left
    color_key = color_left
    x_label = keys_dict[x_left]['description']
    y_label = keys_dict[y_left]['description']
    color_label = keys_dict[color_left]['description']

    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if left_sw:
        context = pa.default_serialization_context()
        data = context.deserialize(redis_instance.get("DATASET"+session_id))
        vis_table = context.deserialize(redis_instance.get("VIS"+session_id))

        filtered_table = filter_all(
            data,
            num_keys,
            numerical_key_values,
            cat_keys,
            categorical_key_values,
            vis_table,
            vis_picker
        )

        left_fig = get_2d_scatter(
            filtered_table,
            x_key,
            y_key,
            color_key,
            x_label,
            y_label,
            color_label,
            colormap=colormap
        )
        left_x_disabled = False
        left_y_disabled = False
        left_color_disabled = False
        colormap_disable = False

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
        colormap_disable = True

    return [
        left_fig,
        left_x_disabled,
        left_y_disabled,
        left_color_disabled,
        colormap_disable
    ]


@ app.callback(
    [
        Output('scatter2d-right', 'figure'),
        Output('x-scatter2d-right', 'disabled'),
        Output('y-scatter2d-right', 'disabled'),
        Output('color-scatter2d-right', 'disabled'),
        Output('colormap-scatter2d-right', 'disabled'),
    ],
    [
        Input('filter-trigger', 'children'),
        Input('left-hide-trigger', 'children'),
        Input('right-switch', 'on'),
        Input('x-scatter2d-right', 'value'),
        Input('y-scatter2d-right', 'value'),
        Input('color-scatter2d-right', 'value'),
        Input('colormap-scatter2d-right', 'value'),
    ],
    [
        State('keys-dict', 'data'),
        State('num-key-list', 'data'),
        State('cat-key-list', 'data'),
        State('cat-key-values', 'data'),
        State('num-key-values', 'data'),
        State('session-id', 'data'),
        State('vis-picker', 'value')
    ]
)
def update_right_graph(
    trigger_idx,
    left_hide_trigger,
    right_sw,
    x_right,
    y_right,
    color_right,
    colormap,
    keys_dict,
    num_keys,
    cat_keys,
    categorical_key_values,
    numerical_key_values,
    session_id,
    vis_picker
):
    x_key = x_right
    y_key = y_right
    color_key = color_right
    x_label = keys_dict[x_right]['description']
    y_label = keys_dict[y_right]['description']
    color_label = keys_dict[color_right]['description']

    if right_sw:
        context = pa.default_serialization_context()
        data = context.deserialize(redis_instance.get("DATASET"+session_id))
        vis_table = context.deserialize(redis_instance.get("VIS"+session_id))
        filtered_table = filter_all(
            data,
            num_keys,
            numerical_key_values,
            cat_keys,
            categorical_key_values,
            vis_table,
            vis_picker
        )

        right_fig = get_2d_scatter(
            filtered_table,
            x_key,
            y_key,
            color_key,
            x_label,
            y_label,
            color_label,
            colormap=colormap
        )
        right_x_disabled = False
        right_y_disabled = False
        right_color_disabled = False
        colormap_disable = False

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
        colormap_disable = True

    return [
        right_fig,
        right_x_disabled,
        right_y_disabled,
        right_color_disabled,
        colormap_disable,
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
        State('session-id', 'data'),
        State('vis-picker', 'value')
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
    numerical_key_values,
    session_id,
    vis_picker
):
    x_key = x_histogram
    x_label = keys_dict[x_histogram]['description']
    y_key = y_histogram

    if histogram_sw:
        context = pa.default_serialization_context()
        data = context.deserialize(redis_instance.get("DATASET"+session_id))
        vis_table = context.deserialize(redis_instance.get("VIS"+session_id))
        filtered_table = filter_all(
            data,
            num_keys,
            numerical_key_values,
            cat_keys,
            categorical_key_values,
            vis_table,
            vis_picker
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
        State('session-id', 'data'),
        State('vis-picker', 'value')
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
    numerical_key_values,
    session_id,
    vis_picker
):
    if heat_sw:
        x_key = x_heat
        x_label = keys_dict[x_heat]['description']
        y_key = y_heat
        y_label = keys_dict[y_heat]['description']
        # if processing.is_filtering_ready():
        context = pa.default_serialization_context()
        data = context.deserialize(redis_instance.get("DATASET"+session_id))
        vis_table = context.deserialize(redis_instance.get("VIS"+session_id))

        filtered_table = filter_all(
            data,
            num_keys,
            numerical_key_values,
            cat_keys,
            categorical_key_values,
            vis_table,
            vis_picker
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
    Output('hidden-scatter3d', 'children'),
    Input('export-scatter3d', 'n_clicks'),
    [
        State('test-case', 'value'),
        State('session-id', 'data'),
        State('keys-dict', 'data'),
        State('color-picker-3d', 'value'),
        State('num-key-list', 'data'),
        State('cat-key-list', 'data'),
        State('cat-key-values', 'data'),
        State('num-key-values', 'data'),
        State('config', 'data'),
        State('vis-picker', 'value')
    ]
)
def export_scatter_3d(
    btn,
    test_case,
    session_id,
    keys_dict,
    color_picker,
    num_keys,
    cat_keys,
    categorical_key_values,
    numerical_key_values,
    ui_config,
    vis_picker
):
    if btn > 0:
        now = datetime.datetime.now()
        timestamp = now.strftime('%Y%m%d_%H%M%S')

        if not os.path.exists('data/'+test_case+'/images'):
            os.makedirs('data/'+test_case+'/images')

        context = pa.default_serialization_context()
        data = context.deserialize(redis_instance.get("DATASET"+session_id))
        vis_table = context.deserialize(redis_instance.get("VIS"+session_id))

        x_det = ui_config.get('x_3d', num_keys[0])
        y_det = ui_config.get('y_3d', num_keys[1])
        z_det = ui_config.get('z_3d', num_keys[2])
        x_host = ui_config.get('x_ref', None)
        y_host = ui_config.get('y_ref', None)

        filtered_table = filter_all(
            data,
            num_keys,
            numerical_key_values,
            cat_keys,
            categorical_key_values,
            vis_table,
            vis_picker
        )

        fig = go.Figure(
            get_animation_data(
                filtered_table,
                x_key=x_det,
                y_key=y_det,
                z_key=z_det,
                host_x_key=x_host,
                host_y_key=y_host,
                color_key=color_picker,
                hover_dict=keys_dict,
                db=False,
                height=700,
                title=test_case
            )
        )

        fig.write_html('data/'+test_case+'/images/' +
                       timestamp+'_3dview.html')
    return 0


@ app.callback(
    Output('hidden-scatter2d-left', 'children'),
    Input('export-scatter2d-left', 'n_clicks'),
    [
        State('scatter2d-left', 'figure'),
        State('test-case', 'value')
    ]
)
def export_left_scatter_2d(btn, fig, test_case):
    if btn > 0:
        now = datetime.datetime.now()
        timestamp = now.strftime('%Y%m%d_%H%M%S')

        if not os.path.exists('data/'+test_case+'/images'):
            os.makedirs('data/'+test_case+'/images')

        temp_fig = go.Figure(fig)
        temp_fig.write_image('data/'+test_case+'/images/' +
                             timestamp+'_fig_left.png', scale=2)
    return 0


@ app.callback(
    Output('hidden-scatter2d-right', 'children'),
    Input('export-scatter2d-right', 'n_clicks'),
    [
        State('scatter2d-right', 'figure'),
        State('test-case', 'value')
    ]
)
def export_right_scatter_2d(btn, fig, test_case):
    if btn > 0:
        now = datetime.datetime.now()
        timestamp = now.strftime('%Y%m%d_%H%M%S')

        if not os.path.exists('data/'+test_case+'/images'):
            os.makedirs('data/'+test_case+'/images')

        temp_fig = go.Figure(fig)
        temp_fig.write_image('data/'+test_case+'/images/' +
                             timestamp+'_fig_right.png', scale=2)
    return 0


@ app.callback(
    Output('hidden-histogram', 'children'),
    Input('export-histogram', 'n_clicks'),
    [
        State('histogram', 'figure'),
        State('test-case', 'value')
    ]
)
def export_histogram(btn, fig, test_case):
    if btn > 0:
        now = datetime.datetime.now()
        timestamp = now.strftime('%Y%m%d_%H%M%S')

        if not os.path.exists('data/'+test_case+'/images'):
            os.makedirs('data/'+test_case+'/images')

        temp_fig = go.Figure(fig)
        temp_fig.write_image('data/'+test_case+'/images/' +
                             timestamp+'_histogram.png', scale=2)
    return 0


@ app.callback(
    Output('hidden-heatmap', 'children'),
    Input('export-heatmap', 'n_clicks'),
    [
        State('heatmap', 'figure'),
        State('test-case', 'value')
    ]
)
def export_heatmap(btn, fig, test_case):
    if btn > 0:
        now = datetime.datetime.now()
        timestamp = now.strftime('%Y%m%d_%H%M%S')

        if not os.path.exists('data/'+test_case+'/images'):
            os.makedirs('data/'+test_case+'/images')

        temp_fig = go.Figure(fig)
        temp_fig.write_image('data/'+test_case+'/images/' +
                             timestamp+'_heatmap.png', scale=2)
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
        State('selected-data-left', 'data'),
        State('left-hide-trigger', 'children'),
        State('session-id', 'data'),
    ]
)
def left_hide_button(
    btn,
    selectedData,
    trigger_idx,
    session_id
):
    if btn > 0 and selectedData is not None:
        context = pa.default_serialization_context()
        # data = context.deserialize(redis_instance.get("DATASET"+session_id))
        vis_table = context.deserialize(redis_instance.get("VIS"+session_id))

        s_data = pd.DataFrame(selectedData['points'])
        idx = s_data['id']
        idx.index = idx

        vis_idx = idx[vis_table['_VIS_'][idx] == 'visible']
        hid_idx = idx[vis_table['_VIS_'][idx] == 'hidden']

        vis_table.loc[vis_idx, '_VIS_'] = 'hidden'
        vis_table.loc[hid_idx, '_VIS_'] = 'visible'

        redis_instance.set(
            REDIS_KEYS["VIS"]+session_id,
            context.serialize(vis_table).to_buffer().to_pybytes(),
            ex=EXPIRATION
        )

        return trigger_idx+1

    else:
        raise PreventUpdate


if __name__ == '__main__':

    app.run_server(debug=True, threaded=True, processes=1, host='0.0.0.0')
