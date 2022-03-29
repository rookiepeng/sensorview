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

from utils import cache_get, CACHE_KEYS

import plotly.graph_objs as go
import plotly.express as px


@app.callback(
    [
        Output('histogram', 'figure'),
    ],
    [
        Input('filter-trigger', 'data'),
        Input('left-hide-trigger', 'data'),
        Input('histogram-switch', 'value'),
        Input('x-picker-histogram', 'value'),
        Input('y-histogram', 'value'),
        Input('c-picker-histogram', 'value'),
    ],
    [
        State('session-id', 'data'),
        State('visible-picker', 'value'),
        State('case-picker', 'value'),
        State('file-picker', 'value'),
    ]
)
def update_histogram(
    unused1,
    unused2,
    histogram_sw,
    x_histogram,
    y_histogram,
    c_histogram,
    session_id,
    visible_list,
    case,
    file
):
    """
    Update histogram

    :param int unused1
        unused trigger data
    :param int unused2
        unused trigger data
    :param boolean histogram_sw
        flag to indicate if this graph is enabled or disabled
    :param str x_histogram
        key for the x-axis
    :param str y_histogram
        key for the y-axis
    :param str c_histogram
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
        Histogram graph,
        X axis picker enable/disable,
        Y axis picker enable/disable,
        Color picker enable/disable,
    ]
    :rtype: list
    """
    config = cache_get(session_id, CACHE_KEYS['config'])
    print(config)

    filter_kwargs = cache_get(session_id, CACHE_KEYS['filter_kwargs'])
    cat_keys = filter_kwargs['cat_keys']
    num_keys = filter_kwargs['num_keys']
    cat_values = filter_kwargs['cat_values']
    num_values = filter_kwargs['num_values']

    x_key = x_histogram
    x_label = config['keys'][x_histogram]['description']
    y_key = y_histogram

    if histogram_sw:
        file = json.loads(file)
        data = pd.read_feather('./data/' +
                               case +
                               file['path'] +
                               '/' +
                               file['feather_name'])
        visible_table = cache_get(session_id, CACHE_KEYS['visible_table'])
        filtered_table = filter_all(
            data,
            num_keys,
            num_values,
            cat_keys,
            cat_values,
            visible_table,
            visible_list
        )

        if y_key == 'probability':
            y_label = 'Probability'
        elif y_key == 'density':
            y_label = 'Density'
        if c_histogram == 'None':
            if x_key == config['slider']:
                nbins = pd.unique(filtered_table[x_key]).size
                histogram_fig = px.histogram(filtered_table,
                                             x=x_key,
                                             histnorm=y_key,
                                             opacity=1,
                                             barmode='group',
                                             nbins=nbins,
                                             labels={x_key: x_label,
                                                     y_key: y_label})
            else:
                histogram_fig = px.histogram(filtered_table,
                                             x=x_key,
                                             histnorm=y_key,
                                             opacity=1,
                                             barmode='group',
                                             labels={x_key: x_label,
                                                     y_key: y_label})
        else:
            if x_key == config['slider']:
                nbins = pd.unique(filtered_table[x_key]).size
                histogram_fig = px.histogram(filtered_table,
                                             x=x_key,
                                             color=c_histogram,
                                             histnorm=y_key,
                                             opacity=1,
                                             barmode='group',
                                             nbins=nbins,
                                             labels={x_key: x_label,
                                                     y_key: y_label})
            else:
                histogram_fig = px.histogram(filtered_table,
                                             x=x_key,
                                             color=c_histogram,
                                             histnorm=y_key,
                                             opacity=1,
                                             barmode='group',
                                             labels={x_key: x_label,
                                                     y_key: y_label})
    else:
        histogram_fig = {
            'data': [{'type': 'histogram',
                      'x': []}
                     ],
            'layout': {
            }}

    return [
        histogram_fig,
    ]


@app.callback(
    Output('dummy-export-histogram', 'data'),
    Input('export-histogram', 'n_clicks'),
    [
        State('histogram', 'figure'),
        State('case-picker', 'value')
    ]
)
def export_histogram(btn, fig, case):
    """
    Export histogram into a png

    :param int btn
        number of clicks
    :param graph fig
        histogram
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
                         timestamp+'_histogram.png', scale=2)
    return 0
