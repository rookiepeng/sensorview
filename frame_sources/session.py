"""Session State: Which Manifest, Which Log, Which Frame

What the rest of this package resolves everything else through. A session
caches its dataset manifest and, alongside it, which log owns each slider
position.

Sidecars resolve from the *stem of the log a frame came from*. Combining logs
concatenates their rows, so the slider walks one log's frames and then the next;
resolving every frame against the primary log's stem would leave the whole
second half with no cloud, no pose, no curves, and the wrong video.

Logs need not run end to end, though. Two that share a frame id collapse onto
one slider position, and there the panels that can show several logs at once --
the camera and the curve -- show all of them rather than picking a winner; see
:func:`get_frame_stems`. The primary log remains the tie-break for anything that
has room for one answer only: the point cloud, the pose, and the stills in the
HTML export.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Any, Dict, List, Optional

from settings import CACHE_KEYS

from dataio.manifest import Manifest

from utils import cache_get, cache_set


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
