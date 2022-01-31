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

import plotly.express as px
import plotly.graph_objs as go


@app.callback(
    [
        Output('violin', 'figure'),
        Output('x-picker-violin', 'disabled'),
        Output('y-picker-violin', 'disabled'),
        Output('c-picker-violin', 'disabled'),
    ],
    [
        Input('filter-trigger', 'data'),
        Input('left-hide-trigger', 'data'),
        Input('violin-switch', 'value'),
        Input('x-picker-violin', 'value'),
        Input('y-picker-violin', 'value'),
        Input('c-picker-violin', 'value'),
    ],
    [
        State('session-id', 'data'),
        State('visible-picker', 'value'),
        State('case-picker', 'value'),
        State('file-picker', 'value'),
    ]
)
def update_violin(
    unused1,
    unused2,
    violin_sw,
    x_violin,
    y_violin,
    c_violin,
    session_id,
    visible_list,
    case,
    file
):
    """
    Update violin plot

    :param int unused1
        unused trigger data
    :param int unused2
        unused trigger data
    :param boolean violin_sw
        flag to indicate if this graph is enabled or disabled
    :param str x_violin
        key for the x-axis
    :param str y_violin
        key for the y-axis
    :param str c_violin
        key for the color
    :param str session_id
        session id
    :param list visible_list
        visibility list
    :param str case
        case name
    :param json file
        selected file

    :return: [
        Violin graph,
        X axis picker enable/disable,
        Y axis picker enable/disable,
        Color picker enable/disable,
    ]
    :rtype: list
    """
    config = redis_get(session_id, REDIS_KEYS['config'])

    filter_kwargs = redis_get(session_id, REDIS_KEYS['filter_kwargs'])
    cat_keys = filter_kwargs['cat_keys']
    num_keys = filter_kwargs['num_keys']
    cat_values = filter_kwargs['cat_values']
    num_values = filter_kwargs['num_values']

    x_key = x_violin
    if x_violin is None:
        raise PreventUpdate

    x_label = config['keys'][x_violin].get('description', x_key)
    y_key = y_violin
    y_label = config['keys'][y_violin].get('description', y_key)

    if violin_sw:
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

        if c_violin == 'None':
            violin_fig = px.violin(filtered_table,
                                   x=x_key,
                                   y=y_key,
                                   box=True,
                                   violinmode='group',
                                   labels={x_key: x_label,
                                           y_key: y_label})
        else:
            violin_fig = px.violin(filtered_table,
                                   x=x_key,
                                   y=y_key,
                                   color=c_violin,
                                   box=True,
                                   violinmode='group',
                                   labels={x_key: x_label,
                                           y_key: y_label})
        violin_x_disabled = False
        violin_y_disabled = False
        violin_c_disabled = False
    else:
        violin_fig = {
            'data': [{'type': 'histogram',
                      'x': []}
                     ],
            'layout': {
            }}
        violin_x_disabled = True
        violin_y_disabled = True
        violin_c_disabled = True

    return [
        violin_fig,
        violin_x_disabled,
        violin_y_disabled,
        violin_c_disabled
    ]


@app.callback(
    Output('dummy-export-violin', 'data'),
    Input('export-violin', 'n_clicks'),
    [
        State('violin', 'figure'),
        State('case-picker', 'value')
    ]
)
def export_violin(btn, fig, case):
    """
    Export violin plot into a png

    :param int btn
        number of clicks
    :param graph fig
        violin plot
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
                         timestamp+'_violin.png', scale=2)
    return 0
