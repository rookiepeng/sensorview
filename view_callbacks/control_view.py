"""SensorView Control View Callbacks

This module provides callback functions for managing control panel interactions
in the SensorView application.

Core Features:
-------------
1. Control Management:
   - Frame slider control
   - Navigation buttons
   - Animation controls
   - Overlay mode switching

2. UI Controls:
   - Element state management
   - Control visibility
   - Interactive mode switching
   - Button state handling

3. State Management:
   - Control state synchronization
   - Mode state tracking
   - Element accessibility

Dependencies:
------------
- dash
- app_config settings
- Standard Python libraries

Usage:
------
Register callbacks with app instance:
    from view_callbacks.control_view import get_control_view_callbacks
    get_control_view_callbacks(app)

Author: Zhengyu Peng
Email: zpeng.me@gmail.com
Website: https://zpeng.me
License: GPL-3.0
"""

import dash
from dash.dependencies import Input, Output


def get_control_view_callbacks(app: dash.Dash) -> None:
    """
    Register callback functions for control view.

    Args:
        app (dash.Dash): The Dash application instance

    Returns:
        None
    """

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
    def overlay_switch_changed(overlay: list) -> dict:
        """
        Toggle control elements based on overlay switch state.

        Args:
            overlay (list): Overlay switch state

        Returns:
            dict: Contains:
                - frame_slider_disabled (bool): Frame slider disabled state
                - previous_button_disabled (bool): Previous button disabled state
                - next_button_disabled (bool): Next button disabled state
                - play_button_disabled (bool): Play button disabled state
                - stop_button_disabled (bool): Stop button disabled state
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
