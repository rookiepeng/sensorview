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


from dash.dependencies import Input, Output

from dash_config import app
from layout import get_app_layout

app.layout = get_app_layout

import test_case_view  # pylint: disable=unused-import, wrong-import-position
import control_view  # pylint: disable=unused-import, wrong-import-position
import scatter_3d_view  # pylint: disable=unused-import, wrong-import-position
import heatmap_view  # pylint: disable=unused-import, wrong-import-position
import histogram_view  # pylint: disable=unused-import, wrong-import-position
import parcats_view  # pylint: disable=unused-import, wrong-import-position
import scatter_2d_left_view  # pylint: disable=unused-import, wrong-import-position
import scatter_2d_right_view  # pylint: disable=unused-import, wrong-import-position
import violin_view  # pylint: disable=unused-import, wrong-import-position

# from flaskwebgui import FlaskUI
# from waitress import serve

server = app.server

"""
This clientside callback function disables the interval component based on
the number of clicks on the play button and stop button. If the play button
is clicked and the number of play clicks is greater than 0, the interval
component is disabled. If the stop button is clicked and the number of stop
clicks is greater than 0, the interval component is enabled. If neither button
is clicked, the interval component remains unchanged.
"""
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
    Output("interval-component", "disabled"),
    Input("play-button", "n_clicks"),
    Input("stop-button", "n_clicks"),
)


if __name__ == "__main__":
    app.run_server(debug=False, threaded=True, processes=1, host="0.0.0.0")
    # FlaskUI(app=server, server="flask", port=46734).run()
    # serve(server, listen='*:8080')
