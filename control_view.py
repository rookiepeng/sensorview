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


@app.callback(
    output={
        "frame_slider_disabled": Output("slider-frame", "disabled"),
        "previous_button_disabled": Output("previous-button", "disabled"),
        "next_button_disabled": Output("next-button", "disabled"),
        "play_button_disabled": Output("play-button", "disabled"),
        "stop_button_disabled": Output("stop-button", "disabled"),
    },
    inputs={"overlay": Input("overlay-switch", "value")},
)
def overlay_switch_changed(overlay):
    """
    Callback function to handle changes in the overlay switch.

    Parameters:
    - overlay (bool): The value of the overlay switch.

    Returns:
    - dict: A dictionary containing the updated values for the output properties.

    Output Properties:
    - frame_slider_disabled (bool): Whether the frame slider should be disabled.
    - previous_button_disabled (bool): Whether the previous button should be disabled.
    - next_button_disabled (bool): Whether the next button should be disabled.
    - play_button_disabled (bool): Whether the play button should be disabled.
    - stop_button_disabled (bool): Whether the stop button should be disabled.
    """
    if overlay:
        return {
            "frame_slider_disabled": True,
            "previous_button_disabled": True,
            "next_button_disabled": True,
            "play_button_disabled": True,
            "stop_button_disabled": True,
        }

    return {
        "frame_slider_disabled": False,
        "previous_button_disabled": False,
        "next_button_disabled": False,
        "play_button_disabled": False,
        "stop_button_disabled": False,
    }
