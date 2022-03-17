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


import dash
from maindash import app
from dash.dependencies import Input, Output, State

from layout.layout import get_app_layout

from utils import redis_get, REDIS_KEYS

from views import test_case_view
from views import control_view
from views import scatter_3d_view
from views import heatmap_view
from views import histogram_view
from views import parcats_view
from views import scatter_2d_left_view
from views import scatter_2d_right_view
from views import violin_view


server = app.server
app.scripts.config.serve_locally = True
app.css.config.serve_locally = True
app.title = 'RadarViz'
app.layout = get_app_layout


""" Callbacks """


@app.callback(
    [
        Output('buffer', 'value'),
        Output('buffer-interval', 'disabled'),
    ],
    [
        Input('buffer-interval', 'n_intervals'),
        Input('filter-trigger', 'data'),
        Input('colormap-3d', 'value'),
        Input('left-hide-trigger', 'data'),
        Input('outline-switch', 'value'),
        Input('file-picker', 'value'),
    ],
    [
        State('slider-frame', 'max'),
        State('session-id', 'data'),
    ]
)
def update_buffer_indicator(
    unused1,
    unused2,
    unused3,
    unused4,
    unused5,
    unused6,
    max_frame,
    session_id
):
    """
    Update buffer progress bar

    :param int unused1
    :param int unused2
    :param str unused3
    :param int unused4
    :param boolean unused5
    :param json unused6
    :param int max_frame
        maximal number of frames
    :param str session_id
        session id

    :return: [
        Buffer percentage,
        Interval enable/disable
    ]
    :rtype: int
    """
    if max_frame is None:
        return [0,  False]

    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if trigger_id == 'buffer-interval':
        fig_idx = redis_get(session_id, REDIS_KEYS['figure_idx'])
        if fig_idx is not None:
            percent = fig_idx/max_frame*100
            if percent == 100:
                return [percent, True]
            else:
                return [percent, dash.no_update]
        else:
            return [0,  dash.no_update]
    else:
        return [0,  False]


app.clientside_callback(
    """
    function(play_clicks, stop_clicks) {
        const triggered = dash_clientside.callback_context.triggered.map(
            t => t.prop_id
            );
        if (triggered.length > 0) {
            if (triggered[0].includes('play-button')) {
                if (play_clicks>0){
                    return false;
                }
                else {
                    return window.dash_clientside.no_update;
                }
            }
            if (triggered[0].includes('stop-button')) {
                if (stop_clicks>0){
                    return true;
                }
                else {
                    return window.dash_clientside.no_update;
                }
            }
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output('interval-component', 'disabled'),
    Input('play-button', 'n_clicks'),
    Input('stop-button', 'n_clicks')
)


if __name__ == '__main__':
    app.run_server(debug=True, threaded=True, processes=1, host='0.0.0.0')
