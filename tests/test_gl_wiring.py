"""The WebGL renderer is wired into the app.

Most of this renderer lives in JavaScript, which nothing here runs. What can be
checked from Python is the seam: the components the browser code reaches for by
id, the callbacks that must accept a click from either renderer, and the server
routes the packed buffer is fetched from. Each of these fails silently in the
browser -- a store that is not in the layout makes `set_props` a no-op, and a
missing route makes the scene stay empty -- so they are asserted here instead.

Author: Zhengyu Peng
License: GPL-3.0
"""

import dash
import pytest

from layouts.app_layout import get_app_layout
from layouts.canvas_layout import get_canvas_layout
from view_callbacks.scatter_3d_view import get_scatter_3d_view_callbacks


def component_ids(component):
    """Every id in a component tree."""
    found = set()

    def walk(node):
        if isinstance(node, (list, tuple)):
            for item in node:
                walk(item)
            return
        if not hasattr(node, "children") and not hasattr(node, "id"):
            return
        node_id = getattr(node, "id", None)
        if isinstance(node_id, str):
            found.add(node_id)
        walk(getattr(node, "children", None))

    walk(component)
    return found


@pytest.fixture(scope="module")
def layout_ids():
    return component_ids(get_app_layout())


@pytest.fixture(scope="module")
def callbacks():
    app = dash.Dash(__name__)
    get_scatter_3d_view_callbacks(app)
    return app.callback_map


class TestTheSceneIsInTheLayout:
    @pytest.mark.parametrize("component_id", ["gl-stage", "gl-canvas", "gl-labels"])
    def test_the_canvas_and_its_label_layer_exist(self, layout_ids, component_id):
        # `sv_scene.esm.js` mounts by looking these up by id; without them it
        # waits on a MutationObserver that never fires.
        assert component_id in layout_ids

    def test_the_toggle_is_with_the_other_view_settings(self):
        assert "renderer-toggle" in component_ids(get_canvas_layout())


class TestTheStores:
    @pytest.mark.parametrize(
        "store_id",
        [
            "renderer-mode",
            "gl-palette",
            "gl-click",
            "gl-redraw",
            "gl-frame-ack",
        ],
    )
    def test_the_store_exists(self, layout_ids, store_id):
        assert store_id in layout_ids

    def test_the_renderer_choice_persists(self):
        # Local storage, so the choice survives a reload the way the theme
        # does. A session-scoped store would silently reset it every launch.
        store = _find_store(get_app_layout(), "renderer-mode")

        assert store.storage_type == "local"

    def test_the_palette_carries_every_colormap_option(self):
        from layouts.layout_constants import colorscales

        store = _find_store(get_app_layout(), "gl-palette")

        assert set(store.data["colorscales"]) == set(colorscales)

    def test_the_palette_carries_the_categorical_colorway(self):
        # The GL renderer colours categorical groups from this rather than from
        # a copy of Plotly's palette written out in JavaScript.
        store = _find_store(get_app_layout(), "gl-palette")

        assert len(store.data["colorway"]) > 0
        assert all(str(c).startswith("#") for c in store.data["colorway"])


class TestTheClickPath:
    def test_the_hide_callback_takes_both_renderers_clicks(self, callbacks):
        inputs = {
            (dep["id"], dep["property"])
            for callback in callbacks.values()
            for dep in callback["inputs"]
        }

        assert ("scatter3d", "clickData") in inputs
        assert ("gl-click", "data") in inputs

    def test_both_clicks_reach_the_same_callback(self, callbacks):
        # One callback, branching on which fired -- not two writing the same
        # visibility table from different directions.
        owners = [
            key
            for key, callback in callbacks.items()
            if any(dep["id"] == "gl-click" for dep in callback["inputs"])
        ]

        assert len(owners) == 1
        plotly_click = [
            dep
            for dep in callbacks[owners[0]]["inputs"]
            if dep["id"] == "scatter3d" and dep["property"] == "clickData"
        ]
        assert plotly_click


class TestThePlotlyOnlyCallbacksStandDown:
    @pytest.mark.parametrize(
        "trigger", ["colormap-3d", "darkmode-switch", "size-vary-switch"]
    )
    def test_the_patch_callback_knows_which_renderer_is_live(self, callbacks, trigger):
        # Each of these patches the Plotly figure in place. In GL mode there is
        # no figure on screen to patch, so they have to be able to tell.
        owners = [
            callback
            for callback in callbacks.values()
            if any(dep["id"] == trigger for dep in callback["inputs"])
            and any(dep["id"] == "scatter3d" for dep in callback["state"])
        ]

        assert owners, f"no figure-patching callback is triggered by {trigger}"
        for callback in owners:
            assert any(dep["id"] == "renderer-mode" for dep in callback["state"])


class TestTheBinaryRoutes:
    @pytest.fixture(scope="class")
    def client(self):
        # A fresh app, not the shared one from `settings`. Flask refuses to
        # register a route once an application has served its first request,
        # and another test module in this suite makes one -- so registering on
        # the shared app passes alone and fails in a full run, depending only
        # on collection order.
        from dash import html

        from server.routes import register_api_routes

        isolated = dash.Dash(__name__)
        isolated.layout = html.Div()
        register_api_routes(isolated)
        return isolated.server.test_client()

    def test_an_unknown_session_gets_the_reset_sentinel(self, client):
        # Not a 500, and not an empty batch: "nothing buffered here" and
        # "nothing new since your index" have to stay distinguishable.
        response = client.get("/api/data3d/no-such-session/0")

        assert response.status_code == 200
        assert response.data[:4] == b"SVB1"
        assert int.from_bytes(response.data[4:8], "little") == 0xFFFFFFFF

    def test_it_serves_bytes_not_json(self, client):
        response = client.get("/api/data3d/no-such-session/0")

        assert response.headers["Content-Type"].startswith("application/octet-stream")

    def test_a_session_without_a_cloud_gets_an_empty_cloud(self, client):
        response = client.get("/api/cloud3d/no-such-session/0")

        assert response.status_code == 200
        assert response.data[:4] == b"SVC1"

    def test_the_json_route_still_exists(self, client):
        # The Plotly fallback reads it, and the toggle depends on it working.
        response = client.get("/api/data/no-such-session/0")

        assert response.status_code == 200
        assert response.headers["Content-Type"].startswith("application/json")


def _find_store(component, store_id):
    """The dcc.Store with the given id."""
    found = []

    def walk(node):
        if node is None or isinstance(node, (str, int, float, bool)):
            return
        if isinstance(node, (list, tuple)):
            for item in node:
                walk(item)
            return
        if getattr(node, "id", None) == store_id:
            found.append(node)
        walk(getattr(node, "children", None))

    walk(component)
    assert found, f"{store_id} is not in the layout"
    return found[0]
