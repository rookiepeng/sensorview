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
    output=dict(
        frame_slider_disabled=Output('slider-frame', 'disabled'),
        previous_button_disabled=Output('previous-button', 'disabled'),
        next_button_disabled=Output('next-button', 'disabled'),
        play_button_disabled=Output('play-button', 'disabled'),
        stop_button_disabled=Output('stop-button', 'disabled'),
    ),
    inputs=dict(
        overlay=Input('overlay-switch', 'value')
    ))
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
        return dict(
            frame_slider_disabled=True,
            previous_button_disabled=True,
            next_button_disabled=True,
            play_button_disabled=True,
            stop_button_disabled=True
        )
    else:
        return dict(
            frame_slider_disabled=False,
            previous_button_disabled=False,
            next_button_disabled=False,
            play_button_disabled=False,
            stop_button_disabled=False
        )
