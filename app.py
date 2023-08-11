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
from dash.dependencies import Input, Output, State

from maindash import app

from layout.layout import get_app_layout

from utils import cache_get, CACHE_KEYS

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
        buffer_tooltip=Output('buffer-tooltip', 'children'),
    ),
    inputs=dict(
        interval=Input('buffer-interval', 'n_intervals'),
        filter_trigger=Input('filter-trigger', 'data'),
        c_key=Input('c-picker-3d', 'value'),
        left_hide_trigger=Input('left-hide-trigger', 'data'),
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
    c_key,
    left_hide_trigger,
    file_picker,
    max_frame,
    session_id
):
    """Update buffer progress

    Args:
        interval (int): _description_
        filter_trigger (int): _description_
        c_key (str): _description_
        left_hide_trigger (int): _description_
        file_picker (_type_): _description_
        max_frame (_type_): _description_
        session_id (_type_): _description_

    Returns:
        _type_: _description_
    """
    if max_frame is None:
        return dict(
            buffer_progress=0,
            buffer_intrval_disabled=False,
            buffer_tooltip='Buffering ... (0 %)',
        )

    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if trigger_id == 'buffer-interval':
        fig_idx = cache_get(session_id, CACHE_KEYS['figure_idx'])
        if fig_idx is not None:
            percent = fig_idx/max_frame*100
            if percent == 100:
                return dict(
                    buffer_progress=percent,
                    buffer_intrval_disabled=True,
                    buffer_tooltip='Buffer ready (100 %)',
                )
            else:
                return dict(
                    buffer_progress=percent,
                    buffer_intrval_disabled=dash.no_update,
                    buffer_tooltip='Buffering ... (' +
                    str(round(percent, 2))+' %)',
                )
        else:
            return dict(
                buffer_progress=0,
                buffer_intrval_disabled=dash.no_update,
                buffer_tooltip='Buffering ... (0 %)',
            )
    else:
        return dict(
            buffer_progress=0,
            buffer_intrval_disabled=False,
            buffer_tooltip='Buffering ... (0 %)',
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
