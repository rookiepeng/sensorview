"""Sensor Calibration / Extrinsics

Converts a sensor's mounting description (translation + roll/pitch/yaw) into a
4x4 homogeneous transform, so point clouds from different sensors land in the
same reference frame when overlaid.

Rotation convention is ZYX intrinsic (yaw, then pitch, then roll), which is the
usual automotive convention: x forward, y left, z up.

Author: Zhengyu Peng
License: GPL-3.0
Copyright (C) 2019 - PRESENT
"""

from typing import Any, Dict, Optional, Sequence

import numpy as np


class Calibration:
    """A sensor's extrinsic mounting transform relative to the vehicle frame."""

    def __init__(
        self,
        translation: Optional[Sequence[float]] = None,
        rotation_rpy_deg: Optional[Sequence[float]] = None,
    ) -> None:
        """
        Args:
            translation: (x, y, z) mounting offset in meters. Defaults to origin.
            rotation_rpy_deg: (roll, pitch, yaw) in degrees. Defaults to no rotation.
        """
        self.translation = np.asarray(
            translation if translation is not None else (0.0, 0.0, 0.0), dtype=float
        )
        self.rotation_rpy_deg = np.asarray(
            rotation_rpy_deg if rotation_rpy_deg is not None else (0.0, 0.0, 0.0),
            dtype=float,
        )

    @classmethod
    def from_dict(cls, cal: Optional[Dict[str, Any]]) -> "Calibration":
        """
        Build a Calibration from a manifest ``calibration`` block.

        Args:
            cal: Dictionary with optional ``translation`` and ``rotation_rpy_deg``
                keys. ``None`` yields an identity calibration.

        Returns:
            Calibration instance.
        """
        if not cal:
            return cls()
        return cls(
            translation=cal.get("translation"),
            rotation_rpy_deg=cal.get("rotation_rpy_deg"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize back to the manifest ``calibration`` block shape."""
        return {
            "translation": self.translation.tolist(),
            "rotation_rpy_deg": self.rotation_rpy_deg.tolist(),
        }

    @property
    def is_identity(self) -> bool:
        """True when the transform is a no-op and can be skipped entirely."""
        return bool(
            np.all(self.translation == 0.0) and np.all(self.rotation_rpy_deg == 0.0)
        )

    def rotation_matrix(self) -> np.ndarray:
        """
        Build the 3x3 rotation matrix from roll/pitch/yaw.

        Returns:
            3x3 rotation matrix (ZYX intrinsic: Rz(yaw) @ Ry(pitch) @ Rx(roll)).
        """
        roll, pitch, yaw = np.deg2rad(self.rotation_rpy_deg)

        c_r, s_r = np.cos(roll), np.sin(roll)
        c_p, s_p = np.cos(pitch), np.sin(pitch)
        c_y, s_y = np.cos(yaw), np.sin(yaw)

        rot_x = np.array([[1, 0, 0], [0, c_r, -s_r], [0, s_r, c_r]])
        rot_y = np.array([[c_p, 0, s_p], [0, 1, 0], [-s_p, 0, c_p]])
        rot_z = np.array([[c_y, -s_y, 0], [s_y, c_y, 0], [0, 0, 1]])

        return rot_z @ rot_y @ rot_x

    def matrix(self) -> np.ndarray:
        """
        Build the full 4x4 homogeneous transform.

        Returns:
            4x4 transform matrix mapping sensor frame -> vehicle frame.
        """
        transform = np.eye(4)
        transform[:3, :3] = self.rotation_matrix()
        transform[:3, 3] = self.translation
        return transform

    def apply(self, points: np.ndarray) -> np.ndarray:
        """
        Transform an (N, 3) array of points into the vehicle frame.

        Args:
            points: (N, 3) array of xyz coordinates.

        Returns:
            (N, 3) transformed array. Returns the input unchanged (no copy) when
            the calibration is an identity transform.
        """
        return apply_transform(points, self)


def apply_transform(points: np.ndarray, calibration: Calibration) -> np.ndarray:
    """
    Apply a calibration transform to an (N, 3) point array.

    Args:
        points: (N, 3) array of xyz coordinates. Extra columns are not accepted;
            slice them off before calling.
        calibration: Calibration describing the sensor mounting.

    Returns:
        (N, 3) transformed points, or the input array itself when the transform
        is an identity (avoids a needless copy on the hot per-frame path).
    """
    if calibration.is_identity or points.size == 0:
        return points

    points = np.asarray(points, dtype=float)
    rotated = points @ calibration.rotation_matrix().T
    return rotated + calibration.translation
