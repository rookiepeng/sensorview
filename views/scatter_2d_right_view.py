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

import json
import os

import datetime

import pandas as pd

from maindash import app
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from tasks import filter_all

from utils import redis_get, REDIS_KEYS, KEY_TYPES

from viz.viz import get_scatter2d

import plotly.graph_objs as go


@app.callback(
    [
        Output('scatter2d-right', 'figure'),
        Output('x-picker-2d-right', 'disabled'),
        Output('y-picker-2d-right', 'disabled'),
        Output('c-picker-2d-right', 'disabled'),
        Output('colormap-scatter2d-right', 'disabled'),
    ],
    [
        Input('filter-trigger', 'data'),
        Input('left-hide-trigger', 'data'),
        Input('right-switch', 'value'),
        Input('x-picker-2d-right', 'value'),
        Input('y-picker-2d-right', 'value'),
        Input('c-picker-2d-right', 'value'),
        Input('colormap-scatter2d-right', 'value'),
        Input('outline-switch', 'value'),
    ],
    [
        State('session-id', 'data'),
        State('visible-picker', 'value'),
        State('case-picker', 'value'),
        State('file-picker', 'value'),
    ]
)
def update_scatter2d_right(
    unused1,
    unused2,
    right_sw,
    x_right,
    y_right,
    color_right,
    colormap,
    outline_enable,
    session_id,
    visible_list,
    case,
    file
):
    """
    Update right 2D scatter graph

    :param int unused1
        unused trigger data
    :param int unused2
        unused trigger data
    :param boolean left_sw
        flag to indicate if this graph is enabled or disabled
    :param str x_left
        key for the x-axis
    :param str y_left
        key for the y-axis
    :param str color_left
        key for the color
    :param str colormap
        colormap name
    :param boolean outline_enable
        flag to enable outline for the scatters
    :param str session_id
        session id
    :param list visible_list
        visibility list
    :param str case
        case name
    :param json file
        selected file

    :return: [
        2D Scatter graph,
        X axis picker enable/disable,
        Y axis picker enable/disable,
        Color picker enable/disable,
        Colormap picker enable/disable
    ]
    :rtype: list
    """
    config = redis_get(session_id, REDIS_KEYS['config'])
    keys_dict = config['keys']

    filter_kwargs = redis_get(session_id, REDIS_KEYS['filter_kwargs'])
    cat_keys = filter_kwargs['cat_keys']
    num_keys = filter_kwargs['num_keys']
    cat_values = filter_kwargs['cat_values']
    num_values = filter_kwargs['num_values']

    x_key = x_right
    y_key = y_right
    c_key = color_right
    x_label = keys_dict[x_right]['description']
    y_label = keys_dict[y_right]['description']
    c_label = keys_dict[color_right]['description']

    if outline_enable:
        linewidth = 1
    else:
        linewidth = 0

    if right_sw:
        file = json.loads(file)
        data = pd.read_feather('./data/' +
                               case +
                               file['path'] +
                               '/' +
                               file['feather_name'])
        visible_table = redis_get(session_id, REDIS_KEYS['visible_table'])
        filtered_table = filter_all(
            data,
            num_keys,
            num_values,
            cat_keys,
            cat_values,
            visible_table,
            visible_list
        )

        right_fig = get_scatter2d(
            filtered_table,
            x_key,
            y_key,
            c_key,
            x_label,
            y_label,
            c_label,
            colormap=colormap,
            linewidth=linewidth,
            c_type=keys_dict[c_key].get('type', KEY_TYPES['NUM'])
        )
        right_x_disabled = False
        right_y_disabled = False
        right_color_disabled = False
        colormap_disable = False

    else:
        right_fig = {
            'data': [{'mode': 'markers',
                      'type': 'scattergl',
                      'x': [],
                      'y': []}
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


@app.callback(
    Output('dummy-export-scatter2d-right', 'data'),
    Input('export-scatter2d-right', 'n_clicks'),
    [
        State('scatter2d-right', 'figure'),
        State('case-picker', 'value')
    ]
)
def export_right_2d_scatter(btn, fig, case):
    """
    Export 2D scatter into a png

    :param int btn
        number of clicks
    :param graph fig
        2D figure
    :param str case
        case name

    :return: dummy
    :rtype: int
    """
    if btn == 0:
        raise PreventUpdate

    now = datetime.datetime.now()
    timestamp = now.strftime('%Y%m%d_%H%M%S')

    if not os.path.exists('data/'+case+'/images'):
        os.makedirs('data/'+case+'/images')

    temp_fig = go.Figure(fig)
    temp_fig.write_image('data/'+case+'/images/' +
                         timestamp+'_fig_right.png', scale=2)
    return 0