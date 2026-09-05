"""Per-Frame Data Sources

Bridges the session cache to the :mod:`dataio` stores, and defines which data
gets re-read on which trigger.

The split matters for performance. The table is refiltered whenever a filter
changes; the cloud, curves, images, and reference pose are display-only and only
ever change when the frame changes. Dragging a filter slider therefore never
touches the cloud or curve path.

Sidecars resolve from the *stem of the log a frame came from*, cached per
session alongside the frame index derived from the loaded Parquet. Combining
logs concatenates their rows, so the slider walks one log's frames and then the
next; resolving every frame against the primary log's stem would leave the whole
second half with no cloud, no pose, no curves, and the wrong video.

Logs need not run end to end, though. Two that share a frame id collapse onto
one slider position, and there the panels that can show several logs at once --
the camera and the curve -- show all of them rather than picking a winner; see
:func:`get_frame_stems`. The pickers those panels sit behind offer the union of
what every loaded log recorded, so a stream or a curve source only the second
log has is still selectable. The primary log remains the tie-break for anything
that has room for one answer only: the point cloud, the pose, and the stills in
the HTML export.

Cloud frames are deliberately *not* copied into the session cache: the chunked
HDF5 sidecar is already a frame-indexed cache, and duplicating decimated points
per frame onto disk would buy nothing over a few-millisecond chunk read.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Any, Dict, List, Optional

import base64
import hashlib
import os
import tempfile

import numpy as np

from app_config import CACHE_KEYS, VIDEO_CACHE_PATH

from dataio.calibration import apply_transform
from dataio.dense_store import CloudStore, CurveStore
from dataio.manifest import Manifest
from dataio.reference import ReferenceStore
from dataio.video import (
    VideoEncodeError,
    extract_frames,
    is_browser_playable,
    probe_frame_count,
    transcode_to_mp4,
)

from utils import cache_get, cache_set

from viz.graph_data import get_cloud_scatter3d_data
from viz.viz import get_curve_plot, get_curve_plot_grid

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


def cache_log_info(
    session_id: str,
    stem: str,
    frame_stems: Optional[List[str]] = None,
    frame_owner_sets: Optional[List[List[str]]] = None,
) -> None:
    """
    Store the loaded logs' identity and per-frame ownership.

    Neither timestamps nor a capture rate are kept: nothing reads either now
    that the camera seek maps frame counts rather than working in seconds.

    Args:
        session_id: Session identifier.
        stem: Primary log's stem -- the one that owns per-load choices.
        frame_stems: Owning log stem per slider position, aligned index-wise
            with the frame list. Defaults to the primary stem throughout, which
            is what a single loaded log means.
        frame_owner_sets: *Every* log that recorded each slider position, the
            primary's first. Two logs sharing a frame id collapse onto one
            slider position, and the camera and curve panels show both -- which
            they cannot do from ``frame_stems``, since that names only one.
    """
    cache_set(
        {
            "stem": stem,
            "frame_stems": list(frame_stems) if frame_stems else [],
            "frame_owner_sets": (
                [list(owners) for owners in frame_owner_sets]
                if frame_owner_sets
                else []
            ),
        },
        session_id,
        CACHE_KEYS["log_info"],
    )


def build_frame_owner_sets(
    frame_list: Any, frame_owners: Optional[Dict[str, List[str]]], stem: str
) -> tuple:
    """
    Shape the per-frame ownership map into the two lists the cache holds.

    Args:
        frame_list: Frame ids in slider order.
        frame_owners: ``{str(frame_id): [stem, ...]}`` as read off the selected
            tables, or None when a single log is loaded.
        stem: Primary log's stem.

    Returns:
        ``(owner_sets, frame_stems)``. Each owner set leads with the primary
        when it recorded that frame, which keeps ``frame_stems`` -- the head of
        every set -- naming the log it named before logs could share a position.
        A frame no selected table claims falls back to the primary alone.
    """
    owner_sets: List[List[str]] = []
    for frame_id in frame_list:
        owners = list((frame_owners or {}).get(str(frame_id)) or [stem])
        if stem in owners:
            owners = [stem] + [other for other in owners if other != stem]
        owner_sets.append(owners)
    return owner_sets, [owners[0] for owners in owner_sets]


def get_log_info(session_id: str) -> Dict[str, Any]:
    """
    Retrieve the loaded logs' identity and derived frame index.

    Args:
        session_id: Session identifier.

    Returns:
        Dict with ``stem``, ``frame_stems``, and ``frame_owner_sets``; empty
        values when nothing is cached yet.
    """
    cached = cache_get(session_id, CACHE_KEYS["log_info"])
    if not cached:
        return {
            "stem": "",
            "frame_stems": [],
            "frame_owner_sets": [],
        }
    cached.setdefault("frame_stems", [])
    # An entry written by an older build carries no owner sets; the accessors
    # below fall back to the single-owner list rather than reading nothing.
    cached.setdefault("frame_owner_sets", [])
    return cached


def get_log_stem(session_id: str) -> str:
    """
    Retrieve the primary log's stem.

    Args:
        session_id: Session identifier.

    Returns:
        Log stem, or an empty string when nothing is cached yet.
    """
    return get_log_info(session_id).get("stem", "")


def get_frame_stem(session_id: str, frame_idx: int) -> str:
    """
    Retrieve the stem of the log one slider position belongs to.

    Args:
        session_id: Session identifier.
        frame_idx: Slider position (an index into the frame list, not a frame
            id).

    Returns:
        The owning log's stem, falling back to the primary log's when no
        per-frame mapping is cached -- which is the single-log case.
    """
    info = get_log_info(session_id)
    frame_stems = info.get("frame_stems") or []
    if frame_idx is not None and 0 <= frame_idx < len(frame_stems):
        return frame_stems[frame_idx]
    return info.get("stem", "")


def get_frame_stems(session_id: str, frame_idx: int) -> List[str]:
    """
    List *every* log that recorded one slider position.

    Two logs sharing a frame id collapse onto a single slider position, and the
    camera and curve panels show one subplot per log rather than picking a
    winner. :func:`get_frame_stem` still names the one log that owns the
    position's other sidecars.

    Args:
        session_id: Session identifier.
        frame_idx: Slider position (an index into the frame list, not a frame
            id).

    Returns:
        Owning stems, the primary log's first. Falls back to the single owner
        when no owner sets are cached -- which is the single-log case, and any
        session cached by an older build.
    """
    owner_sets = get_log_info(session_id).get("frame_owner_sets") or []
    if frame_idx is not None and 0 <= frame_idx < len(owner_sets):
        owners = [stem for stem in owner_sets[frame_idx] if stem]
        if owners:
            return owners

    stem = get_frame_stem(session_id, frame_idx)
    return [stem] if stem else []


def get_log_stems(session_id: str) -> List[str]:
    """
    List every loaded log's stem, the primary's first.

    Args:
        session_id: Session identifier.

    Returns:
        De-duplicated stems. The primary leads so that anything resolving a
        clash by iteration order -- the HTML export's stills, say -- settles on
        the same log the rest of the app treats as authoritative.
    """
    info = get_log_info(session_id)
    stems: List[str] = []
    ordered = [info.get("stem", "")]
    for owners in info.get("frame_owner_sets") or []:
        ordered.extend(owners)
    ordered.extend(info.get("frame_stems") or [])
    for stem in ordered:
        if stem and stem not in stems:
            stems.append(stem)
    return stems


def get_frame_positions(session_id: str, stem: str) -> List[int]:
    """
    List the slider positions one log recorded.

    Membership, not ownership: a position two logs share counts for both, so
    each log's video and curve range are measured against its own frames rather
    than against only the ones it won.

    Args:
        session_id: Session identifier.
        stem: Log stem.

    Returns:
        Slider positions in ascending order. When no per-frame mapping is
        cached the log owns every position, so the whole range is returned.
    """
    info = get_log_info(session_id)
    owner_sets = info.get("frame_owner_sets") or []
    if owner_sets:
        return [idx for idx, owners in enumerate(owner_sets) if stem in owners]

    frame_stems = info.get("frame_stems") or []
    if not frame_stems:
        frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])
        return list(range(len(frame_list))) if frame_list is not None else []
    return [idx for idx, owner in enumerate(frame_stems) if owner == stem]


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

    store = CloudStore(
        manifest.cloud_path(stem),
        manifest.cloud_dataset_pattern(),
        manifest.cloud_columns(),
    )
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


def has_reference_sidecar(manifest: Optional[Manifest], stems: List[str]) -> bool:
    """
    Whether any loaded log has a reference-pose sidecar on disk.

    Asked alongside :func:`get_combined_reference_bounds`, which answers None
    for two different situations the renderer has to tell apart: a dataset with
    no sidecar anywhere, and one whose sidecar pairs with no frame because its
    frame column is unmapped. The first draws its declared reference unplaced;
    the second hides it, the sidecar's own pairing being the thing that is
    unset.

    Args:
        manifest: Dataset manifest, or None.
        stems: Log stems in play.

    Returns:
        True when at least one stem has a sidecar file.
    """
    if manifest is None:
        return False
    return any(stem and manifest.has_reference_pose(stem) for stem in stems)


def get_combined_reference_bounds(
    manifest: Optional[Manifest], stems: List[str]
) -> Optional[Dict[str, Any]]:
    """
    Position extent of the reference across every loaded log.

    The 3D scene's axis ranges are fixed once for the whole session, so with
    logs combined they have to cover wherever *any* of the references travels
    or the second log's reference is clipped the moment the slider reaches it.

    Args:
        manifest: Dataset manifest, or None.
        stems: Log stems in play.

    Returns:
        ``{"x": (min, max), "y": ..., "z": ...}`` spanning every log's sidecar,
        or None when no log has one.
    """
    merged: Dict[str, Any] = {}
    for stem in stems:
        bounds = get_reference_bounds(manifest, stem)
        if bounds is None:
            continue
        for axis, extent in bounds.items():
            if not extent:
                continue
            if axis not in merged:
                merged[axis] = tuple(extent)
            else:
                low, high = merged[axis]
                merged[axis] = (min(low, extent[0]), max(high, extent[1]))
    return merged or None


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


def _video_frame_for(local: int, local_total: int, video_frames: int) -> int:
    """
    Map one of a log's frames onto a frame of its recording.

    The same count-to-count mapping the camera panel seeks with, restated
    server-side for the export. Kept deliberately identical -- including
    rounding halves up the way ``Math.round`` does rather than to even the way
    Python's ``round`` does -- so an exported still is the picture the panel was
    showing at that slider position, not its neighbour.

    Args:
        local: 0-based ordinal of the frame within the log's own frames.
        local_total: How many frames that log owns.
        video_frames: Frame count of its recording.

    Returns:
        0-based video frame index.
    """
    span = local_total - 1 if local_total > 1 else 1
    ratio = min(1.0, max(0.0, local / span))
    return int(ratio * (video_frames - 1) + 0.5)


def get_export_frame_images(
    manifest: Optional[Manifest],
    session_id: str,
    stream_id: Optional[str] = None,
    max_width: int = 640,
) -> Dict[Any, str]:
    """
    Extract one still per frame from the logs' recordings, base64 encoded.

    The camera panel plays a video the browser seeks; the HTML export is a
    single file with no server behind it, so its pictures have to travel inside
    it as data URIs. Each slider position is mapped onto a video frame exactly
    as the panel maps it, and the frames are pulled out in one ffmpeg pass per
    log.

    Frames that map onto the same video frame -- a log sampled faster than the
    camera ran -- share one encoded string rather than decoding it twice.

    Args:
        manifest: Dataset manifest, or None.
        session_id: Session identifier.
        stream_id: Which image stream to extract, as chosen in the camera
            panel. Falls back to each log's default stream when it has no
            stream by that id.
        max_width: Width to fit the stills within; see
            :func:`dataio.video.extract_frames`.

    Returns:
        Mapping of frame id -> ``data:image/jpeg;base64,...``. Empty when no
        loaded log has a recording, or when ffmpeg is unavailable -- the export
        then simply carries no pictures.
    """
    frame_list = cache_get(session_id, CACHE_KEYS["frame_list"])
    if manifest is None or frame_list is None or len(frame_list) == 0:
        return {}

    images: Dict[Any, str] = {}
    for stem in get_log_stems(session_id):
        streams = manifest.image_streams(stem)
        if not streams:
            continue

        selected = next((s for s in streams if s["id"] == stream_id), streams[0])
        source = selected.get("file", "")
        video_frames = image_stream_frame_count(source)
        if not video_frames:
            continue

        positions = get_frame_positions(session_id, stem)
        if not positions:
            continue

        # Several slider positions can land on one video frame, so gather the
        # frame ids per video frame and extract each picture once.
        wanted: Dict[int, List[Any]] = {}
        for local, position in enumerate(positions):
            if position >= len(frame_list):
                continue
            key = _video_frame_for(local, len(positions), video_frames)
            wanted.setdefault(key, []).append(frame_list[position])

        with tempfile.TemporaryDirectory(prefix="sv-export-") as staging:
            extracted = extract_frames(
                source, wanted.keys(), staging, max_width=max_width
            )
            for key, path in extracted.items():
                try:
                    with open(path, "rb") as handle:
                        encoded = base64.b64encode(handle.read()).decode()
                except OSError:
                    continue
                uri = f"data:image/jpeg;base64,{encoded}"
                for frame_id in wanted[key]:
                    # A frame two logs recorded is claimed by both. The export
                    # has room for one still per frame, so the first log to
                    # offer one keeps it -- and `get_log_stems` leads with the
                    # primary, which is the log the rest of the app defers to.
                    images.setdefault(frame_id, uri)

    return images


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
