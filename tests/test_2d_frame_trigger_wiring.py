"""Each 2D scatter regenerates per frame off its own Frame/All switch.

The two panes are near-copies of each other, which is how the right pane came to
gate its per-frame regeneration on ``scatter2dl-allframe-switch`` -- the left
pane's switch. The panes are independent: with A on All and B on Frame, moving
the slider left B untouched, because the trigger it needs was gated on a switch
belonging to the other pane. These tests read the wiring Dash actually
registered, so a copy-paste between the two modules cannot reintroduce it.

Author: Zhengyu Peng
License: GPL-3.0
"""

import dash
import pytest

from view_callbacks.scatter_2d_left_view import get_scatter_2d_left_view_callbacks
from view_callbacks.scatter_2d_right_view import get_scatter_2d_right_view_callbacks

PANES = {
    "left": (get_scatter_2d_left_view_callbacks, "l"),
    "right": (get_scatter_2d_right_view_callbacks, "r"),
}


def dependency_ids(app, callback_id, kind):
    """The component ids a registered callback reads or writes."""
    return [dep["id"] for dep in app.callback_map[callback_id][kind]]


@pytest.fixture(params=sorted(PANES))
def pane(request):
    """One pane's registered callbacks, on an app of its own."""
    register, _ = PANES[request.param]
    app = dash.Dash(__name__)
    register(app)
    return request.param, app


class TestFrameTrigger:
    def test_reads_its_own_scope_switch(self, pane):
        side, app = pane
        _, letter = PANES[side]

        inputs = dependency_ids(app, f"..{side}-regenerate-trigger.data..", "inputs")

        # The crux: the pane's own switch, not the other pane's.
        assert f"scatter2d{letter}-allframe-switch" in inputs

    def test_reads_no_dependency_of_the_other_pane(self, pane):
        side, app = pane
        other = "right" if side == "left" else "left"
        other_letter = PANES[other][1]

        callback_id = f"..{side}-regenerate-trigger.data.."
        referenced = dependency_ids(app, callback_id, "inputs") + dependency_ids(
            app, callback_id, "state"
        )

        assert f"scatter2d{other_letter}-allframe-switch" not in referenced
        assert f"{other}-switch" not in referenced
        assert f"{other}-regenerate-trigger" not in referenced
