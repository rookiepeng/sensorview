"""Per-Frame Data Sources

Bridges the session cache to the :mod:`dataio` stores, and defines which data
gets re-read on which trigger.

The split matters for performance. The table is refiltered whenever a filter
changes; the cloud, curves, images, and reference pose are display-only and only
ever change when the frame changes. Dragging a filter slider therefore never
touches the cloud or curve path.

Sidecars resolve from the *current log's stem*, cached per session alongside the
frame index derived from that log's Parquet. When several logs are overlaid, the
primary selected log owns the backdrop, maps, and video -- those are per-log
data with no meaningful way to merge.

Cloud frames are deliberately *not* copied into the session cache: the chunked
HDF5 sidecar is already a frame-indexed cache, and duplicating decimated points
per frame onto disk would buy nothing over a few-millisecond chunk read.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Any, Dict, List, Optional

import hashlib
import os

import numpy as np

from app_config import CACHE_KEYS, VIDEO_CACHE_PATH

from dataio.calibration import apply_transform
from dataio.dense_store import CloudStore, CurveStore
from dataio.manifest import Manifest
from dataio.reference import ReferenceStore
from dataio.video import (
    VideoEncodeError,
    is_browser_playable,
    probe_frame_count,
    transcode_to_mp4,
)

from utils import cache_get, cache_set

from viz.graph_data import get_cloud_scatter3d_data
from viz.viz import get_curve_plot

# Video frame counts, keyed on (path, size, mtime). Probing shells out to
# ffmpeg, and the answer only changes when the file does.
_FRAME_COUNTS: Dict[Any, Optional[int]] = {}


def cache_manifest(manifest: Manifest, session_id: str) -> None:
    """
    Store a manifest in the session cache.

    Only the raw dictionary and case directory are cached; the ``Manifest``
    wrapper is rebuilt on read so cached sessions survive code changes to it.

    Args:
        manifest: Manifest to cache.
        session_id: Session identifier.
    """
    cache_set(
        {
            "raw": manifest.raw,
            "case_dir": manifest.case_dir,
            "source_version": manifest.source_version,
        },
        session_id,
        CACHE_KEYS["manifest"],
    )


def get_manifest(session_id: str) -> Optional[Manifest]:
    """
    Retrieve the cached manifest for a session.

    Args:
        session_id: Session identifier.

    Returns:
        Manifest instance, or None when nothing is cached yet.
    """
    cached = cache_get(session_id, CACHE_KEYS["manifest"])
    if not cached:
        return None
    return Manifest(
        cached["raw"],
        cached["case_dir"],
        source_version=cached.get("source_version", 2),
    )


def cache_log_info(session_id: str, stem: str, timestamps: List[float]) -> None:
    """
    Store the current log's identity and derived frame index.

    The capture rate is deliberately not kept: nothing reads it now that the
    camera seek maps frame counts rather than working in seconds.

    Args:
        session_id: Session identifier.
        stem: Log stem that sidecars are keyed on.
        timestamps: Per-frame timestamps derived from the Parquet data.
    """
    cache_set(
        {"stem": stem, "timestamps": timestamps},
        session_id,
        CACHE_KEYS["log_info"],
    )


def get_log_info(session_id: str) -> Dict[str, Any]:
    """
    Retrieve the current log's identity and derived frame index.

    Args:
        session_id: Session identifier.

    Returns:
        Dict with ``stem`` and ``timestamps``; empty values when nothing is
        cached yet.
    """
    cached = cache_get(session_id, CACHE_KEYS["log_info"])
    if not cached:
        return {"stem": "", "timestamps": []}
    return cached


def get_log_stem(session_id: str) -> str:
    """
    Retrieve the current log's stem.

    Args:
        session_id: Session identifier.

    Returns:
        Log stem, or an empty string when nothing is cached yet.
    """
    return get_log_info(session_id).get("stem", "")


def get_cloud_points(
    manifest: Manifest, stem: str, frame_id: Any, apply_calibration: bool = True
) -> Optional[np.ndarray]:
    """
    Read one frame of decimated cloud points, in the reference frame.

    Args:
        manifest: Dataset manifest.
        stem: Log stem.
        frame_id: Frame identifier.
        apply_calibration: Whether to apply the cloud extrinsics. Needed for the
            overlay to line up with the table; skip only for raw inspection.

    Returns:
        (N, 3+) point array, or None when the log has no cloud or that frame is
        missing.
    """
    if not manifest.has_cloud(stem):
        return None

    store = CloudStore(manifest.cloud_path(stem), manifest.cloud_dataset_pattern())
    points = store.read_frame(frame_id)
    if points is None or len(points) == 0:
        return None

    if apply_calibration:
        calibration = manifest.cloud_calibration()
        if not calibration.is_identity:
            transformed = apply_transform(points[:, :3], calibration)
            if points.shape[1] > 3:
                points = np.column_stack([transformed, points[:, 3:]])
            else:
                points = transformed

    return points


def get_cloud_trace(
    manifest: Optional[Manifest], stem: str, frame_id: Any
) -> Optional[Dict[str, Any]]:
    """
    Build the point-cloud backdrop trace for one frame.

    Args:
        manifest: Dataset manifest, or None.
        stem: Log stem.
        frame_id: Frame identifier.

    Returns:
        Scatter3d trace dictionary, or None when there is no cloud to draw.
    """
    if manifest is None or not stem:
        return None

    points = get_cloud_points(manifest, stem, frame_id)
    if points is None:
        return None

    return get_cloud_scatter3d_data(points, manifest.cloud_display())


def get_reference_store(
    manifest: Optional[Manifest], stem: str
) -> Optional[ReferenceStore]:
    """
    Open the current log's reference-pose sidecar.

    Args:
        manifest: Dataset manifest, or None.
        stem: Log stem.

    Returns:
        Store for the sidecar, or None when the log has none or the file
        carries no column the pose can be built from.
    """
    if manifest is None or not stem or not manifest.has_reference_pose(stem):
        return None

    store = ReferenceStore.open(
        manifest.reference_path(stem),
        manifest.reference_columns(),
        frame_key=manifest.frame_key,
    )
    if store is None or not store.is_usable:
        return None
    return store


def get_reference_mapping(
    manifest: Optional[Manifest], stem: str
) -> Optional[Dict[str, Any]]:
    """
    Describe a log's reference sidecar for the view's column pickers.

    Unlike :func:`get_reference_store` this answers for a sidecar that is
    present but not yet mapped to anything usable -- which is exactly the state
    the pickers exist to get the user out of.

    Args:
        manifest: Dataset manifest, or None.
        stem: Log stem.

    Returns:
        ``{"file", "columns", "mapping"}`` -- the sidecar's name, its column
        names, and the column currently feeding each pose field -- or None when
        the log has no sidecar.
    """
    if manifest is None or not stem or not manifest.has_reference_pose(stem):
        return None

    path = manifest.reference_path(stem)
    store = ReferenceStore.open(
        path, manifest.reference_columns(), frame_key=manifest.frame_key
    )
    if store is None:
        return None

    return {
        "file": os.path.basename(path or ""),
        "columns": store.available_columns,
        "mapping": store.resolved_columns,
    }


def get_reference_pose(
    manifest: Optional[Manifest], stem: str, frame_id: Any
) -> Optional[Dict[str, float]]:
    """
    Read the reference pose for one frame.

    Args:
        manifest: Dataset manifest, or None.
        stem: Log stem.
        frame_id: Frame identifier.

    Returns:
        Pose dict with ``x``/``y``/``z`` in meters and ``yaw``/``pitch``/``roll``
        in radians, or None when the log has no sidecar or no row for that frame.
    """
    store = get_reference_store(manifest, stem)
    if store is None:
        return None
    return store.pose(frame_id)


def get_reference_bounds(
    manifest: Optional[Manifest], stem: str
) -> Optional[Dict[str, Any]]:
    """
    Position extent of the reference across the whole log.

    The 3D scene fixes its axis ranges from the table's filters, so a reference
    that travels outside them has to be accounted for before the figure is built
    or it is simply clipped.

    Args:
        manifest: Dataset manifest, or None.
        stem: Log stem.

    Returns:
        ``{"x": (min, max), "y": ..., "z": ...}``, or None when the log has no
        sidecar.
    """
    store = get_reference_store(manifest, stem)
    if store is None:
        return None
    return store.bounds()


def playable_image_file(source: str) -> Optional[str]:
    """
    Resolve an image stream to a file the browser can actually play.

    A recorder's own container is served untouched when browsers understand it.
    Anything else is transcoded once into the video cache and served from there
    -- the case folder is treated as read-only input, so nothing is written back
    beside the user's data.

    The cache key includes the source's size and mtime, so replacing a log's
    recording invalidates its transcode without anyone having to clear a cache.

    The path returned is absolute. Both the data path and the video cache are
    configured relative (``./data``, ``./cache/video``), and ``flask.send_file``
    resolves a relative path against ``app.root_path`` rather than the working
    directory. Run from source those are the same folder and a relative path
    happens to work; in a PyInstaller build ``root_path`` is the bundle
    directory while the data sits beside the executable, so the same relative
    path resolves into the bundle, the stat fails, and the camera panel gets an
    error instead of a video.

    Args:
        source: Path to the stream file as discovered in the case folder.

    Returns:
        Absolute path to a playable file, or None when the source is missing or
        cannot be transcoded.
    """
    if not source or not os.path.exists(source):
        return None

    if is_browser_playable(source):
        return os.path.abspath(source)

    try:
        stat = os.stat(source)
    except OSError:
        return None

    fingerprint = hashlib.sha1(
        f"{os.path.abspath(source)}|{stat.st_size}|{int(stat.st_mtime)}".encode()
    ).hexdigest()[:16]
    cached = os.path.abspath(
        os.path.join(
            VIDEO_CACHE_PATH,
            f"{os.path.splitext(os.path.basename(source))[0]}.{fingerprint}.mp4",
        )
    )

    if os.path.exists(cached) and os.path.getsize(cached) > 0:
        return cached

    try:
        return transcode_to_mp4(source, cached)
    except (VideoEncodeError, FileNotFoundError, OSError):
        return None


def image_stream_frame_count(source: str) -> Optional[int]:
    """
    Count the frames in an image stream, memoized per file revision.

    The count is read off the *source* rather than the transcoded copy: the
    transcode is frame-for-frame, and probing the source avoids forcing one to
    happen just to answer this while the stream picker is rendering.

    Args:
        source: Path to the stream file as discovered in the case folder.

    Returns:
        Frame count, or None when it cannot be determined.
    """
    if not source:
        return None

    try:
        stat = os.stat(source)
    except OSError:
        return None

    # Keyed on the file's revision, so replacing a recording re-probes it. Held
    # in the process rather than the session cache because it is a property of
    # the file, shared by every session that opens the same case folder.
    key = (os.path.abspath(source), stat.st_size, int(stat.st_mtime))
    if key not in _FRAME_COUNTS:
        _FRAME_COUNTS[key] = probe_frame_count(source)
    return _FRAME_COUNTS[key]


def get_curve_sources(
    manifest: Optional[Manifest], stem: str
) -> List[Dict[str, str]]:
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

    # Every series carries its own x column, so each curve is drawn against its
    # own axis rather than a shared one.
    series = {}
    x_series = {}
    for trace in plot["traces"]:
        axis, values = store.read_curve(trace["dataset"], frame_id)
        if values is None:
            continue
        series[trace["name"]] = values
        if axis is not None:
            x_series[trace["name"]] = axis

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
