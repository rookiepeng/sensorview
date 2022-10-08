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

import os
import datetime

from maindash import app
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from tasks import filter_all

from utils import cache_get, CACHE_KEYS

import plotly.graph_objs as go
from viz.viz import get_heatmap
from utils import background_callback_manager
from utils import load_data


@app.callback(
    background=True,
    output=dict(
        heatmap=Output('heatmap', 'figure'),
        collapse=Output('collapse-heatmap', 'is_open'),
    ),
    inputs=dict(
        filter_trigger=Input('filter-trigger', 'data'),
        left_hide_trigger=Input('left-hide-trigger', 'data'),
        heat_sw=Input('heat-switch', 'value'),
        x_heat=Input('x-picker-heatmap', 'value'),
        y_heat=Input('y-picker-heatmap', 'value'),
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
def update_heatmap(
    filter_trigger,
    left_hide_trigger,
    heat_sw,
    x_heat,
    y_heat,
    session_id,
    visible_list,
    case,
    file,
    file_list
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
        collapse = True
        config = cache_get(session_id, CACHE_KEYS['config'])

        filter_kwargs = cache_get(session_id, CACHE_KEYS['filter_kwargs'])
        cat_keys = filter_kwargs['cat_keys']
        num_keys = filter_kwargs['num_keys']
        cat_values = filter_kwargs['cat_values']
        num_values = filter_kwargs['num_values']

        x_key = x_heat
        x_label = config['keys'][x_heat]['description']
        y_key = y_heat
        y_label = config['keys'][y_heat]['description']

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

        heat_fig = get_heatmap(
            filtered_table,
            x_key,
            y_key,
            x_label,
            y_label,
        )
    else:
        collapse = False
        heat_fig = {
            'data': [{'type': 'histogram2dcontour',
                      'x': []}
                     ],
            'layout': {
            }}

    return dict(
        heatmap=heat_fig,
        collapse=collapse
    )


@app.callback(
    output=dict(
        dummy=Output('dummy-export-heatmap', 'data')
    ),
    inputs=dict(
        btn=Input('export-heatmap', 'n_clicks')
    ),
    state=dict(
        fig=State('heatmap', 'figure'),
        case=State('case-picker', 'value')
    )
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
    return dict(
        dummy=0
    )
