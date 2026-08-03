"""SensorView Threshold View Callbacks

Renders one 1D threshold plot per frame -- a signal and the thresholds applied
to it -- read from the log's HDF5 sidecar. A single file holds many named
series; which of them share a plot, and how each is styled, comes from
``info.json``.

Note what this callback does *not* listen to: ``filter-trigger``. Threshold
series are display-only, so dragging a filter slider never re-reads or
re-renders them. They update on frame change and on their own selector.

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
    get_threshold_plots,
    get_threshold_y_range,
)

from utils import cache_get

HIDDEN = {"display": "none"}


def get_threshold_view_callbacks(app: dash.Dash) -> None:
    """
    Register the callback functions for the threshold view.

    Args:
        app (dash.Dash): The Dash application instance

    Returns:
        None
    """

    @app.callback(
        output={
            "section_style": Output("subview-threshold-section", "style"),
            "picker_style": Output("threshold-plot-picker-col", "style"),
            "plot_options": Output("threshold-plot-picker", "options"),
            "plot_value": Output("threshold-plot-picker", "value"),
        },
        inputs={"unused_file_loaded": Input("file-loaded-trigger", "data")},
        state={"session_id": State("session-id", "data")},
    )
    def populate_threshold_plots(
        unused_file_loaded: int, session_id: str
    ) -> Dict[str, Any]:
        """
        Populate the plot selector and show or hide the threshold section.

        Args:
            unused_file_loaded (int): File load trigger count
            session_id (str): Session identifier

        Returns:
            dict: Section visibility, plot options, and selected plot
        """
        manifest = get_manifest(session_id)
        plots = get_threshold_plots(manifest, get_log_stem(session_id))

        if not plots:
            return {
                "section_style": HIDDEN,
                "picker_style": HIDDEN,
                "plot_options": [],
                "plot_value": None,
            }

        return {
            "section_style": {},
            # A selector is noise when there is only one plot to select.
            "picker_style": HIDDEN if len(plots) == 1 else {},
            "plot_options": [{"label": p["label"], "value": p["id"]} for p in plots],
            "plot_value": plots[0]["id"],
        }

    @app.callback(
        output={"figure": Output("threshold-plot", "figure")},
        inputs={
            "frame_idx": Input("slider-frame", "value"),
            "plot_id": Input("threshold-plot-picker", "value"),
        },
        state={"session_id": State("session-id", "data")},
    )
    def update_threshold_plot(
        frame_idx: int, plot_id: str, session_id: str
    ) -> Dict[str, Any]:
        """
        Render the threshold plot for the current frame.

        Args:
            frame_idx (int): Current slider position
            plot_id (str): Selected plot identifier
            session_id (str): Session identifier

        Returns:
            dict: Contains the threshold figure

        Raises:
            PreventUpdate: If no plot is selected or no data is loaded
        """
        if not plot_id:
            raise PreventUpdate

        manifest = get_manifest(session_id)
        if manifest is None:
            raise PreventUpdate

        # The slider carries a positional index; the stores are keyed by the
        # data's own frame ids.
        frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])
        if frame_list is None or len(frame_list) == 0:
            raise PreventUpdate
        if frame_idx is None or frame_idx >= len(frame_list):
            raise PreventUpdate

        stem = get_log_stem(session_id)

        # Held constant across frames so the signal's position relative to its
        # threshold stays readable while scrubbing.
        y_range = get_threshold_y_range(
            manifest, stem, plot_id, session_id, frame_ids=frame_list
        )

        return {
            "figure": get_threshold_figure(
                manifest,
                stem,
                frame_list[frame_idx],
                plot_id,
                y_range=y_range,
            )
        }
