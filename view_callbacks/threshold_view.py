"""SensorView Threshold View Callbacks

Renders one 1D threshold plot per frame -- a signal and the thresholds applied
to it -- read from the log's HDF5 sidecar. A single file holds many named
series; which of them share a plot, and how each is styled, comes from
``info.json``.

Combining logs that share frame ids puts several sidecars on one slider
position. Each gets a stacked band of its own against a shared x axis and a
shared y range, rather than the primary log winning the position outright:
overlaying them instead would double every trace the plot already declares, and
these plots regularly declare a handful. The sensor and plot selectors offer the
union of what the loaded logs recorded, so a sidecar only the second log has is
still reachable.

Note what this callback does *not* listen to: ``filter-trigger``. Threshold
series are display-only, so dragging a filter slider never re-reads or
re-renders them. They update on frame change and on their own selector.

Usage:
    from view_callbacks.threshold_view import get_threshold_view_callbacks
    get_threshold_view_callbacks(app)

Author: Zhengyu Peng
License: GPL-3.0
"""

from typing import Any, Dict, List, Optional

import dash
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from settings import CACHE_KEYS

from frame_sources import (
    get_frame_positions,
    get_frame_stems,
    get_log_stems,
    get_manifest,
    get_curve_figure_multi,
    get_curve_plots,
    get_curve_sources,
    get_curve_y_range,
)

from utils import cache_get

HIDDEN = {"display": "none"}

# Enough for the axis, a wrapped legend, and one readable curve; each further
# stacked panel needs a band of its own on top of that.
MIN_GRAPH_HEIGHT = 220
PANEL_HEIGHT = 140


def _merge_options(per_log: List[List[Dict[str, str]]]) -> List[Dict[str, str]]:
    """
    Union the picker entries several logs offer, keeping the first log's order.

    Combined logs need not have recorded the same sensors or the same plots, and
    a selector that only listed the primary's would hide the very sidecar the
    second log was combined in for.

    Args:
        per_log: One list of ``{"id", "label"}`` dicts per log, primary first.

    Returns:
        De-duplicated entries by id, in first-seen order.
    """
    merged: List[Dict[str, str]] = []
    seen = set()
    for entries in per_log:
        for entry in entries:
            if entry["id"] in seen:
                continue
            seen.add(entry["id"])
            merged.append(entry)
    return merged


def _merge_y_ranges(ranges: List[Optional[list]]) -> Optional[list]:
    """
    Widen several per-log y ranges into the one the stacked panels share.

    Stacking the logs is only worth doing if a level in one band means the same
    as the level beside it, so the panels are pinned to a common range rather
    than each to its own.

    Args:
        ranges: Per-log ``[min, max]`` estimates, any of which may be None.

    Returns:
        The enclosing ``[min, max]``, or None when nothing could be estimated.
    """
    usable = [pair for pair in ranges if pair]
    if not usable:
        return None
    return [min(pair[0] for pair in usable), max(pair[1] for pair in usable)]


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
        sources = _merge_options(
            [get_curve_sources(manifest, stem) for stem in get_log_stems(session_id)]
        )

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
            _merge_options(
                [
                    get_curve_plots(manifest, stem, source_id)
                    for stem in get_log_stems(session_id)
                ]
            )
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
        output={
            "figure": Output("threshold-plot", "figure"),
            "wrap_style": Output("threshold-graph-wrap", "style"),
        },
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

        Logs that share a frame id land on one slider position, and each gets a
        stacked panel of its own rather than the primary silently winning. The
        wrapper's minimum height grows with the panel count, so the extra bands
        take room from the dock instead of squeezing each other flat.

        Args:
            frame_idx (int): Current slider position
            plot_id (str): Selected plot identifier
            source_id (str): Selected threshold source identifier
            session_id (str): Session identifier

        Returns:
            dict: Contains the threshold figure and the wrapper's height

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

        # Curves belong to the logs that recorded this frame, which with logs
        # combined need not include the primary one at all.
        stems = [
            stem
            for stem in get_frame_stems(session_id, frame_idx)
            if manifest.has_curve(stem)
        ]

        # Held constant across frames so the signal's position relative to its
        # threshold stays readable while scrubbing, and shared between the
        # panels so their levels can be read against each other. Sampled only
        # from the frames each log recorded -- the other logs' ids are not in
        # its sidecar, and spending the sample budget on frames that read back
        # empty would leave the range estimated from a handful of the log's own.
        y_range = _merge_y_ranges(
            [
                get_curve_y_range(
                    manifest,
                    stem,
                    plot_id,
                    session_id,
                    frame_ids=[
                        frame_list[idx] for idx in get_frame_positions(session_id, stem)
                    ],
                    source_id=source_id,
                )
                for stem in stems
            ]
        )

        figure = get_curve_figure_multi(
            manifest,
            stems,
            frame_list[frame_idx],
            plot_id,
            y_range=y_range,
            source_id=source_id,
        )

        # One y axis per panel, so counting them counts the bands that were
        # actually drawn -- stems whose sidecar read back empty are not among
        # them.
        panels = sum(1 for key in figure.get("layout", {}) if key.startswith("yaxis"))
        return {
            "figure": figure,
            "wrap_style": {
                "minHeight": f"{max(MIN_GRAPH_HEIGHT, PANEL_HEIGHT * panels)}px"
            },
        }
