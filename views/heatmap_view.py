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

from utils import redis_get, REDIS_KEYS

import plotly.graph_objs as go
from viz.viz import get_heatmap


@app.callback(
    [
        Output('heatmap', 'figure'),
        Output('x-picker-heatmap', 'disabled'),
        Output('y-picker-heatmap', 'disabled'),
    ],
    [
        Input('filter-trigger', 'data'),
        Input('left-hide-trigger', 'data'),
        Input('heat-switch', 'value'),
        Input('x-picker-heatmap', 'value'),
        Input('y-picker-heatmap', 'value'),
    ],
    [
        State('session-id', 'data'),
        State('visible-picker', 'value'),
        State('case-picker', 'value'),
        State('file-picker', 'value'),
    ]
)
def update_heatmap(
    unused1,
    unused2,
    heat_sw,
    x_heat,
    y_heat,
    session_id,
    visible_list,
    case,
    file
):
    """
    Update heatmap

    :param int unused1
        unused trigger data
    :param int unused2
        unused trigger data
    :param boolean heat_sw
        flag to indicate if this graph is enabled or disabled
    :param str x_heat
        key for the x-axis
    :param str y_heat
        key for the y-axis
    :param str session_id
        session id
    :param list visible_list
        visibility list
    :param str case
        case name
    :param json file
        selected file

    :return: [
        Heatmap,
        X axis picker enable/disable,
        Y axis picker enable/disable
    ]
    :rtype: list
    """
    if heat_sw:
        config = redis_get(session_id, REDIS_KEYS['config'])

        filter_kwargs = redis_get(session_id, REDIS_KEYS['filter_kwargs'])
        cat_keys = filter_kwargs['cat_keys']
        num_keys = filter_kwargs['num_keys']
        cat_values = filter_kwargs['cat_values']
        num_values = filter_kwargs['num_values']

        x_key = x_heat
        x_label = config['keys'][x_heat]['description']
        y_key = y_heat
        y_label = config['keys'][y_heat]['description']

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


@app.callback(
    Output('dummy-export-heatmap', 'data'),
    Input('export-heatmap', 'n_clicks'),
    [
        State('heatmap', 'figure'),
        State('case-picker', 'value')
    ]
)
def export_heatmap(btn, fig, case):
    """
    Export heatmap into a png

    :param int btn
        number of clicks
    :param graph fig
        heatmap
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
                         timestamp+'_heatmap.png', scale=2)
    return 0
