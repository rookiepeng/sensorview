"""Frame index derivation.

The frame index is derived from the Parquet table rather than declared in the
manifest, so this sits under every view that scrubs, seeks or exports. The
failure mode worth guarding is a frame key that is not a column: pandas would
raise a bare KeyError naming nothing, which says nothing about what the log
actually offers.

Author: Zhengyu Peng
License: GPL-3.0
"""

import numpy as np
import pandas as pd
import pytest

from dataio.frames import unique_frame_ids


@pytest.fixture
def timed_frames():
    """Three frames, two rows each, with a wall-clock column."""
    return pd.DataFrame(
        {
            "Frame": [0, 0, 1, 1, 2, 2],
            "Time": [100.0, 100.0, 100.1, 100.1, 100.2, 100.2],
            "x": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        }
    )


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

    def test_returns_ids_as_array(self, timed_frames):
        assert isinstance(unique_frame_ids(timed_frames, "Frame"), np.ndarray)

    def test_empty_table_yields_no_ids(self):
        data = pd.DataFrame({"Frame": pd.Series([], dtype="int64")})
        assert list(unique_frame_ids(data, "Frame")) == []
