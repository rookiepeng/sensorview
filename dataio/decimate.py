"""Point Cloud Decimation

Cloud frames are commonly 50k-200k+ points, well past what Plotly's WebGL
scatter3d renders smoothly. Since the cloud backdrop has no runtime controls,
decimation happens once at ingest time and only the display-ready points are
stored -- no full-resolution data is kept on the read path.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Optional

import numpy as np


def voxel_downsample(points: np.ndarray, voxel_size: float) -> np.ndarray:
    """
    Keep one representative point per occupied voxel.

    Preserves spatial structure far better than random sampling at the same
    point budget, which matters for a backdrop whose whole job is conveying
    scene geometry.

    Args:
        points: (N, C) array; the first three columns are treated as xyz.
        voxel_size: Voxel edge length in meters. Non-positive disables.

    Returns:
        (M, C) array with M <= N, one point per occupied voxel.
    """
    if voxel_size <= 0 or points.shape[0] == 0:
        return points

    grid = np.floor(points[:, :3] / voxel_size).astype(np.int64)
    _, keep_idx = np.unique(grid, axis=0, return_index=True)
    keep_idx.sort()
    return points[keep_idx]


def random_downsample(
    points: np.ndarray, max_points: int, seed: Optional[int] = 0
) -> np.ndarray:
    """
    Uniformly subsample to a hard point budget.

    Applied after voxel downsampling as a backstop, so a dense scene can never
    blow past the renderer's budget.

    Args:
        points: (N, C) array.
        max_points: Maximum number of points to keep. Non-positive disables.
        seed: RNG seed, fixed by default so a given frame decimates identically
            on every ingest run.

    Returns:
        (M, C) array with M <= max_points, in original point order.
    """
    if max_points <= 0 or points.shape[0] <= max_points:
        return points

    rng = np.random.default_rng(seed)
    keep_idx = rng.choice(points.shape[0], size=max_points, replace=False)
    keep_idx.sort()
    return points[keep_idx]


def decimate(
    points: np.ndarray,
    voxel_size: float = 0.0,
    max_points: int = 0,
    seed: Optional[int] = 0,
) -> np.ndarray:
    """
    Run the full ingest-time decimation chain.

    Args:
        points: (N, C) array; first three columns are xyz.
        voxel_size: Voxel edge length in meters; 0 skips voxel downsampling.
        max_points: Hard point budget; 0 skips the budget backstop.
        seed: RNG seed for the budget backstop.

    Returns:
        Decimated (M, C) array.
    """
    points = voxel_downsample(points, voxel_size)
    return random_downsample(points, max_points, seed=seed)
