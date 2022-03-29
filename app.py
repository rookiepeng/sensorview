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

from utils import redis_get, CACHE_KEYS

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
    output=dict(
        buffer_progress=Output('buffer', 'value'),
        buffer_intrval_disabled=Output('buffer-interval', 'disabled'),
    ),
    inputs=dict(
        interval=Input('buffer-interval', 'n_intervals'),
        filter_trigger=Input('filter-trigger', 'data'),
        colormap=Input('colormap-3d', 'value'),
        left_hide_trigger=Input('left-hide-trigger', 'data'),
        outline_sw=Input('outline-switch', 'value'),
        file_picker=Input('file-picker', 'value'),
    ),
    state=dict(
        max_frame=State('slider-frame', 'max'),
        session_id=State('session-id', 'data'),
    )
)
def update_buffer_indicator(
    interval,
    filter_trigger,
    colormap,
    left_hide_trigger,
    outline_sw,
    file_picker,
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
        return dict(
            buffer_progress=0,
            buffer_intrval_disabled=False
        )

    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if trigger_id == 'buffer-interval':
        fig_idx = redis_get(session_id, CACHE_KEYS['figure_idx'])
        if fig_idx is not None:
            percent = fig_idx/max_frame*100
            if percent == 100:
                return dict(
                    buffer_progress=percent,
                    buffer_intrval_disabled=True
                )
            else:
                return dict(
                    buffer_progress=percent,
                    buffer_intrval_disabled=dash.no_update
                )
        else:
            return dict(
                buffer_progress=0,
                buffer_intrval_disabled=dash.no_update
            )
    else:
        return dict(
            buffer_progress=0,
            buffer_intrval_disabled=False
        )


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
