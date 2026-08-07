"""Slider position clamping.

``clamp_frame_index`` exists because loading a dataset replaces the frame list and
resets the slider from two separate callbacks firing off the same trigger. For one
round the old position is read against the new list, and a shorter dataset would
index off the end. These tests pin that survival behaviour so the guard is not
mistaken for redundancy and removed.

Author: Zhengyu Peng
License: GPL-3.0
"""

import numpy as np
import pytest

from utils import clamp_frame_index


class TestNoFramesToPointAt:
    @pytest.mark.parametrize("frame_list", [None, [], np.array([])])
    def test_returns_none(self, frame_list):
        assert clamp_frame_index(frame_list, 3) is None


class TestStalePosition:
    def test_position_past_the_new_end_clamps_to_last(self):
        # The crux: a 100-frame dataset replaced by a 3-frame one, with the old
        # slider position still in flight.
        assert clamp_frame_index([0, 1, 2], 99) == 2

    def test_negative_position_clamps_to_first(self):
        assert clamp_frame_index([0, 1, 2], -5) == 0

    def test_position_within_range_is_unchanged(self):
        assert clamp_frame_index([0, 1, 2, 3, 4], 3) == 3

    def test_last_valid_position_is_kept(self):
        assert clamp_frame_index([0, 1, 2], 2) == 2


class TestMissingPosition:
    def test_none_position_starts_at_the_beginning(self):
        assert clamp_frame_index([7, 8, 9], None) == 0

    def test_none_position_on_single_frame_list(self):
        assert clamp_frame_index([7], None) == 0


class TestInputTypes:
    def test_accepts_numpy_frame_list(self):
        assert clamp_frame_index(np.array([10, 20, 30]), 99) == 2

    def test_returns_an_index_not_a_frame_id(self):
        # Frame ids need not be 0-based or contiguous; the return value indexes
        # into the list rather than naming a frame.
        assert clamp_frame_index([100, 200, 300], 1) == 1

    def test_float_position_is_truncated_to_int(self):
        result = clamp_frame_index([0, 1, 2, 3], 2.7)
        assert result == 2
        assert isinstance(result, int)
