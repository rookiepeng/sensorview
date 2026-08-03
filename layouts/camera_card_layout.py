"""Camera Card Layout Module

Layout for the camera panel. The camera is an mp4 played by a native
``<video>`` element that the frame slider seeks via ``currentTime``, rather
than a per-frame image decoded and base64-encoded on the server. The browser
does the decoding, and scrubbing costs no round trip.

Usage:
    from layouts.camera_card_layout import get_camera_card_layout

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from dash import dcc
from dash import html

import dash_bootstrap_components as dbc


def get_camera_card_layout():
    """
    Creates the camera card containing the frame-synchronized video player.

    The card includes:
        - A stream selector (shown only when the dataset has several cameras)
        - A muted, control-less ``<video>`` element driven by the frame slider
        - Stores holding the stream descriptor and the seek acknowledgement

    Args:
        None

    Returns:
        dbc.Card: A Dash Bootstrap Card component containing the camera player.
        The card hides itself when the loaded dataset declares no camera.
    """
    return dbc.Card(
        [
            dbc.CardBody(
                [
                    # Stream descriptor: {"src", "fps", "frame_count"}. The
                    # clientside seek reads fps from here.
                    dcc.Store(id="camera-config"),
                    dcc.Store(id="camera-seek-ack"),
                    dbc.Row(
                        [
                            dbc.Col(dbc.Label("Camera"), width="auto"),
                            dbc.Col(
                                dbc.InputGroup(
                                    [
                                        dbc.InputGroupText("Stream"),
                                        dbc.Select(id="camera-stream-picker"),
                                        dbc.Tooltip(
                                            "Select camera stream",
                                            target="camera-stream-picker",
                                            placement="top",
                                        ),
                                    ],
                                    size="sm",
                                ),
                                width=4,
                                id="camera-stream-picker-col",
                                className="ms-auto",
                            ),
                        ],
                        className="mb-2 align-items-center",
                    ),
                    html.Video(
                        id="camera-video",
                        # Playback is driven entirely by the frame slider, so
                        # the element never plays on its own: no controls, no
                        # autoplay, muted so browsers never block the load.
                        controls=False,
                        autoPlay=False,
                        muted=True,
                        preload="auto",
                        style={
                            "width": "100%",
                            "maxHeight": "40vh",
                            "objectFit": "contain",
                            "backgroundColor": "#000",
                            "borderRadius": "0.375rem",
                        },
                    ),
                ],
                className="mx-3 my-3",
            )
        ],
        id="camera-card",
        className="mb-3",
        style={"display": "none"},
    )
