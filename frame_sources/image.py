"""Camera Streams and Stills

Serving a log's recording to the browser, and pulling stills out of it for the
self-contained HTML export.

A container the browser cannot play is transcoded once and served from the video
cache, keeping the dataset directory read-only input. Frame counts are probed
with ffmpeg and memoized, since the count only changes when the file does -- and
it is what the frame-count-to-frame-count seek mapping is built on.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Any, Dict, List, Optional

import base64
import hashlib
import os
import tempfile

from settings import CACHE_KEYS, VIDEO_CACHE_PATH

from dataio.manifest import Manifest
from dataio.video import (
    VideoEncodeError,
    extract_frames,
    is_browser_playable,
    probe_frame_count,
    transcode_to_mp4,
)

from utils import cache_get

from frame_sources.session import get_frame_positions, get_log_stems

# Video frame counts, keyed on (path, size, mtime). Probing shells out to
# ffmpeg, and the answer only changes when the file does.
_FRAME_COUNTS: Dict[Any, Optional[int]] = {}


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
