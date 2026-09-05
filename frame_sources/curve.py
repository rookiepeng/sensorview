"""Per-Frame 1D Curves

Range profiles, thresholds, noise floors: one HDF5 sidecar per sensor, many
named series per frame.

The y range is estimated once per (log, source, plot) and then held, so where a
signal sits relative to its threshold stays readable while scrubbing instead of
autoscaling every frame.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Any, Dict, List, Optional

import numpy as np

from settings import CACHE_KEYS

from dataio.dense_store import CurveStore
from dataio.manifest import Manifest

from utils import cache_get, cache_set

from viz.viz import get_curve_plot, get_curve_plot_grid


def get_curve_sources(manifest: Optional[Manifest], stem: str) -> List[Dict[str, str]]:
    """
    List the curve sidecars available for the current log.

    A log may record curves from several sensors, each in its own file.
    They are separate sources rather than merged series because their range
    bins do not line up -- one sensor's profile ends at 241 m and another's at
    262 m, so there is no shared axis to draw them against.

    Args:
        manifest: Dataset manifest, or None.
        stem: Log stem.

    Returns:
        List of ``{"id", "label"}`` dicts; empty when the log has no curve
        sidecar.
    """
    if manifest is None or not stem:
        return []
    return [
        {"id": source["id"], "label": source["label"]}
        for source in manifest.curve_sources(stem)
    ]


def _curve_store(
    manifest: Manifest, stem: str, source_id: Optional[str] = None
) -> Optional[CurveStore]:
    """
    Open one of a log's curve sidecars.

    Args:
        manifest: Dataset manifest.
        stem: Log stem.
        source_id: Source identifier; defaults to the log's first source.

    Returns:
        Store for that source, or None when it does not exist.
    """
    path = manifest.curve_path(stem, source_id)
    if not path:
        return None
    return CurveStore(path, sensor_id=source_id)


def get_curve_plots(
    manifest: Optional[Manifest], stem: str, source_id: Optional[str] = None
) -> List[Dict[str, str]]:
    """
    List the curve plots available for the current log.

    Args:
        manifest: Dataset manifest, or None.
        stem: Log stem.
        source_id: Curve source to inspect; defaults to the log's first.

    Returns:
        List of ``{"id", "label"}`` dicts; empty when the log has no curve
        sidecar or the manifest declares no plots.
    """
    if manifest is None or not manifest.has_curve(stem):
        return []

    store = _curve_store(manifest, stem, source_id)
    if store is None:
        return []

    # Plot definitions are declared once for the whole case, but which series a
    # given source actually recorded varies. Offering a plot whose series are
    # all missing would just show an empty frame, so check the file once here.
    available = set(store.signals(manifest.curve_dataset_pattern()))

    plots = []
    for plot in manifest.curve_plots():
        usable = any(
            # A trace addressing a dataset directly cannot be checked by name;
            # keep it and let the read decide.
            not trace["name"] or trace["name"] in available
            for trace in plot["traces"]
        )
        if usable:
            plots.append({"id": plot["id"], "label": plot["label"]})
    return plots


def get_curve_y_range(
    manifest: Optional[Manifest],
    stem: str,
    plot_id: str,
    session_id: str,
    frame_ids: Optional[Any] = None,
    max_frames: int = 50,
    source_id: Optional[str] = None,
) -> Optional[list]:
    """
    Estimate a stable y range for one curve plot.

    Letting the axis autoscale per frame makes the curves jump while scrubbing,
    which hides exactly the thing these plots exist to show -- where the signal
    sits relative to its threshold. The range is estimated once per (log, plot)
    and cached, sampling at most ``max_frames`` evenly spaced frames.

    A manifest-declared ``y_range`` always wins over the estimate.

    Args:
        manifest: Dataset manifest, or None.
        stem: Log stem.
        plot_id: Plot identifier.
        session_id: Session identifier, used as the cache scope.
        frame_ids: Frame ids to sample from, as derived from the Parquet data.
        max_frames: Maximum number of frames to sample.
        source_id: Curve source to sample; defaults to the log's first.

    Returns:
        ``[ymin, ymax]``, or None when nothing could be read.
    """
    if manifest is None or not plot_id or not manifest.has_curve(stem):
        return None

    plot = manifest.curve_plot(plot_id)
    if plot is None:
        return None
    if plot.get("y_range"):
        return list(plot["y_range"])

    # Sources are scaled independently -- one sensor's levels say nothing about
    # another's -- so each gets its own estimate.
    cache_key = f"{stem}/{source_id or ''}/{plot_id}"
    cached = cache_get(session_id, CACHE_KEYS["curve_range"], cache_key)
    if cached is not None:
        return cached

    if frame_ids is None or len(frame_ids) == 0:
        return None

    frame_ids = np.asarray(frame_ids)
    if len(frame_ids) > max_frames:
        indices = np.linspace(0, len(frame_ids) - 1, max_frames).astype(int)
        sampled = frame_ids[indices]
    else:
        sampled = frame_ids

    store = _curve_store(manifest, stem, source_id)
    if store is None:
        return None

    low, high = np.inf, -np.inf
    for frame_id in sampled:
        for trace in plot["traces"]:
            values = store.read_series(trace["dataset"], frame_id)
            if values is None or np.size(values) == 0:
                continue
            finite = values[np.isfinite(values)]
            if finite.size == 0:
                continue
            low = min(low, float(finite.min()))
            high = max(high, float(finite.max()))

    if not np.isfinite(low) or not np.isfinite(high):
        return None

    # A little headroom so curves never sit flush against the frame.
    padding = (high - low) * 0.05 or 1.0
    y_range = [low - padding, high + padding]
    cache_set(y_range, session_id, CACHE_KEYS["curve_range"], cache_key)
    return y_range


def get_curve_figure(
    manifest: Optional[Manifest],
    stem: str,
    frame_id: Any,
    plot_id: str,
    y_range: Optional[list] = None,
    source_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build the 1D curve figure for one (frame, plot).

    Args:
        manifest: Dataset manifest, or None.
        stem: Log stem.
        frame_id: Frame identifier.
        plot_id: Plot identifier declared in the manifest.
        y_range: Optional [min, max] y clamp held constant across frames.
        source_id: Curve source to read; defaults to the log's first.

    Returns:
        Figure dictionary; an empty placeholder figure when nothing is readable.
    """
    if manifest is None or not plot_id or not manifest.has_curve(stem):
        return get_curve_plot()

    plot = manifest.curve_plot(plot_id)
    if plot is None:
        return get_curve_plot()

    store = _curve_store(manifest, stem, source_id)
    if store is None:
        return get_curve_plot()

    series, x_series = _read_curve_series(store, plot, frame_id)

    return get_curve_plot(
        series=series,
        x_series=x_series,
        traces=plot["traces"],
        x_label=plot["x_label"],
        y_label=plot["y_label"],
        x_range=plot["x_range"],
        y_range=y_range or plot["y_range"],
        log_y=plot["log_y"],
    )


