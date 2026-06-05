"""SensorView Graph Layout Module

Layout configurations for plot types with focus on 3D scatter plot layouts,
axis range management, aspect ratio calculation, and image overlay support.

Key function: get_scatter3d_layout()

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Dict, Optional, Any, Tuple


def get_scatter3d_layout(
    x_range: Tuple[float, float],
    y_range: Tuple[float, float],
    z_range: Tuple[float, float] = (-20, 20),
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Generate an optimized layout configuration for a 3D scatter plot.

    Args:
        x_range: Tuple of (min, max) values for x-axis range.
        y_range: Tuple of (min, max) values for y-axis range.
        z_range: Tuple of (min, max) values for z-axis range. Defaults to (-20, 20).
        **kwargs: Additional layout parameters:
            - image: Optional image source for plot overlay
            - title: Optional plot title
            - x_label: Optional x-axis label
            - y_label: Optional y-axis label
            - z_label: Optional z-axis label

    Returns:
        Dictionary containing the complete layout configuration for a 3D scatter plot.
    """
    # Calculate ranges once
    x_size = x_range[1] - x_range[0]
    y_size = y_range[1] - y_range[0]
    z_size = z_range[1] - z_range[0]
    scale = min(x_size, y_size, z_size)

    # Create axis configuration template
    def create_axis_config(
        range_vals: Tuple[float, float], title: Optional[str]
    ) -> Dict[str, Any]:
        return {"range": list(range_vals), "title": {"text": title}, "autorange": False}

    # Guard against division-by-zero when a filter collapses an axis to a single value
    # (min == max), which makes scale == 0. Fall back to a 1:1:1 aspect ratio.
    if scale == 0:
        aspect_ratio = {"x": 1.0, "y": 1.0, "z": 1.0}
    else:
        aspect_ratio = {
            "x": x_size / scale,
            "y": y_size / scale,
            "z": z_size / scale,
        }

    # Build scene configuration
    scene_config = {
        "xaxis": create_axis_config(x_range, kwargs.get("x_label")),
        "yaxis": create_axis_config(y_range, kwargs.get("y_label")),
        "zaxis": create_axis_config(z_range, kwargs.get("z_label")),
        "aspectmode": "manual",
        "aspectratio": aspect_ratio,
    }

    # Efficiently create image configuration
    image = kwargs.get("image")
    img_dict = (
        [
            {
                "source": image,
                "xref": "x domain",
                "yref": "y domain",
                "x": 0,
                "y": 1,
                "xanchor": "left",
                "yanchor": "top",
                "sizex": 0.3,
                "sizey": 0.3,
            }
        ]
        if image is not None
        else None
    )

    # Return optimized layout configuration
    return {
        "title": kwargs.get("title"),
        "scene": scene_config,
        "margin": {"l": 0, "r": 0, "b": 0, "t": 40},
        "legend": {"x": 0, "y": 0},
        "images": img_dict,
        "uirevision": "no_change",
    }
