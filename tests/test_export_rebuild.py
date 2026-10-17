"""The 3D exports rebuild their figure rather than reading it back.

Both exports used to take ``State("scatter3d", "figure")`` -- the live Plotly
figure sitting in the browser. That works only while Plotly is the thing
drawing the canvas, so the moment a second renderer exists an export would
either ship a stale figure or an empty one. They now rebuild from the dataset
through ``_build_current_figure``, which is also what the server-side fallback
uses, so all three agree by construction.

Author: Zhengyu Peng
License: GPL-3.0
"""

import dash
import pytest

from view_callbacks.scatter_3d_view import get_scatter_3d_view_callbacks

EXPORT_OUTPUTS = ("export-scatter3d-png", "export-scatter3d-html")


@pytest.fixture(scope="module")
def callbacks():
    """Every 3D-view callback, keyed by the id it is triggered from."""
    app = dash.Dash(__name__)
    get_scatter_3d_view_callbacks(app)

    by_trigger = {}
    for callback in app.callback_map.values():
        for dep in callback["inputs"]:
            by_trigger.setdefault(dep["id"], []).append(callback)
    return by_trigger


def _state_ids(callback):
    return {(dep["id"], dep["property"]) for dep in callback["state"]}


class TestTheExportsDoNotReadTheLiveFigure:
    @pytest.mark.parametrize("trigger", EXPORT_OUTPUTS)
    def test_the_figure_is_not_a_state(self, callbacks, trigger):
        assert trigger in callbacks, f"{trigger} triggers no callback"

        for callback in callbacks[trigger]:
            assert ("scatter3d", "figure") not in _state_ids(callback)

    @pytest.mark.parametrize("trigger", EXPORT_OUTPUTS)
    def test_it_takes_what_a_rebuild_needs(self, callbacks, trigger):
        # The arguments `_build_current_figure` cannot do without: without the
        # session there is no config to read, and without the frame and the
        # filters the rebuild is not of what is on screen.
        required = {
            ("session-id", "data"),
            ("slider-frame", "value"),
            ("overlay-switch", "value"),
            ("c-picker-3d", "value"),
            ("colormap-3d", "value"),
            ("visible-picker", "value"),
            ("darkmode-switch", "value"),
        }

        for callback in callbacks[trigger]:
            assert required <= _state_ids(callback)


class TestTheFallbackAndTheExportsShareTheRebuild:
    def test_the_server_side_update_still_reads_the_dataset(self, callbacks):
        # `trigger-remote-figure` is the bounce `retrieveBuffer` performs when a
        # frame is not buffered yet. It must still reach a callback, or an
        # unbuffered frame renders nothing at all.
        assert "trigger-remote-figure" in callbacks

    def test_the_helper_is_importable_on_its_own(self):
        # Module level, not a closure over `app` -- which is what lets the
        # exports call it without going through a callback.
        from view_callbacks.scatter_3d_view import _build_current_figure

        assert callable(_build_current_figure)
