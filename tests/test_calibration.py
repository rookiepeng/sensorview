"""Sensor extrinsics.

Overlaid point clouds only line up if every sensor's mounting transform agrees on
one convention: ZYX intrinsic, x forward, y left, z up. A silent change to the
multiplication order would still produce plausible-looking clouds that are wrong,
so the composition order is pinned here explicitly rather than assumed.

Author: Zhengyu Peng
License: GPL-3.0
"""

import numpy as np
import pytest

from dataio.calibration import Calibration, apply_transform, rotation_matrix


class TestRotationMatrix:
    def test_zero_rotation_is_identity(self):
        np.testing.assert_allclose(
            rotation_matrix(0.0, 0.0, 0.0), np.eye(3), atol=1e-12
        )

    def test_yaw_turns_forward_to_left(self):
        # +90 deg about z takes x forward onto y left.
        rotated = rotation_matrix(0.0, 0.0, np.pi / 2) @ np.array([1.0, 0.0, 0.0])
        np.testing.assert_allclose(rotated, [0.0, 1.0, 0.0], atol=1e-12)

    def test_roll_turns_left_to_up(self):
        rotated = rotation_matrix(np.pi / 2, 0.0, 0.0) @ np.array([0.0, 1.0, 0.0])
        np.testing.assert_allclose(rotated, [0.0, 0.0, 1.0], atol=1e-12)

    def test_pitch_turns_forward_to_down(self):
        rotated = rotation_matrix(0.0, np.pi / 2, 0.0) @ np.array([1.0, 0.0, 0.0])
        np.testing.assert_allclose(rotated, [0.0, 0.0, -1.0], atol=1e-12)

    def test_composition_order_is_zyx(self):
        # Rz(yaw) @ Ry(pitch) @ Rx(roll). Applying roll first sends y up to z up,
        # which yaw then leaves alone. The reverse order would give [-1, 0, 0],
        # so this value is what distinguishes the two conventions.
        rotated = rotation_matrix(np.pi / 2, 0.0, np.pi / 2) @ np.array([0.0, 1.0, 0.0])
        np.testing.assert_allclose(rotated, [0.0, 0.0, 1.0], atol=1e-12)

    def test_is_orthonormal_with_unit_determinant(self):
        matrix = rotation_matrix(0.3, -0.7, 1.1)
        np.testing.assert_allclose(matrix @ matrix.T, np.eye(3), atol=1e-12)
        # +1 rather than -1: a rotation, never a reflection.
        assert np.isclose(np.linalg.det(matrix), 1.0)


class TestCalibrationFromDict:
    def test_none_yields_identity(self):
        assert Calibration.from_dict(None).is_identity

    def test_empty_dict_yields_identity(self):
        assert Calibration.from_dict({}).is_identity

    def test_reads_translation_and_rotation(self):
        cal = Calibration.from_dict(
            {"translation": [1.0, 2.0, 3.0], "rotation_rpy_deg": [0.0, 0.0, 90.0]}
        )
        np.testing.assert_allclose(cal.translation, [1.0, 2.0, 3.0])
        np.testing.assert_allclose(cal.rotation_rpy_deg, [0.0, 0.0, 90.0])

    def test_partial_block_defaults_the_missing_half(self):
        cal = Calibration.from_dict({"translation": [1.0, 0.0, 0.0]})
        np.testing.assert_allclose(cal.rotation_rpy_deg, [0.0, 0.0, 0.0])

    def test_translation_only_is_not_identity(self):
        assert not Calibration.from_dict({"translation": [1.0, 0.0, 0.0]}).is_identity

    def test_rotation_only_is_not_identity(self):
        assert not Calibration.from_dict(
            {"rotation_rpy_deg": [0.0, 0.0, 90.0]}
        ).is_identity

    def test_degrees_are_converted_to_radians(self):
        cal = Calibration(rotation_rpy_deg=[0.0, 0.0, 90.0])
        rotated = cal.rotation_matrix() @ np.array([1.0, 0.0, 0.0])
        np.testing.assert_allclose(rotated, [0.0, 1.0, 0.0], atol=1e-12)


class TestApplyTransform:
    @pytest.fixture
    def points(self):
        return np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])

    def test_identity_returns_the_same_object(self, points):
        # Documented contract: no copy on the hot per-frame path.
        assert apply_transform(points, Calibration()) is points

    def test_empty_input_is_returned_untouched(self):
        empty = np.empty((0, 3))
        assert apply_transform(empty, Calibration(translation=[1.0, 2.0, 3.0])) is empty

    def test_translation_only(self, points):
        moved = apply_transform(points, Calibration(translation=[10.0, 0.0, 0.0]))
        np.testing.assert_allclose(
            moved, [[11.0, 0.0, 0.0], [10.0, 1.0, 0.0], [10.0, 0.0, 1.0]]
        )

    def test_rotation_only(self, points):
        turned = apply_transform(points, Calibration(rotation_rpy_deg=[0.0, 0.0, 90.0]))
        np.testing.assert_allclose(
            turned, [[0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]], atol=1e-12
        )

    def test_rotation_is_applied_before_translation(self, points):
        # A sensor mounted 10 m forward and yawed 90 deg: the point at its own
        # x=1 lands at y=1 relative to the mount, then the mount offset is added.
        cal = Calibration(
            translation=[10.0, 0.0, 0.0], rotation_rpy_deg=[0.0, 0.0, 90.0]
        )
        placed = apply_transform(points, cal)
        np.testing.assert_allclose(placed[0], [10.0, 1.0, 0.0], atol=1e-12)

    def test_preserves_shape(self, points):
        assert apply_transform(
            points, Calibration(translation=[1.0, 1.0, 1.0])
        ).shape == (3, 3)

    def test_accepts_integer_input(self):
        # Manifests and HDF5 stores can hand over integer arrays; the transform
        # must not truncate the result back to int.
        integers = np.array([[1, 0, 0]])
        moved = apply_transform(integers, Calibration(translation=[0.5, 0.0, 0.0]))
        np.testing.assert_allclose(moved, [[1.5, 0.0, 0.0]])
