"""Slider positions compressed into per-log runs for the camera seek.

The camera panel ships one descriptor per log to the browser, and the browser
turns a slider position into a position within that log's own recording. Runs
are what carry the mapping: get ``local_start`` wrong and the video is seeked to
the wrong moment for every frame after the first gap, silently, with a picture
that still looks plausible.

Author: Zhengyu Peng
License: GPL-3.0
"""

from frame_sources import _video_frame_for
from view_callbacks.camera_view import _stem_runs


def _local_for(runs, index):
    """Resolve a slider position to the log's own frame number, as the JS does."""
    for run in runs:
        if run["start"] <= index < run["start"] + run["count"]:
            return run["local_start"] + (index - run["start"])
    return None


class TestContiguous:
    """A log owning one unbroken stretch is one run."""

    def test_whole_slider_is_a_single_run(self):
        assert _stem_runs([0, 1, 2, 3]) == [{"start": 0, "count": 4, "local_start": 0}]

    def test_stretch_starting_partway_keeps_its_offset(self):
        assert _stem_runs([5, 6, 7]) == [{"start": 5, "count": 3, "local_start": 0}]

    def test_empty_log_has_no_runs(self):
        assert _stem_runs([]) == []

    def test_single_position(self):
        assert _stem_runs([9]) == [{"start": 9, "count": 1, "local_start": 0}]


class TestGaps:
    """Positions another log covers split the run without skipping local frames."""

    def test_gap_starts_a_new_run(self):
        assert _stem_runs([0, 1, 4, 5]) == [
            {"start": 0, "count": 2, "local_start": 0},
            {"start": 4, "count": 2, "local_start": 2},
        ]

    def test_interleaved_log_yields_one_run_per_frame(self):
        # Every other position: the log's own frames are still 0,1,2 in order.
        runs = _stem_runs([0, 2, 4])
        assert runs == [
            {"start": 0, "count": 1, "local_start": 0},
            {"start": 2, "count": 1, "local_start": 1},
            {"start": 4, "count": 1, "local_start": 2},
        ]

    def test_local_frames_run_end_to_end_across_gaps(self):
        positions = [0, 1, 5, 6, 7, 20]
        runs = _stem_runs(positions)
        # The whole point of local_start: the log is measured against its own
        # recording, so its frames are numbered 0..n-1 whatever the gaps.
        assert [_local_for(runs, p) for p in positions] == list(range(len(positions)))

    def test_positions_the_log_does_not_own_resolve_to_nothing(self):
        runs = _stem_runs([0, 1, 5])
        assert _local_for(runs, 3) is None


class TestAgainstTheVideoMapping:
    """Runs feed `_video_frame_for`, so the pair has to agree end to end."""

    def test_interleaved_log_spans_its_whole_recording(self):
        # Two logs alternating over 10 slider positions; this one owns 5 of
        # them, and those 5 must cover its 30-frame clip from first to last.
        positions = [0, 2, 4, 6, 8]
        runs = _stem_runs(positions)
        total = len(positions)
        mapped = [_video_frame_for(_local_for(runs, p), total, 30) for p in positions]
        assert mapped[0] == 0
        assert mapped[-1] == 29
        assert mapped == sorted(mapped)
