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
    get_frame_positions,
    get_frame_stem,
    get_log_stem,
    get_manifest,
    get_curve_figure,
    get_curve_plots,
    get_curve_sources,
    get_curve_y_range,
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
            "source_style": Output("threshold-source-picker-col", "style"),
            "source_options": Output("threshold-source-picker", "options"),
            "source_value": Output("threshold-source-picker", "value"),
        },
        inputs={"unused_file_loaded": Input("file-loaded-trigger", "data")},
        state={"session_id": State("session-id", "data")},
    )
    def populate_threshold_sources(
        unused_file_loaded: int, session_id: str
    ) -> Dict[str, Any]:
        """
        Populate the sensor selector and show or hide the threshold section.

        Args:
            unused_file_loaded (int): File load trigger count
            session_id (str): Session identifier

        Returns:
            dict: Section visibility, source options, and selected source
        """
        manifest = get_manifest(session_id)
        sources = get_curve_sources(manifest, get_log_stem(session_id))

        if not sources:
            return {
                "section_style": HIDDEN,
                "source_style": HIDDEN,
                "source_options": [],
                "source_value": None,
            }

        return {
            "section_style": {},
            # A selector is noise when there is only one source to select.
            "source_style": HIDDEN if len(sources) == 1 else {},
            "source_options": [
                {"label": s["label"], "value": s["id"]} for s in sources
            ],
            "source_value": sources[0]["id"],
        }

    @app.callback(
        output={
            "picker_style": Output("threshold-plot-picker-col", "style"),
            "plot_options": Output("threshold-plot-picker", "options"),
            "plot_value": Output("threshold-plot-picker", "value"),
        },
        inputs={"source_id": Input("threshold-source-picker", "value")},
        state={"session_id": State("session-id", "data")},
    )
    def populate_threshold_plots(source_id: str, session_id: str) -> Dict[str, Any]:
        """
        Populate the plot selector for the selected source.

        Which plots are offered depends on the source: sensors need not have
        recorded the same series, so the list is rebuilt per selection.

        Args:
            source_id (str): Selected threshold source identifier
            session_id (str): Session identifier

        Returns:
            dict: Plot options and selected plot
        """
        manifest = get_manifest(session_id)
        plots = (
            get_curve_plots(manifest, get_log_stem(session_id), source_id)
            if source_id
            else []
        )

        if not plots:
            return {
                "picker_style": HIDDEN,
                "plot_options": [],
                "plot_value": None,
            }

        return {
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
            "source_id": Input("threshold-source-picker", "value"),
        },
        state={"session_id": State("session-id", "data")},
    )
    def update_threshold_plot(
        frame_idx: int, plot_id: str, source_id: str, session_id: str
    ) -> Dict[str, Any]:
        """
        Render the threshold plot for the current frame.

        Args:
            frame_idx (int): Current slider position
            plot_id (str): Selected plot identifier
            source_id (str): Selected threshold source identifier
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

        # Curves belong to the log that recorded this frame, which with logs
        # combined is not necessarily the primary one.
        stem = get_frame_stem(session_id, frame_idx)

        # Held constant across frames so the signal's position relative to its
        # threshold stays readable while scrubbing. Sampled only from the frames
        # this log owns -- the other logs' ids are not in its sidecar, and
        # spending the sample budget on frames that read back empty would leave
        # the range estimated from a handful of the log's own.
        y_range = get_curve_y_range(
            manifest,
            stem,
            plot_id,
            session_id,
            frame_ids=[
                frame_list[idx] for idx in get_frame_positions(session_id, stem)
            ],
            source_id=source_id,
        )

        return {
            "figure": get_curve_figure(
                manifest,
                stem,
                frame_list[frame_idx],
                plot_id,
                y_range=y_range,
                source_id=source_id,
            )
        }
