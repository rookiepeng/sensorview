// Entry point for the WebGL renderer.
//
// This is the only file of the GL stack Dash script-tags. Everything else is an
// ES module under `assets/gl/`, excluded from the asset walk by
// `settings.ASSETS_IGNORE` -- excluded from being *tagged*, that is, not from
// being served -- and pulled in here by dynamic `import()`. A classic script
// tag would throw on the first `import` inside those files, so the exclusion is
// what makes the whole arrangement work; see `assets/gl/VENDOR.md`.
//
// Nothing is imported until WebGL2 is known to be there. A machine without it
// keeps Plotly as the only renderer rather than downloading two megabytes of
// three.js to find out it cannot use them.

(function () {
  "use strict";

  // Dash serves assets under `requests_pathname_prefix`, which is "/" here but
  // need not be. Deriving the directory from this file's own URL means the
  // import path is right whatever the prefix is.
  var HERE = (function () {
    var self = document.currentScript;
    if (self && self.src) {
      return self.src.replace(/[^/]*$/, "");
    }
    return "/assets/";
  })();

  // A context alone does not mean usable: Chromium falls back to a software
  // rasteriser when the GPU is blocklisted or the driver is stale, and software
  // WebGL on a hundred thousand points is slower than the Plotly path this is
  // meant to replace. The renderer string is the only way to tell, and it is
  // worth surfacing rather than leaving the user to wonder why it is slow.
  function probe() {
    var canvas = document.createElement("canvas");
    var gl;
    try {
      gl = canvas.getContext("webgl2");
    } catch (error) {
      return { ok: false, reason: String(error) };
    }
    if (!gl) {
      return { ok: false, reason: "no webgl2 context" };
    }

    var renderer = "";
    try {
      var ext = gl.getExtension("WEBGL_debug_renderer_info");
      if (ext) {
        renderer = String(gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) || "");
      }
    } catch (error) {
      // Some builds hide the extension entirely. Not knowing is fine.
    }

    var software = /swiftshader|llvmpipe|software|basic render/i.test(renderer);

    try {
      var lose = gl.getExtension("WEBGL_lose_context");
      if (lose) {
        lose.loseContext();
      }
    } catch (error) {
      // Probe cleanup is best effort.
    }

    return { ok: true, renderer: renderer, software: software };
  }

  function disable(reason) {
    window.svGLAvailable = false;
    window.svGLReason = reason;
    document.documentElement.classList.add("sv-no-webgl");
  }

  var result = probe();
  window.svGLRenderer = result.renderer || "";
  window.svGLSoftware = result.software === true;

  if (!result.ok) {
    disable(result.reason);
    console.info("SensorView: WebGL renderer unavailable (" + result.reason + "), using Plotly.");
    return;
  }

  if (result.software) {
    console.warn(
      "SensorView: WebGL is running on a software rasteriser (" +
        result.renderer +
        "). The GL renderer will work but may be slower than Plotly."
    );
  }

  window.svGLAvailable = true;

  // Resolves to the scene handle. Clientside callbacks await this rather than
  // `window.svGL`, because Dash can fire a callback before the import settles.
  window.svGLReady = import(HERE + "gl/sv_scene.esm.js")
    .then(function (module) {
      window.svGL = module.create();
      document.documentElement.classList.add("sv-gl-loaded");
      return window.svGL;
    })
    .catch(function (error) {
      disable("module import failed");
      console.error("SensorView: GL renderer failed to load.", error);
      return null;
    });
})();
