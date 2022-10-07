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

from utils import cache_get, CACHE_KEYS

import plotly.graph_objs as go
from utils import background_callback_manager
from utils import load_data


@app.callback(
    background=True,
    output=dict(
        parallel=Output('parallel', 'figure'),
        collapse=Output('collapse-parallel', 'is_open'),
    ),
    inputs=dict(
        filter_trigger=Input('filter-trigger', 'data'),
        left_hide_trigger=Input('left-hide-trigger', 'data'),
        parallel_sw=Input('parallel-switch', 'value'),
        dim_parallel=Input('dim-picker-parallel', 'value'),
        c_key=Input('c-picker-parallel', 'value')
    ),
    state=dict(
        session_id=State('session-id', 'data'),
        visible_list=State('visible-picker', 'value'),
        case=State('case-picker', 'value'),
        file=State('file-picker', 'value'),
        file_list=State('file-add', 'value')
    ),
    manager=background_callback_manager,
)
def update_parallel(
    filter_trigger,
    left_hide_trigger,
    parallel_sw,
    dim_parallel,
    c_key,
    session_id,
    visible_list,
    case,
    file,
    file_list
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
    filter_kwargs = cache_get(session_id, CACHE_KEYS['filter_kwargs'])
    cat_keys = filter_kwargs['cat_keys']
    num_keys = filter_kwargs['num_keys']
    cat_values = filter_kwargs['cat_values']
    num_values = filter_kwargs['num_values']

    if parallel_sw:
        collapse = True
        if len(dim_parallel) > 0:
            # file = json.loads(file)
            # data = pd.read_feather('./data/' +
            #                        case +
            #                        file['path'] +
            #                        '/' +
            #                        file['feather_name'])
            data = load_data(file, file_list, case)
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
        collapse = False
        parallel_fig = {
            'data': [{'type': 'histogram',
                      'x': []}
                     ],
            'layout': {
            }}

    return dict(
        parallel=parallel_fig,
        collapse=collapse
    )


@app.callback(
    output=dict(
        dummy=Output('dummy-export-parallel', 'data')
    ),
    inputs=dict(
        btn=Input('export-parallel', 'n_clicks')
    ),
    state=dict(
        fig=State('parallel', 'figure'),
        case=State('case-picker', 'value')
    )
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
    return dict(
        dummy=0
    )