def get_curve_figure_multi(
    manifest: Optional[Manifest],
    stems: List[str],
    frame_id: Any,
    plot_id: str,
    y_range: Optional[list] = None,
    source_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build the 1D curve figure for one (frame, plot) across several logs.

    Combining logs that share frame ids puts more than one recording on a single
    slider position. Rather than picking a winner, each log that recorded this
    frame gets its own stacked panel, drawn against one shared x axis and one
    shared y range so the levels are directly comparable.

    Args:
        manifest: Dataset manifest, or None.
        stems: Log stems to draw, in panel order (top first). Stems without
            this curve sidecar, or with nothing readable for this frame, are
            dropped rather than shown as an empty row.
        frame_id: Frame identifier.
        plot_id: Plot identifier declared in the manifest.
        y_range: Optional [min, max] y clamp shared by every panel.
        source_id: Curve source to read; defaults to each log's first.

    Returns:
        Figure dictionary. One readable log renders exactly as
        :func:`get_curve_figure` does, so the single-log case is unchanged.
    """
    if manifest is None or not plot_id:
        return get_curve_plot()

    plot = manifest.curve_plot(plot_id)
    if plot is None:
        return get_curve_plot()

    panels = []
    for stem in stems:
        if not manifest.has_curve(stem):
            continue
        store = _curve_store(manifest, stem, source_id)
        if store is None:
            continue
        series, x_series = _read_curve_series(store, plot, frame_id)
        if not series:
            continue
        panels.append(
            {
                "title": stem,
                "series": series,
                "x_series": x_series,
                "traces": plot["traces"],
            }
        )

    shared_range = y_range or plot["y_range"]

    if not panels:
        return get_curve_plot()
    if len(panels) == 1:
        return get_curve_plot(
            series=panels[0]["series"],
            x_series=panels[0]["x_series"],
            traces=plot["traces"],
            x_label=plot["x_label"],
            y_label=plot["y_label"],
            x_range=plot["x_range"],
            y_range=shared_range,
            log_y=plot["log_y"],
        )

    return get_curve_plot_grid(
        panels=panels,
        x_label=plot["x_label"],
        y_label=plot["y_label"],
        x_range=plot["x_range"],
        y_range=shared_range,
        log_y=plot["log_y"],
    )


def _read_curve_series(store: CurveStore, plot: Dict[str, Any], frame_id: Any) -> tuple:
    """
    Read one plot's traces out of one log's curve sidecar.

    Args:
        store: Curve store for the log.
        plot: Normalized plot definition.
        frame_id: Frame identifier.

    Returns:
        ``(series, x_series)`` keyed by trace name. Every series carries its own
        x column, so each curve is drawn against its own axis rather than a
        shared one; a trace the file does not hold is simply absent.
    """
    series: Dict[str, Any] = {}
    x_series: Dict[str, Any] = {}
    for trace in plot["traces"]:
        axis, values = store.read_curve(trace["dataset"], frame_id)
        if values is None:
            continue
        series[trace["name"]] = values
        if axis is not None:
            x_series[trace["name"]] = axis
    return series, x_series
