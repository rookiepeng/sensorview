"""Reference Pose

The moving origin -- the host vehicle, usually -- read from a log's
``.reference.parquet`` sidecar, plus the axis bounds the 3D view widens to cover
wherever that pose travels.

The pose has room for one answer per frame, so it resolves against the primary
log rather than every combined one.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Any, Dict, List, Optional

import os

from dataio.manifest import Manifest
from dataio.reference import ReferenceStore


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
