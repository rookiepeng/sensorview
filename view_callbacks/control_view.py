"""SensorView Control View Callbacks

Callback functions for control panel interactions including frame slider,
navigation buttons, animation controls, and overlay mode switching.

Usage:
    from view_callbacks.control_view import get_control_view_callbacks
    get_control_view_callbacks(app)

Author: Zhengyu Peng
License: GPL-3.0
"""

import dash
from dash import html
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
            "play_stop_button_disabled": Output("play-stop-button", "disabled"),
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
                - play_stop_button_disabled (bool): Play/stop button disabled state
        """
        if overlay:
            return {
                "frame_slider_disabled": True,
                "previous_button_disabled": True,
                "next_button_disabled": True,
                "play_stop_button_disabled": True,
            }

        return {
            "frame_slider_disabled": False,
            "previous_button_disabled": False,
            "next_button_disabled": False,
            "play_stop_button_disabled": False,
        }

    @app.callback(
        output={
            "children": Output("play-stop-button", "children"),
            "color": Output("play-stop-button", "color"),
        },
        inputs={"ispaused": Input("interval-component", "disabled")},
    )
    def update_play_stop_button(ispaused: bool) -> dict:
        if ispaused:
            return {
                "children": html.I(className="bi bi-play-fill"),
                "color": "primary",
            }
        return {
            "children": html.I(className="bi bi-stop-fill"),
            "color": "danger",
        }
