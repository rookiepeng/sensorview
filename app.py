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

from maindash import app

from layout.layout import get_app_layout

from views import test_case_view
from views import control_view
from views import scatter_3d_view
from views import heatmap_view
from views import histogram_view
from views import parcats_view
from views import scatter_2d_left_view
from views import scatter_2d_right_view
from views import violin_view

from flaskwebgui import FlaskUI


server = app.server
app.scripts.config.serve_locally = True
app.css.config.serve_locally = True
app.title = "SensorView"
app.layout = get_app_layout


""" Callbacks """

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
    # app.run_server(debug=True, threaded=True, processes=1, host="0.0.0.0")
    FlaskUI(app=server, server="flask", port=46734).run()
