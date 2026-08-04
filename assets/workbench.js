/*
 * Workbench chrome: panel collapse, region resize, and Plotly re-fitting.
 *
 * All of it is clientside. Collapsing a panel or dragging a splitter fires
 * continuously and changes nothing the server knows about, so a Dash round
 * trip per event would only add latency to a purely visual change.
 *
 * Plotly sizes itself once and then only listens to `window.resize`, so every
 * layout change here ends with a synthetic resize -- otherwise a graph keeps
 * the width of whatever panel arrangement existed when it first drew.
 *
 * Author: Zhengyu Peng
 * License: GPL-3.0
 */

(function () {
  "use strict";

  var DOCK_MAX_MARGIN = 220; /* pixels of stage that must survive a drag */
  var CANVAS_MIN = 320; /* likewise, but horizontally */
  var THEME_KEY = "sensorview-theme";

  /* Every draggable edge, keyed by the handle's id. `grow` is the sign the
     pointer delta carries: the dock and the inspector are anchored to the far
     edge, so moving toward the origin makes them bigger. */
  var SPLITTERS = {
    "dock-splitter": { axis: "y", panel: "analysis-dock", grow: -1, min: 140 },
    "rail-splitter": {
      axis: "x",
      panel: "filter-sidebar-col",
      grow: 1,
      min: 200,
    },
    "inspector-splitter": {
      axis: "x",
      panel: "subview-panel",
      grow: -1,
      min: 200,
    },
  };

  /* ── Plotly re-fit ──────────────────────────────────────────────────── */

  var refitPending = false;

  /* Coalesce: a single collapse can trigger several notifications, and each
     resize walks every graph on the page. */
  function refitPlots() {
    if (refitPending) return;
    refitPending = true;
    window.requestAnimationFrame(function () {
      refitPending = false;
      window.dispatchEvent(new Event("resize"));
    });
  }

  /* Panel widths animate, so the size at transitionend is the one that counts.
     Refit on the way as well, or the graph visibly lags the panel. */
  function refitDuring(durationMs) {
    var start = Date.now();
    (function tick() {
      refitPlots();
      if (Date.now() - start < durationMs) {
        window.requestAnimationFrame(tick);
      }
    })();
  }

  /* ── Collapsible panels ─────────────────────────────────────────────── */

  function togglePanel(panelId, buttonId, iconOpen, iconClosed) {
    var panel = document.getElementById(panelId);
    if (!panel) return;

    var collapsed = panel.classList.toggle("sv-collapsed");
    var icon = document.querySelector("#" + buttonId + " i");
    if (icon) {
      icon.className = "bi " + (collapsed ? iconClosed : iconOpen);
    }
    refitDuring(260);
  }

  /* ── Splitters ──────────────────────────────────────────────────────── */

  var dragState = null;

  /* The ceiling is whatever the 3D view can give up and still be usable, which
     is only knowable at grab time: the canvas is the flexible region, so its
     current slack is exactly how much further this edge can travel. */
  function maxSize(spec, startSize) {
    if (spec.axis === "y") {
      return window.innerHeight - DOCK_MAX_MARGIN;
    }
    var canvas = document.querySelector(".sv-canvas");
    if (!canvas) return startSize;
    return startSize + (canvas.getBoundingClientRect().width - CANVAS_MIN);
  }

  function onSplitterDown(event, spec) {
    var panel = document.getElementById(spec.panel);
    if (!panel || panel.classList.contains("sv-collapsed")) return;

    var rect = panel.getBoundingClientRect();
    var startSize = spec.axis === "y" ? rect.height : rect.width;

    dragState = {
      spec: spec,
      panel: panel,
      start: spec.axis === "y" ? event.clientY : event.clientX,
      startSize: startSize,
      max: Math.max(spec.min, maxSize(spec, startSize)),
    };
    document.body.classList.add(
      "sv-resizing",
      spec.axis === "y" ? "sv-resizing-row" : "sv-resizing-col"
    );
    event.preventDefault();
  }

  function onPointerMove(event) {
    if (!dragState) return;

    var spec = dragState.spec;
    var pos = spec.axis === "y" ? event.clientY : event.clientX;
    var next = dragState.startSize + (pos - dragState.start) * spec.grow;
    next = Math.min(Math.max(next, spec.min), dragState.max);

    /* Both properties, because these regions are flex items sized by basis but
       still read by anything that measures `width`/`height`. */
    dragState.panel.style.flexBasis = next + "px";
    dragState.panel.style[spec.axis === "y" ? "height" : "width"] = next + "px";
    refitPlots();
  }

  function onPointerUp() {
    if (!dragState) return;
    dragState = null;
    document.body.classList.remove(
      "sv-resizing",
      "sv-resizing-row",
      "sv-resizing-col"
    );
    refitPlots();
  }

  /* Double-click restores the stylesheet's size: dropping the inline override
     is the only way back to a width that tracks the design tokens. */
  function onSplitterDouble(spec) {
    var panel = document.getElementById(spec.panel);
    if (!panel) return;
    panel.style.flexBasis = "";
    panel.style.width = "";
    panel.style.height = "";
    refitDuring(260);
  }

  /* ── Theme ──────────────────────────────────────────────────────────── */

  /* The Dash switch owns the Plotly template; this owns the app chrome. Both
     read the same control so the two can never disagree. */
  function applyTheme(dark) {
    document.documentElement.setAttribute(
      "data-bs-theme",
      dark ? "dark" : "light"
    );
    try {
      window.localStorage.setItem(THEME_KEY, dark ? "dark" : "light");
    } catch (error) {
      /* Private browsing: the theme just will not persist. */
    }
    refitPlots();
  }

  function watchThemeSwitch() {
    var input = document.querySelector("#darkmode-switch input");
    if (!input) return false;

    applyTheme(input.checked);
    input.addEventListener("change", function () {
      applyTheme(input.checked);
    });
    return true;
  }

  /* ── Wiring ─────────────────────────────────────────────────────────── */

  function bind() {
    document.addEventListener("click", function (event) {
      if (event.target.closest("#toggle-sidebar-button")) {
        togglePanel(
          "filter-sidebar-col",
          "toggle-sidebar-button",
          "bi-layout-sidebar-inset",
          "bi-funnel"
        );
      } else if (event.target.closest("#inspector-toggle")) {
        togglePanel(
          "subview-panel",
          "inspector-toggle",
          "bi-layout-sidebar-inset-reverse",
          "bi-camera-video"
        );
      } else if (event.target.closest("#dock-toggle")) {
        togglePanel(
          "analysis-dock",
          "dock-toggle",
          "bi-chevron-bar-down",
          "bi-chevron-bar-up"
        );
      } else if (event.target.closest("#dock-swap")) {
        refitDuring(200);
      }
    });

    /* A pane that was display:none drew at zero width, so every slot change
       needs the plots re-measured once they are visible again. */
    document.addEventListener("change", function (event) {
      if (event.target.closest(".sv-slot-picker")) {
        refitDuring(400);
      }
    });

    document.addEventListener("pointerdown", function (event) {
      var handle = event.target.closest(".sv-splitter");
      if (handle && SPLITTERS[handle.id]) {
        onSplitterDown(event, SPLITTERS[handle.id]);
      }
    });
    document.addEventListener("dblclick", function (event) {
      var handle = event.target.closest(".sv-splitter");
      if (handle && SPLITTERS[handle.id]) {
        onSplitterDouble(SPLITTERS[handle.id]);
      }
    });
    document.addEventListener("pointermove", onPointerMove);
    document.addEventListener("pointerup", onPointerUp);
    document.addEventListener("pointercancel", onPointerUp);

    /* Dash replaces the switch when the layout re-renders, so keep looking
       until it exists rather than binding once at load. */
    if (!watchThemeSwitch()) {
      var observer = new MutationObserver(function () {
        if (watchThemeSwitch()) observer.disconnect();
      });
      observer.observe(document.body, { childList: true, subtree: true });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }
})();
