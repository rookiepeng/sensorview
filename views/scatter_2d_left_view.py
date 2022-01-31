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

from utils import redis_set, redis_get, REDIS_KEYS, KEY_TYPES

from viz.viz import get_scatter2d

import plotly.graph_objs as go


@app.callback(
    [
        Output('scatter2d-left', 'figure'),
        Output('x-picker-2d-left', 'disabled'),
        Output('y-picker-2d-left', 'disabled'),
        Output('c-picker-2d-left', 'disabled'),
        Output('colormap-scatter2d-left', 'disabled'),
    ],
    [
        Input('filter-trigger', 'data'),
        Input('left-hide-trigger', 'data'),
        Input('left-switch', 'value'),
        Input('x-picker-2d-left', 'value'),
        Input('y-picker-2d-left', 'value'),
        Input('c-picker-2d-left', 'value'),
        Input('colormap-scatter2d-left', 'value'),
        Input('outline-switch', 'value'),
    ],
    [
        State('session-id', 'data'),
        State('visible-picker', 'value'),
        State('case-picker', 'value'),
        State('file-picker', 'value'),
    ]
)
def update_scatter2d_left(
    unused1,
    unused2,
    left_sw,
    x_left,
    y_left,
    color_left,
    colormap,
    outline_enable,
    session_id,
    visible_list,
    case,
    file
):
    """
    Update left 2D scatter graph

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

    filter_kwargs = redis_get(session_id, REDIS_KEYS['filter_kwargs'])
    cat_keys = filter_kwargs['cat_keys']
    num_keys = filter_kwargs['num_keys']
    cat_values = filter_kwargs['cat_values']
    num_values = filter_kwargs['num_values']

    x_key = x_left
    y_key = y_left
    c_key = color_left
    x_label = config['keys'][x_left]['description']
    y_label = config['keys'][y_left]['description']
    c_label = config['keys'][color_left]['description']

    if outline_enable:
        linewidth = 1
    else:
        linewidth = 0

    if left_sw:
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

        left_fig = get_scatter2d(
            filtered_table,
            x_key,
            y_key,
            c_key,
            x_label,
            y_label,
            c_label,
            colormap=colormap,
            linewidth=linewidth,
            c_type=config['keys'][c_key].get('type', KEY_TYPES['NUM'])
        )
        left_x_disabled = False
        left_y_disabled = False
        left_color_disabled = False
        colormap_disable = False

    else:
        left_fig = {
            'data': [{'mode': 'markers',
                      'type': 'scattergl',
                      'x': [],
                      'y': []}
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


@app.callback(
    Output('dummy-export-scatter2d-left', 'data'),
    Input('export-scatter2d-left', 'n_clicks'),
    [
        State('scatter2d-left', 'figure'),
        State('case-picker', 'value')
    ]
)
def export_left_2d_scatter(btn, fig, case):
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
                         timestamp+'_fig_left.png', scale=2)
    return 0


@app.callback(
    Output('selected-data-left', 'data'),
    Input('scatter2d-left', 'selectedData'),
    State('session-id', 'data'),
)
def select_left_figure(selectedData, session_id):
    """
    Callback when data selected on the left 2D scatter

    :param json selectedData
        selected data
    :param str session_id
        session id

    :return: selected data
    :rtype: json
    """
    redis_set(selectedData, session_id, REDIS_KEYS['selected_data'])
    return 0


@app.callback(
    Output('left-hide-trigger', 'data'),
    Input('hide-left', 'n_clicks'),
    [
        State('left-hide-trigger', 'data'),
        State('session-id', 'data'),
    ]
)
def left_hide_button(
    btn,
    trigger_idx,
    session_id
):
    """
    Callback when hide/unhide button is clicked

    :param int btn
        number of clicks
    :param int trigger_idx
        trigger value
    :param int session_id
        session id

    :return: trigger signal
    :rtype: int
    """
    if btn == 0:
        raise PreventUpdate

    selectedData = redis_get(session_id, REDIS_KEYS['selected_data'])

    if selectedData is None:
        raise PreventUpdate

    visible_table = redis_get(session_id, REDIS_KEYS['visible_table'])

    s_data = pd.DataFrame(selectedData['points'])
    idx = s_data['id']
    idx.index = idx

    vis_idx = idx[visible_table['_VIS_'][idx] == 'visible']
    hid_idx = idx[visible_table['_VIS_'][idx] == 'hidden']

    visible_table.loc[vis_idx, '_VIS_'] = 'hidden'
    visible_table.loc[hid_idx, '_VIS_'] = 'visible'

    redis_set(visible_table, session_id, REDIS_KEYS['visible_table'])

    return trigger_idx+1
