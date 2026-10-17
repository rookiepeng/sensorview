# Vendored three.js

`assets/gl/*.esm.js` is three.js, copied in rather than installed: this project
has no bundler and no npm, and is not getting one for three files. Dash serves
everything under `assets/`, so a copy here is reachable at `/assets/gl/<name>`.

The `.esm.js` suffix is load-bearing, twice over:

- `settings.py` passes `assets_ignore=r"\.esm\.js$"`, which keeps Dash from
  script-tagging these as classic scripts (they are ES modules, and a classic
  `<script>` throws on the first `import`). An ignored asset is still *served*,
  which is the whole trick -- `gl_bootstrap.js` reaches them by dynamic import.
- `.mjs` would seem the obvious name and is a trap. Dash's asset walk tests
  `f.endswith("js")`, so `.mjs` is picked up anyway, and Dash emits it as
  `<script type="module">` -- but `mimetypes.guess_type("a.mjs")` returns
  `text/plain` on a stock Windows box, and browsers hard-block module scripts
  served with a non-JS MIME type. `.esm.js` resolves to
  `application/javascript` and sidesteps both halves.

## Source

three.js **r180** (npm `three@0.180.0`), from `https://unpkg.com/three@0.180.0/`.

`build/three.module.js` is not self-contained: it imports the bulk of the
library from `build/three.core.js` and re-exports it. Both are needed.

| upstream path | vendored as | bytes | sha256 (upstream, pre-patch) |
|---|---|---:|---|
| `build/three.core.js` | `three.core.esm.js` | 1403421 | `eb077d2417f61d3e6d9264c317cabc4ea35769ed6b0ab533067292a550784c20` |
| `build/three.module.js` | `three.esm.js` | 603113 | `c8211c69345d2e9949dc7a8ac969380497aa0600a5a8ac6a459c8cd02dd9cb8a` |
| `examples/jsm/controls/OrbitControls.js` | `OrbitControls.esm.js` | 38703 | `b97879c748170baadeb3fb84cea1ffdf4674e283dc06042f34e2acb95a76042c` |
| `examples/jsm/renderers/CSS2DRenderer.js` | `CSS2DRenderer.esm.js` | 6976 | `dd667941bc67380ecb46c79fa682494e19a7b0a953806f7df24e78cfdfc6270e` |

## Patches

One line per file, so an upgrade is a re-copy plus the same four edits.

```
three.core.esm.js:
    (verbatim)
three.esm.js:
    2x from './three.core.js' -> from './three.core.esm.js'
OrbitControls.esm.js:
    1x } from 'three'; -> } from './three.esm.js';
CSS2DRenderer.esm.js:
    1x } from 'three'; -> } from './three.esm.js';
```

`three.module.js` and the two addons name their dependency by a bare specifier
(`'three'`, `'./three.core.js'`), which only a bundler or an import map can
resolve. Rewriting them to relative paths keeps the browser able to load the
files directly, and avoids overriding `app.index_string` in `server/dash_app.py`
just to inject an import map.

## Upgrading

1. Download the four upstream files at the new tag.
2. Re-apply the patch table above.
3. Update the version, sizes and hashes here.
4. Run `pytest tests/test_assets_manifest.py` -- it asserts none of these ever
   gets script-tagged, which is the failure mode that is silent at page load.

The unminified build is deliberate: this is served from localhost, so the size
costs nothing, and there is no source-map tooling here to make a minified stack
trace readable.
