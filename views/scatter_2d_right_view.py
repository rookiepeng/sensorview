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

from utils import cache_get, CACHE_KEYS, KEY_TYPES

from viz.viz import get_scatter2d

from utils import background_callback_manager

import plotly.graph_objs as go


@app.callback(
    background=True,
    output=dict(
        figure=Output('scatter2d-right', 'figure'),
        collapse=Output('collapse-right2d', 'is_open'),
    ),
    inputs=dict(
        filter_trigger=Input('filter-trigger', 'data'),
        left_hide_trigger=Input('left-hide-trigger', 'data'),
        right_sw=Input('right-switch', 'value'),
        x_right=Input('x-picker-2d-right', 'value'),
        y_right=Input('y-picker-2d-right', 'value'),
        color_right=Input('c-picker-2d-right', 'value'),
        colormap=Input('colormap-scatter2d-right', 'value'),
        outline_enable=Input('outline-switch', 'value')
    ),
    state=dict(
        session_id=State('session-id', 'data'),
        visible_list=State('visible-picker', 'value'),
        case=State('case-picker', 'value'),
        file=State('file-picker', 'value')
    ),
    manager=background_callback_manager,
)
def update_scatter2d_right(
    filter_trigger,
    left_hide_trigger,
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
    config = cache_get(session_id, CACHE_KEYS['config'])
    keys_dict = config['keys']

    filter_kwargs = cache_get(session_id, CACHE_KEYS['filter_kwargs'])
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

    else:
        collapse = False
        right_fig = {
            'data': [{'mode': 'markers',
                      'type': 'scattergl',
                      'x': [],
                      'y': []}
                     ],
            'layout': {
            }}

    return dict(
        figure=right_fig,
        collapse=collapse
    )


@app.callback(
    output=dict(
        dummy=Output('dummy-export-scatter2d-right', 'data')
    ),
    inputs=dict(
        btn=Input('export-scatter2d-right', 'n_clicks')
    ),
    state=dict(
        fig=State('scatter2d-right', 'figure'),
        case=State('case-picker', 'value')
    )
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
    return dict(
        dummy=0
    )
