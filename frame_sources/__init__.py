"""Per-Frame Data Sources

Bridges the session cache to the :mod:`dataio` stores, and defines which data
gets re-read on which trigger.

The split matters for performance. The table is refiltered whenever a filter
changes; the cloud, curves, images, and reference pose are display-only and only
ever change when the frame changes. Dragging a filter slider therefore never
touches the cloud or curve path.

One module per store, mirroring :mod:`dataio` and the manifest's own blocks:

- :mod:`~frame_sources.session`    which manifest, which log owns which frame
- :mod:`~frame_sources.cloud`      the point-cloud backdrop
- :mod:`~frame_sources.reference`  the moving origin and its axis bounds
- :mod:`~frame_sources.image`      camera streams and export stills
- :mod:`~frame_sources.curve`      per-frame 1D curves

Everything resolves through :mod:`~frame_sources.session`, which is the only one
the other four depend on. The names below are re-exported so callers import from
the package rather than reaching into a submodule.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from frame_sources.session import (
    cache_manifest,
    get_manifest,
    cache_log_info,
    build_frame_owner_sets,
    get_log_info,
    get_log_stem,
    get_frame_stem,
    get_frame_stems,
    get_log_stems,
    get_frame_positions,
)
from frame_sources.cloud import (
    get_cloud_points,
    get_cloud_trace,
)
from frame_sources.reference import (
    get_reference_store,
    get_reference_mapping,
    get_reference_pose,
    get_reference_bounds,
    has_reference_sidecar,
    get_combined_reference_bounds,
)

# `_video_frame_for` is the slider-to-video seek mapping itself. It stays
# private to the app -- nothing outside this package calls it in anger -- but the
# two test modules that pin the mapping's behaviour import it from here, so it
# is re-exported rather than reached for through the submodule.
from frame_sources.image import (
    playable_image_file,
    image_stream_frame_count,
    _video_frame_for,
    get_export_frame_images,
)
from frame_sources.curve import (
    get_curve_sources,
    get_curve_plots,
    get_curve_y_range,
    get_curve_figure,
    get_curve_figure_multi,
)

__all__ = [
    "cache_manifest",
    "get_manifest",
    "cache_log_info",
    "build_frame_owner_sets",
    "get_log_info",
    "get_log_stem",
    "get_frame_stem",
    "get_frame_stems",
    "get_log_stems",
    "get_frame_positions",
    "get_cloud_points",
    "get_cloud_trace",
    "get_reference_store",
    "get_reference_mapping",
    "get_reference_pose",
    "get_reference_bounds",
    "has_reference_sidecar",
    "get_combined_reference_bounds",
    "playable_image_file",
    "image_stream_frame_count",
    "_video_frame_for",
    "get_export_frame_images",
    "get_curve_sources",
    "get_curve_plots",
    "get_curve_y_range",
    "get_curve_figure",
    "get_curve_figure_multi",
]
