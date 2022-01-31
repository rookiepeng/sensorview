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

from maindash import app
from dash.dependencies import Input, Output


@app.callback(
    [
        Output('slider-frame', 'disabled'),
        Output('previous-button', 'disabled'),
        Output('next-button', 'disabled'),
        Output('play-button', 'disabled'),
        Output('stop-button', 'disabled'),
    ],
    Input('overlay-switch', 'value'))
def overlay_switch_changed(overlay):
    """
    Callback when the overlay switch state is changed

    :param boolean overlay
        overlay switch state

    :return: [
        Frame slider enable/disable,
        Previous button enable/disable,
        Next button enable/disable,
        Play button enable/disable,
        Stop button enable/disable
    ]
    :rtype: list
    """
    if overlay:
        return [True]*5
    else:
        return [False]*5
