"""Background callback results are never served from a previous job.

Dash keys a background callback's result by the hash of its argument values and
expects the browser to read -- and thereby delete -- that result once. A job
whose poll chain stopped early never performs the read, so its result is left
behind under a key that repeats the moment the same arguments come round again:
flipping a 2D scatter's x/y/c back and forth holds every other argument still.
Dash then serves the leftover and kills the job it just started, which shows up
as a plot that does not update when the leftover is the ``no_update`` a
PreventUpdate stored.

``SafeDiskcacheManager`` drops the key before the job starts. These tests pin
that, including the ordering the fix rests on: the drop has to happen before the
job is handed over, not after.

Author: Zhengyu Peng
License: GPL-3.0
"""

import pytest

from dash import DiskcacheManager
from diskcache import FanoutCache

from settings import SafeDiskcacheManager

NO_UPDATE = {"_dash_no_update": "_dash_no_update"}


@pytest.fixture
def manager(tmp_path):
    """A manager over a cache of its own, so tests cannot see each other."""
    return SafeDiskcacheManager(FanoutCache(str(tmp_path / "dash")))


@pytest.fixture
def started(monkeypatch):
    """Record what the result store held when the job was handed to Dash."""
    record = {}

    def fake_call_job_fn(self, key, job_fn, args, context):
        record["result_at_start"] = self.handle.get(key, "<empty>")
        record["args"] = args
        return 4242

    monkeypatch.setattr(DiskcacheManager, "call_job_fn", fake_call_job_fn)
    return record


class TestLeftoverResult:
    def test_stale_no_update_is_dropped_before_the_job_starts(self, manager, started):
        # The crux: a PreventUpdate left by an earlier job at this key would be
        # handed to the browser instead of what this job is about to compute.
        manager.handle.set("key", NO_UPDATE)

        manager.call_job_fn("key", None, {}, {})

        assert started["result_at_start"] == "<empty>"

    def test_stale_figure_is_dropped_too(self, manager, started):
        manager.handle.set("key", {"figure": "from a previous job"})

        manager.call_job_fn("key", None, {}, {})

        assert started["result_at_start"] == "<empty>"

    def test_progress_and_set_props_are_dropped(self, manager, started):
        manager.handle.set(manager._make_progress_key("key"), [50, "half way"])
        manager.handle.set(manager._make_set_props_key("key"), {"id": {"a": 1}})

        manager.call_job_fn("key", None, {}, {})

        assert manager.get_progress("key") is None
        assert manager.get_updated_props("key") == {}

    def test_the_job_is_still_started(self, manager, started):
        assert manager.call_job_fn("key", None, {"x": 1}, {}) == 4242
        assert started["args"] == {"x": 1}
