"""Frame index derivation.

The frame index is derived from the Parquet table rather than declared in the
manifest, so these functions sit under every view that scrubs, seeks or exports.
The fallbacks matter as much as the happy path: a log with no time column, a
dropped frame, or a stalled sensor all have to yield a usable rate rather than a
division by zero.

Author: Zhengyu Peng
License: GPL-3.0
"""

import numpy as np
import pandas as pd
import pytest

from dataio.frames import (
    DEFAULT_FPS,
    build_frame_index,
    compute_timestamps,
    derive_fps,
    find_time_key,
    unique_frame_ids,
)


@pytest.fixture
def timed_frames():
    """Three frames at 10 Hz, two rows each, with a wall-clock column."""
    return pd.DataFrame(
        {
            "Frame": [0, 0, 1, 1, 2, 2],
            "Time": [100.0, 100.0, 100.1, 100.1, 100.2, 100.2],
            "x": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        }
    )


class TestFindTimeKey:
    def test_returns_column_when_present(self, timed_frames):
        assert find_time_key(timed_frames) == "Time"

    def test_returns_none_when_absent(self, timed_frames):
        assert find_time_key(timed_frames.drop(columns=["Time"])) is None

    def test_honours_custom_key(self, timed_frames):
        assert find_time_key(timed_frames, "x") == "x"
        assert find_time_key(timed_frames, "nope") is None


class TestUniqueFrameIds:
    def test_deduplicates_and_sorts(self):
        data = pd.DataFrame({"Frame": [2, 0, 1, 0, 2]})
        assert list(unique_frame_ids(data, "Frame")) == [0, 1, 2]

    def test_missing_key_raises_with_available_columns(self, timed_frames):
        with pytest.raises(KeyError) as excinfo:
            unique_frame_ids(timed_frames, "NoSuchColumn")
        # The message names the columns that do exist; that is the whole point of
        # raising here rather than letting pandas surface a bare KeyError.
        assert "Frame" in str(excinfo.value)


class TestComputeTimestamps:
    def test_rebases_wall_clock_to_zero(self, timed_frames):
        stamps = compute_timestamps(timed_frames, [0, 1, 2], "Frame", "Time")
        assert stamps == [0.0, 0.1, 0.2]

    def test_applies_time_scale_after_rebasing(self):
        # A millisecond epoch: rebasing first is what keeps the subtraction from
        # losing precision.
        data = pd.DataFrame(
            {
                "Frame": [0, 1, 2],
                "Time": [1_700_000_000_000, 1.7e12 + 100, 1.7e12 + 200],
            }
        )
        stamps = compute_timestamps(data, [0, 1, 2], "Frame", "Time", time_scale=0.001)
        assert stamps == [0.0, 0.1, 0.2]

    def test_uses_per_frame_minimum(self):
        # Rows within a frame are not ordered; the frame's time is its earliest.
        data = pd.DataFrame({"Frame": [0, 0, 1, 1], "Time": [5.0, 4.0, 6.0, 5.5]})
        assert compute_timestamps(data, [0, 1], "Frame", "Time") == [0.0, 1.5]

    def test_falls_back_to_index_over_fps_without_time_column(self, timed_frames):
        stamps = compute_timestamps(
            timed_frames.drop(columns=["Time"]), [0, 1, 2], "Frame", None, fps=4.0
        )
        assert stamps == [0.0, 0.25, 0.5]

    def test_falls_back_when_a_frame_has_no_timestamp(self, timed_frames):
        # Frame 3 is absent from the table, so its lookup is NaN and the whole
        # vector is untrustworthy -- index/fps is used instead of a partial one.
        stamps = compute_timestamps(
            timed_frames, [0, 1, 2, 3], "Frame", "Time", fps=4.0
        )
        assert stamps == [0.0, 0.25, 0.5, 0.75]

    def test_empty_frame_list_yields_empty_timestamps(self, timed_frames):
        assert compute_timestamps(timed_frames, [], "Frame", "Time") == []


class TestDeriveFps:
    def test_regular_spacing(self):
        assert derive_fps([0.0, 0.1, 0.2, 0.3]) == 10.0

    def test_median_absorbs_a_dropped_frame(self):
        # One doubled gap must not drag the rate down to 8 Hz.
        assert derive_fps([0.0, 0.1, 0.2, 0.4, 0.5]) == 10.0

    @pytest.mark.parametrize("timestamps", [[], [0.0]])
    def test_too_few_timestamps_fall_back(self, timestamps):
        assert derive_fps(timestamps) == DEFAULT_FPS

    def test_stalled_clock_falls_back(self):
        # Every delta is zero, so there is no rate to infer.
        assert derive_fps([5.0, 5.0, 5.0]) == DEFAULT_FPS

    def test_non_finite_deltas_fall_back(self):
        assert derive_fps([0.0, float("inf")]) == DEFAULT_FPS
        assert derive_fps([0.0, float("nan")]) == DEFAULT_FPS

    def test_non_increasing_timestamps_fall_back(self):
        assert derive_fps([0.0, -1.0, -2.0]) == DEFAULT_FPS

    def test_custom_fallback_is_honoured(self):
        assert derive_fps([], fallback=25.0) == 25.0

    def test_result_is_rounded_to_three_decimals(self):
        # 1/0.3 is 3.333... and must not leak full float noise into the UI.
        assert derive_fps([0.0, 0.3, 0.6]) == 3.333


class TestBuildFrameIndex:
    def test_derives_ids_timestamps_and_rate_together(self, timed_frames):
        frame_ids, timestamps, fps = build_frame_index(timed_frames, "Frame")
        assert list(frame_ids) == [0, 1, 2]
        assert timestamps == [0.0, 0.1, 0.2]
        assert fps == 10.0

    def test_explicit_fps_overrides_inference(self, timed_frames):
        _, _, fps = build_frame_index(timed_frames, "Frame", fps=30.0)
        assert fps == 30.0

    def test_time_key_none_skips_the_lookup(self, timed_frames):
        # The column is present but must be ignored, falling back to index/fps.
        _, timestamps, _ = build_frame_index(
            timed_frames, "Frame", time_key=None, fps=4.0
        )
        assert timestamps == [0.0, 0.25, 0.5]

    def test_returns_ids_as_array(self, timed_frames):
        frame_ids, _, _ = build_frame_index(timed_frames, "Frame")
        assert isinstance(frame_ids, np.ndarray)
