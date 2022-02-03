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
import numpy as np

from maindash import app
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from tasks import filter_all

from utils import redis_get, REDIS_KEYS

import plotly.graph_objs as go


@app.callback(
    [
        Output('parallel', 'figure'),
    ],
    [
        Input('filter-trigger', 'data'),
        Input('left-hide-trigger', 'data'),
        Input('parallel-switch', 'value'),
        Input('dim-picker-parallel', 'value'),
        Input('c-picker-parallel', 'value'),
    ],
    [
        State('session-id', 'data'),
        State('visible-picker', 'value'),
        State('case-picker', 'value'),
        State('file-picker', 'value'),
    ]
)
def update_parallel(
    unused1,
    unused2,
    parallel_sw,
    dim_parallel,
    c_key,
    session_id,
    visible_list,
    case,
    file
):
    """
    Update parallel categories diagram

    :param int unused1
        unused trigger data
    :param int unused2
        unused trigger data
    :param boolean parallel_sw
        flag to indicate if this graph is enabled or disabled
    :param str dim_parallel
        keys of the dimensions
    :param str c_key
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
        Parallel categories diagram,
        Dimensions picker enable/disable,
        Color picker enable/disable,
    ]
    :rtype: list
    """
    filter_kwargs = redis_get(session_id, REDIS_KEYS['filter_kwargs'])
    cat_keys = filter_kwargs['cat_keys']
    num_keys = filter_kwargs['num_keys']
    cat_values = filter_kwargs['cat_values']
    num_values = filter_kwargs['num_values']

    if parallel_sw:
        if len(dim_parallel) > 0:
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

            dims = []
            for _, dim_key in enumerate(dim_parallel):
                dims.append(go.parcats.Dimension(
                    values=filtered_table[dim_key], label=dim_key))

            if c_key != 'None':
                unique_list = np.sort(filtered_table[c_key].unique())

                if np.issubdtype(unique_list.dtype, np.integer) or \
                        np.issubdtype(unique_list.dtype, np.floating):
                    parallel_fig = go.Figure(
                        data=[go.Parcats(dimensions=dims,
                                         line={'color': filtered_table[c_key],
                                               'colorbar':dict(
                                             title=c_key)},
                                         hoveron='color',
                                         hoverinfo='count+probability',
                                         arrangement='freeform')])
                else:
                    filtered_table['_C_'] = np.zeros_like(
                        filtered_table[c_key])
                    for idx, var in enumerate(unique_list):
                        filtered_table.loc[filtered_table[c_key]
                                           == var, '_C_'] = idx

                    parallel_fig = go.Figure(
                        data=[go.Parcats(dimensions=dims,
                                         line={'color': filtered_table['_C_']},
                                         hoverinfo='count+probability',
                                         arrangement='freeform')])
            else:
                parallel_fig = go.Figure(
                    data=[go.Parcats(dimensions=dims,
                                     arrangement='freeform')])
        else:
            parallel_fig = {
                'data': [{'type': 'histogram',
                          'x': []}
                         ],
                'layout': {
                }}
    else:
        parallel_fig = {
            'data': [{'type': 'histogram',
                      'x': []}
                     ],
            'layout': {
            }}

    return [
        parallel_fig,
    ]


@app.callback(
    Output('dummy-export-parallel', 'data'),
    Input('export-parallel', 'n_clicks'),
    [
        State('parallel', 'figure'),
        State('case-picker', 'value')
    ]
)
def export_parallel(btn, fig, case):
    """
    Export parallel categories plot into a png

    :param int btn
        number of clicks
    :param graph fig
        parallel categories plot
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
                         timestamp+'_parallel.png', scale=2)
    return 0
