"""3D Scatter Figure Arguments

Resolves everything the 3D scene needs that is not the data itself: which
columns are the axes, how they are labelled, what colours them, how far each
axis has to reach, and where -- if anywhere -- the reference overlay is drawn.

It sits between the callbacks and :mod:`viz.graph_data` /
:mod:`viz.graph_layout`: both of those take the dict built here, so this is the
single place the three sources of truth about a reference (what the manifest
declared, whether a sidecar exists, whether that sidecar yielded poses) are seen
together and collapsed into one ``ref_source``.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Dict, List, Optional, Any, Tuple, Union

import numpy as np

from settings import KEY_TYPES

from dataio.manifest import normalize_reference_display

from utils.filters import clamp_frame_index


def prepare_figure_kwargs(
    config: Dict[str, Any],
    # Data parameters
    num_keys: List[str],
    num_values: List[Tuple[float, float]],
    # Color and visualization parameters
    c_key: str,
    size_vary: bool,
    # Animation parameters
    frame_list: Union[List[float], "np.ndarray"],
    slider_arg: int = 0,
    # Reference sidecar
    ref_bounds: Optional[Dict[str, Any]] = None,
    has_sidecar: bool = False,
) -> Dict[str, Any]:
    """
    Prepare keyword arguments for creating a 3D scatter plot figure.

    Args:
        config: Configuration dictionary containing plot settings and key definitions.
        num_keys: List of numerical column names.
        num_values: List of (min, max) tuples for numerical value ranges.
        c_key: Column name for color mapping.
        size_vary: Whether to vary marker sizes based on groups.
        frame_list: List or array of frame values for animation.
        slider_arg: Current slider position index. Defaults to 0.
        ref_bounds: Position extent of the reference sidecars, as
            ``{"x": (min, max), ...}``. Its presence means a sidecar places the
            reference, and the axis ranges make room for wherever it travels.
        has_sidecar: Whether any loaded log has a reference sidecar on disk.
            Together with ``ref_bounds`` this separates the two ways a log can
            have no poses: no sidecar at all, and a sidecar whose frame column
            pairs with nothing. See ``ref_source`` below.

    Returns:
        Dictionary containing all necessary keyword arguments for plotting.
        ``ref_source`` in it says where the reference overlay comes from and is
        the only thing a renderer should branch on:

        - ``"sidecar"`` -- poses place it, read per frame.
        - ``"origin"`` -- the manifest declares a reference and no log has a
          sidecar, so it is drawn unplaced at the origin. A declared reference
          that never appears reads as the block having been ignored.
        - ``None`` -- draw nothing. Either the dataset never declared a
          reference, or it has a sidecar that pairs with no frame: the frame
          picker reading ``None`` is the mapping being unset, and a reference
          whose own file cannot be paired with the table is hidden rather than
          parked at the origin, where it would look placed.
    """
    keys_dict = config["keys"]

    def get_axis_range(key: str) -> List[float]:
        """The filter range of one axis column."""
        key_idx = num_keys.index(key)
        return [num_values[key_idx][0], num_values[key_idx][1]]

    # How the reference is drawn comes from the dataset manifest; where it sits
    # comes from the ref pickers below.
    ref_display = normalize_reference_display(config.get("reference"))

    # Initialize figure kwargs with basic settings
    fig_kwargs = {
        "ref_name": ref_display["name"],
        "ref_display": ref_display,
        "size_vary": size_vary,
    }

    # Setup axis keys and labels
    x_key = config.get("x_3d", num_keys[0])
    y_key = config.get("y_3d", num_keys[1])
    z_key = config.get("z_3d", num_keys[2])

    fig_kwargs.update(
        {
            "x_key": x_key,
            "x_label": keys_dict[x_key].get("description", x_key),
            "y_key": y_key,
            "y_label": keys_dict[y_key].get("description", y_key),
            "z_key": z_key,
            "z_label": keys_dict[z_key].get("description", z_key),
        }
    )

    # Setup color mapping
    fig_kwargs.update(
        {
            "c_key": c_key,
            "c_label": keys_dict[c_key].get("description", c_key),
            "c_type": keys_dict[c_key].get("type", KEY_TYPES["NUM"]),
        }
    )

    # Where the reference comes from -- resolved once, here, because this is the
    # only place that can see all three inputs at once: what the manifest
    # declared, whether a sidecar exists, and whether it yielded any poses.
    from_sidecar = ref_bounds is not None
    if from_sidecar:
        ref_source = "sidecar"
    elif has_sidecar or not ref_display.get("declared"):
        # A sidecar with no poses is one whose frame column pairs with nothing.
        # That is the mapping being unset, not a dataset that never says where
        # its reference goes, so the overlay is hidden rather than sent to the
        # origin -- a body sitting at (0, 0, 0) reads as placed.
        ref_source = None
    else:
        ref_source = "origin"

    fig_kwargs["ref_source"] = ref_source

    # Calculate axis ranges
    fig_kwargs.update(
        {
            "x_range": get_axis_range(x_key),
            "y_range": get_axis_range(y_key),
            "z_range": get_axis_range(z_key),
        }
    )

    # A reference read from a sidecar is not a column of the table, so nothing
    # above has accounted for where it goes. Widen the ranges to cover its whole
    # path -- fixed axes mean a reference that leaves the data's extent would
    # otherwise vanish partway through playback.
    if from_sidecar:
        for axis, range_key in zip(("x", "y", "z"), ("x_range", "y_range", "z_range")):
            extent = ref_bounds.get(axis)
            if not extent:
                continue
            low, high = fig_kwargs[range_key]
            fig_kwargs[range_key] = [min(low, extent[0]), max(high, extent[1])]

    # A mesh reference occupies space a dot does not, and the 3D scene fixes its
    # axes (autorange is off), so whatever the mesh adds beyond the data has to
    # be made room for here or it is simply clipped away. An unplaced reference
    # of either shape needs the same treatment for a different reason: it is
    # drawn at the origin, which the data's own extent need not contain.
    if ref_source is not None:
        # A mesh that turns reaches further along an axis than its own extent on
        # that axis, so budget for the worst case: the distance to its furthest
        # vertex, which bounds every orientation. A marker carries no geometry,
        # so its extent is the origin itself.
        radius = ref_display.get("radius", 0.0)
        extent = ref_display.get("extent") or [[0.0, 0.0]] * 3
        for axis, range_key in enumerate(("x_range", "y_range", "z_range")):
            low, high = fig_kwargs[range_key]
            if ref_source == "origin":
                # Drawn at the origin, so the range has to reach it where it
                # actually is rather than pad by it wherever the data sits.
                fig_kwargs[range_key] = [
                    min(low, extent[axis][0]),
                    max(high, extent[axis][1]),
                ]
            else:
                fig_kwargs[range_key] = [
                    min(low, low - radius),
                    max(high, high + radius),
                ]

    # Setup color range
    if fig_kwargs["c_type"] == KEY_TYPES["NUM"]:
        c_idx = num_keys.index(c_key)
        fig_kwargs["c_range"] = [num_values[c_idx][0], num_values[c_idx][1]]
    else:
        fig_kwargs["c_range"] = [0, 0]

    # Setup plot name/title. The position is clamped again here so a title is
    # never the thing that raises -- callers hand this whatever the slider held.
    slider_label = keys_dict[config["slider"]]["description"]
    frame_pos = clamp_frame_index(frame_list, slider_arg)
    fig_kwargs["name"] = (
        f"Index: {slider_arg}"
        if frame_pos is None
        else f"Index: {frame_pos} ({slider_label}: {frame_list[frame_pos]})"
    )

    return fig_kwargs
