"""SensorView Threshold Map View Callbacks

Renders one dense threshold map (range-Doppler, range-angle, ...) per frame,
read straight from the HDF5 sidecar.

Note what this callback does *not* listen to: ``filter-trigger``. Threshold maps
are display-only, so dragging a filter slider never re-reads or re-renders them.
They update on frame change and on their own selectors, nothing else.

Usage:
    from view_callbacks.threshold_view import get_threshold_view_callbacks
    get_threshold_view_callbacks(app)

Author: Zhengyu Peng
License: GPL-3.0
"""

from typing import Any, Dict

import dash
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from app_config import CACHE_KEYS

from frame_sources import (
    get_log_stem,
    get_manifest,
    get_threshold_figure,
    get_threshold_sensors,
    get_threshold_value_range,
)

from utils import cache_get

HIDDEN = {"display": "none"}
VISIBLE = {"display": "block"}


def get_threshold_view_callbacks(app: dash.Dash) -> None:
    """
    Register the callback functions for the threshold map view.

    Args:
        app (dash.Dash): The Dash application instance

    Returns:
        None
    """

    @app.callback(
        output={
            "card_style": Output("threshold-card", "style"),
            "sensor_options": Output("threshold-sensor-picker", "options"),
            "sensor_value": Output("threshold-sensor-picker", "value"),
        },
        inputs={"unused_file_loaded": Input("file-loaded-trigger", "data")},
        state={"session_id": State("session-id", "data")},
    )
    def populate_threshold_sensors(
        unused_file_loaded: int, session_id: str
    ) -> Dict[str, Any]:
        """
        Populate the sensor selector and show or hide the threshold card.

        Args:
            unused_file_loaded (int): File load trigger count
            session_id (str): Session identifier

        Returns:
            dict: Card visibility, sensor options, and selected sensor
        """
        manifest = get_manifest(session_id)
        # Sensors are discovered from the log's HDF5 sidecar, not declared.
        sensors = get_threshold_sensors(manifest, get_log_stem(session_id))

        if not sensors:
            return {
                "card_style": HIDDEN,
                "sensor_options": [],
                "sensor_value": None,
            }

        return {
            "card_style": VISIBLE,
            "sensor_options": [
                {"label": s["label"], "value": s["id"]} for s in sensors
            ],
            "sensor_value": sensors[0]["id"],
        }

    @app.callback(
        output={"figure": Output("threshold-map", "figure")},
        inputs={
            "frame_idx": Input("slider-frame", "value"),
            "sensor_id": Input("threshold-sensor-picker", "value"),
            "colormap": Input("colormap-threshold", "value"),
            "lock_scale": Input("threshold-lock-scale", "value"),
        },
        state={"session_id": State("session-id", "data")},
    )
    def update_threshold_map(
        frame_idx: int,
        sensor_id: str,
        colormap: str,
        lock_scale: list,
        session_id: str,
    ) -> Dict[str, Any]:
        """
        Render the threshold map for the current frame and sensor.

        Args:
            frame_idx (int): Current slider position
            sensor_id (str): Selected sensor identifier
            colormap (str): Selected colorscale name
            lock_scale (list): Non-empty when the color scale is pinned
            session_id (str): Session identifier

        Returns:
            dict: Contains the threshold map figure

        Raises:
            PreventUpdate: If no sensor is selected
        """
        if not sensor_id:
            raise PreventUpdate

        manifest = get_manifest(session_id)
        if manifest is None:
            raise PreventUpdate

        # The slider carries a positional index; the stores are keyed by the
        # dataset's own frame ids.
        frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])
        if frame_list is None or len(frame_list) == 0:
            raise PreventUpdate
        if frame_idx is None or frame_idx >= len(frame_list):
            raise PreventUpdate

        frame_id = frame_list[frame_idx]
        stem = get_log_stem(session_id)

        value_range = (
            get_threshold_value_range(
                manifest, stem, sensor_id, session_id, frame_ids=frame_list
            )
            if lock_scale
            else None
        )

        return {
            "figure": get_threshold_figure(
                manifest,
                stem,
                frame_id,
                sensor_id,
                colormap=colormap or "Jet",
                value_range=value_range,
            )
        }
