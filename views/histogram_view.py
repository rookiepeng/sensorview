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
from utils import background_callback_manager_figure


@app.callback(
    background=True,
    output=dict(
        histogram=Output('histogram', 'figure'),
        collapse=Output('collapse-hist', 'is_open'),
    ),
    inputs=dict(
        filter_trigger=Input('filter-trigger', 'data'),
        left_hide_trigger=Input('left-hide-trigger', 'data'),
        histogram_sw=Input('histogram-switch', 'value'),
        x_histogram=Input('x-picker-histogram', 'value'),
        y_histogram=Input('y-histogram', 'value'),
        c_histogram=Input('c-picker-histogram', 'value')
    ),
    state=dict(
        session_id=State('session-id', 'data'),
        visible_list=State('visible-picker', 'value'),
        case=State('case-picker', 'value'),
        file=State('file-picker', 'value')
    ),
    manager=background_callback_manager_figure,
)
def update_histogram(
    filter_trigger,
    left_hide_trigger,
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

    filter_kwargs = cache_get(session_id, CACHE_KEYS['filter_kwargs'])
    cat_keys = filter_kwargs['cat_keys']
    num_keys = filter_kwargs['num_keys']
    cat_values = filter_kwargs['cat_values']
    num_values = filter_kwargs['num_values']

    x_key = x_histogram
    x_label = config['keys'][x_histogram]['description']
    y_key = y_histogram

    if histogram_sw:
        collapse = True
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
                histogram_fig = px.histogram(
                    filtered_table,
                    x=x_key,
                    histnorm=y_key,
                    opacity=1,
                    barmode='group',
                    nbins=nbins,
                    labels={x_key: x_label,
                            y_key: y_label})
            else:
                histogram_fig = px.histogram(
                    filtered_table,
                    x=x_key,
                    histnorm=y_key,
                    opacity=1,
                    barmode='group',
                    labels={x_key: x_label,
                            y_key: y_label})
        else:
            if x_key == config['slider']:
                nbins = pd.unique(filtered_table[x_key]).size
                histogram_fig = px.histogram(
                    filtered_table,
                    x=x_key,
                    color=c_histogram,
                    histnorm=y_key,
                    opacity=1,
                    barmode='group',
                    nbins=nbins,
                    labels={x_key: x_label,
                            y_key: y_label})
            else:
                histogram_fig = px.histogram(
                    filtered_table,
                    x=x_key,
                    color=c_histogram,
                    histnorm=y_key,
                    opacity=1,
                    barmode='group',
                    labels={x_key: x_label,
                            y_key: y_label})
    else:
        collapse = False
        histogram_fig = {
            'data': [{'type': 'histogram',
                      'x': []}
                     ],
            'layout': {
            }}

    return dict(
        histogram=histogram_fig,
        collapse=collapse
    )


@app.callback(
    output=dict(
        dummy=Output('dummy-export-histogram', 'data')
    ),
    inputs=dict(
        btn=Input('export-histogram', 'n_clicks')
    ),
    state=dict(
        fig=State('histogram', 'figure'),
        case=State('case-picker', 'value')
    )
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
    return dict(
        dummy=0
    )
