"""Per-frame log ownership when combined logs share frame ids.

Combining logs concatenates their rows, and two logs numbering their frames the
same way collapse onto a single slider position. Which logs that position then
names decides what the camera and curve panels can draw, and which one the views
with room for a single answer fall back to -- so the ordering rule ("the primary
leads") is load-bearing rather than cosmetic.

Author: Zhengyu Peng
License: GPL-3.0
"""

import numpy as np
import pytest

from frame_sources import build_frame_owner_sets


@pytest.fixture
def shared_ids():
    """Two logs numbering frames 0-2, both claiming every id."""
    return {"0": ["other", "main"], "1": ["other", "main"], "2": ["other", "main"]}


class TestPrimaryLeads:
    """The primary log heads every set it belongs to."""

    def test_shared_frames_keep_both_logs(self, shared_ids):
        owner_sets, _ = build_frame_owner_sets([0, 1, 2], shared_ids, "main")
        assert owner_sets == [["main", "other"]] * 3

    def test_frame_stems_still_name_the_primary(self, shared_ids):
        # The head of each set is what everything keyed on a single owner reads,
        # so this is the guarantee that nothing outside the two panels changed
        # behaviour when a frame gained a second owner.
        _, frame_stems = build_frame_owner_sets([0, 1, 2], shared_ids, "main")
        assert frame_stems == ["main"] * 3

    def test_primary_leads_wherever_the_scan_put_it(self):
        # `frame_ids_by_file` appends the primary last, but nothing guarantees
        # that, so the reordering must not depend on its position.
        owners = {"0": ["main", "b", "c"], "1": ["b", "main", "c"]}
        owner_sets, _ = build_frame_owner_sets([0, 1], owners, "main")
        assert owner_sets == [["main", "b", "c"], ["main", "b", "c"]]


class TestFramesThePrimaryDoesNotOwn:
    """A log can cover a stretch the primary never recorded."""

    def test_other_log_alone_keeps_its_own_order(self):
        owners = {"0": ["main"], "1": ["other"], "2": ["other", "third"]}
        owner_sets, frame_stems = build_frame_owner_sets([0, 1, 2], owners, "main")
        assert owner_sets == [["main"], ["other"], ["other", "third"]]
        assert frame_stems == ["main", "other", "other"]

    def test_unclaimed_frame_falls_back_to_the_primary(self):
        # A frame in the loaded table that no scanned file claims: better the
        # primary's sidecars than none at all.
        owner_sets, frame_stems = build_frame_owner_sets([7], {}, "main")
        assert owner_sets == [["main"]]
        assert frame_stems == ["main"]


class TestSingleLog:
    """One loaded log is the case that must stay exactly as it was."""

    def test_no_owner_map_names_the_primary_throughout(self):
        owner_sets, frame_stems = build_frame_owner_sets([0, 1, 2], None, "main")
        assert owner_sets == [["main"], ["main"], ["main"]]
        assert frame_stems == ["main"] * 3


class TestFrameIdTypes:
    """Ids come back from Polars as Python scalars and from the table as NumPy."""

    def test_numpy_ids_match_the_string_keyed_map(self):
        owners = {"0": ["other", "main"], "1": ["main"]}
        owner_sets, _ = build_frame_owner_sets(
            np.array([0, 1], dtype=np.int64), owners, "main"
        )
        assert owner_sets == [["main", "other"], ["main"]]
