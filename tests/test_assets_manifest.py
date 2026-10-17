"""The vendored ES modules must never be script-tagged.

Dash walks `assets/` and puts a `<script>` tag on everything ending in "js".
The three.js files under `assets/gl/` are ES modules: a classic script tag
throws on their first `import`, and the only sign of it is one console line on a
page that otherwise looks fine but has no 3D view. `settings.ASSETS_IGNORE`
keeps them out of the walk, and this is the test that keeps that true.

The other half of the arrangement is equally silent in failure: an ignored file
is still *served*, which is what lets `gl_bootstrap.js` dynamic-import it. If a
future Dash ever stops serving ignored assets, the route test below catches it.

Author: Zhengyu Peng
License: GPL-3.0
"""

import pathlib
import re

import pytest

from settings import ASSETS_IGNORE, app

ASSETS = pathlib.Path(__file__).resolve().parent.parent / "assets"
GL = ASSETS / "gl"

# The classic script that bootstraps the module graph. It is the one GL file
# that must be tagged, or nothing loads the rest.
BOOTSTRAP = "gl_bootstrap.js"


@pytest.fixture(scope="module")
def tagged():
    """Asset paths Dash will emit a <script> tag for."""
    app._walk_assets_directory()
    return {
        resource["asset_path"]
        for resource in app.scripts._resources._resources
        if "asset_path" in resource
    }


class TestTheModulesAreNotTagged:
    def test_no_esm_file_is_tagged(self, tagged):
        assert [path for path in tagged if path.endswith(".esm.js")] == []

    def test_nothing_under_gl_is_tagged(self, tagged):
        # Belt and braces: the rule is about the directory as much as the
        # suffix, so a file added there under another name is caught too.
        assert [
            path for path in tagged if path.replace("\\", "/").startswith("gl/")
        ] == []

    def test_the_bootstrap_is_tagged(self, tagged):
        # Without this the exclusion above would "pass" on a page with no GL at
        # all, which is the failure it is meant to prevent.
        assert BOOTSTRAP in tagged


class TestEveryVendoredFileMatchesTheRule:
    def test_the_directory_exists(self):
        assert GL.is_dir(), "assets/gl is missing -- see assets/gl/VENDOR.md"

    @pytest.mark.parametrize(
        "name",
        [
            "three.esm.js",
            "three.core.esm.js",
            "OrbitControls.esm.js",
            "CSS2DRenderer.esm.js",
        ],
    )
    def test_the_vendored_file_is_present(self, name):
        assert (GL / name).is_file()

    def test_every_js_file_there_is_ignored(self):
        pattern = re.compile(ASSETS_IGNORE)
        unmatched = [
            path.name for path in GL.glob("*.js") if not pattern.search(path.name)
        ]

        assert unmatched == [], (
            f"{unmatched} would be script-tagged as classic scripts. "
            f"Name GL modules '*.esm.js' so {ASSETS_IGNORE!r} covers them."
        )


class TestTheImportsResolveWithoutABundler:
    """A bare specifier needs a bundler or an import map; this project has
    neither, so every import in the vendored files has to be a relative path
    that exists on disk beside it."""

    @pytest.mark.parametrize(
        "name",
        ["three.esm.js", "OrbitControls.esm.js", "CSS2DRenderer.esm.js"],
    )
    def test_no_bare_three_specifier_survives(self, name):
        source = (GL / name).read_text(encoding="utf-8")

        # Only real import/export statements; the files carry `@three_import`
        # JSDoc lines quoting the bare form as documentation.
        bare = re.findall(
            r"^\s*(?:import|export)[^;]*?from\s+['\"]three['\"]", source, re.M
        )

        assert bare == []

    def test_relative_imports_point_at_files_that_exist(self):
        for path in GL.glob("*.esm.js"):
            source = path.read_text(encoding="utf-8")
            for target in re.findall(r"from\s+['\"](\./[^'\"]+)['\"]", source):
                assert (GL / target).is_file(), f"{path.name} imports missing {target}"


@pytest.fixture(scope="module")
def client():
    """A test client for the asset routes.

    Dash validates the layout on every request, so the bare app from
    `settings` -- which has one only once `server.dash_app` has run -- needs a
    placeholder. Nothing here renders it; these are static file routes.
    """
    from dash import html

    if app.layout is None:
        app.layout = html.Div()
    return app.server.test_client()


class TestTheModulesAreStillServed:
    """Ignoring an asset removes its script tag, not its route."""

    @pytest.mark.parametrize(
        "name", ["three.esm.js", "three.core.esm.js", "OrbitControls.esm.js"]
    )
    def test_it_is_reachable_with_a_javascript_mime_type(self, client, name):
        response = client.get(f"/assets/gl/{name}")

        assert response.status_code == 200
        # A browser refuses a module script served as text/plain, which is
        # exactly why these are not named `.mjs`.
        assert "javascript" in response.headers["Content-Type"].lower()
