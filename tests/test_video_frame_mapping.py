"""Frame-to-video mapping parity.

``frame_sources._video_frame_for`` is the server-side restatement of the mapping
the camera panel seeks with, which lives as JavaScript in
``view_callbacks/camera_view.py`` (``const k = Math.round(ratio * (videoFrames - 1))``).
The same formula existing twice, in two languages, in two files, with nothing
mechanical keeping the pair in step, is what these tests are for: an exported
still has to be the picture the panel was showing at that slider position, not
its neighbour.

Author: Zhengyu Peng
License: GPL-3.0
"""

import pytest

from frame_sources import _video_frame_for


class TestRoundingMatchesJavaScript:
    """The half-up rounding rule, which Python's built-in round() does not share."""

    # JavaScript's Math.round breaks halves upward; Python's round() breaks them
    # toward even. Both cases below land exactly on .5, so they are precisely
    # where a well-meaning rewrite to round() would silently start returning the
    # neighbouring video frame.
    @pytest.mark.parametrize(
        "local, local_total, video_frames, expected, python_round_would_give",
        [
            # ratio 0.5 * (2 - 1) = 0.5 -> half-up 1, round() 0
            (1, 3, 2, 1, 0),
            # ratio 0.5 * (6 - 1) = 2.5 -> half-up 3, round() 2
            (1, 3, 6, 3, 2),
        ],
    )
    def test_halves_round_up_not_to_even(
        self, local, local_total, video_frames, expected, python_round_would_give
    ):
        assert _video_frame_for(local, local_total, video_frames) == expected
        # Guards the premise: if these ever stop differing, the test above has
        # quietly stopped testing anything.
        assert expected != python_round_would_give


class TestEndpoints:
    """The first and last data frames must land on the first and last video frames."""

    def test_first_frame_maps_to_first_video_frame(self):
        assert _video_frame_for(0, 10, 30) == 0

    def test_last_frame_maps_to_last_video_frame(self):
        assert _video_frame_for(9, 10, 30) == 29

    def test_single_frame_log_maps_to_first_video_frame(self):
        # local_total of 1 would make span zero; the guard substitutes 1 so this
        # divides rather than raising.
        assert _video_frame_for(0, 1, 30) == 0

    def test_single_frame_video(self):
        assert _video_frame_for(5, 10, 1) == 0


class TestClamping:
    """Out-of-range positions saturate instead of indexing off either end."""

    def test_negative_local_clamps_to_first(self):
        assert _video_frame_for(-5, 10, 30) == 0

    def test_local_past_end_clamps_to_last(self):
        assert _video_frame_for(99, 10, 30) == 29


class TestMonotonicity:
    """Scrubbing forward never seeks backward."""

    def test_mapping_is_non_decreasing(self):
        mapped = [_video_frame_for(i, 50, 37) for i in range(50)]
        assert mapped == sorted(mapped)

    def test_mapping_stays_in_video_range(self):
        for total, frames in ((50, 37), (7, 120), (120, 7)):
            for i in range(total):
                assert 0 <= _video_frame_for(i, total, frames) <= frames - 1
