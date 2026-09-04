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
    /* The dock's floor is its chrome (head, pane padding, control strip: about
       130px) plus --sv-pane-plot-min, so dragging this edge can never squeeze a
       pane's plot below the height at which it is still a plot. Getting the
       dock out of the way entirely is what the collapse toggle is for. */
    "dock-splitter": { axis: "y", panel: "analysis-dock", grow: -1, min: 310 },
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

    /* The size a panel expands back to was agreed with a window that may since
       have shrunk. Checked once the animation has landed rather than now, so
       the check reads settled sizes and the animation still plays. */
    window.setTimeout(function () {
      fitToViewport();
      refitPlots();
    }, 280);
  }

  /* ── Splitters ──────────────────────────────────────────────────────── */

  var dragState = null;

  /* Both properties, because these regions are flex items sized by basis but
     still read by anything that measures `width`/`height`. */
  function setPanelSize(panel, axis, size) {
    panel.style.flexBasis = size + "px";
    panel.style[axis === "y" ? "height" : "width"] = size + "px";
  }

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

    /* Kept as the size that was asked for, not just the size that was applied:
       a window too narrow to honour it now may be wide enough for it later. */
    dragState.panel.svSize = next;
    setPanelSize(dragState.panel, spec.axis, next);
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
    panel.svSize = null;
    panel.style.flexBasis = "";
    panel.style.width = "";
    panel.style.height = "";
    refitDuring(260);
  }

  /* ── Fitting the dragged sizes to the window ────────────────────────── */

  /* A drag writes pixels onto a panel, and pixels do not shrink with the
     window: narrow it far enough and the panels together outrun the stage,
     leaving the canvas with nothing and the shell overflowing. Every window
     change therefore replays the intended sizes and then takes back only what
     the canvas needs, so a panel gives way while there is no room for it and
     returns to its dragged size once the room comes back. */

  function measure(element, axis) {
    if (!element) return 0;
    var rect = element.getBoundingClientRect();
    return axis === "y" ? rect.height : rect.width;
  }

  /* A collapsed panel is already at its floor and the stylesheet owns its size,
     so there is nothing here to give. */
  function resizablePanels(axis) {
    var entries = [];
    Object.keys(SPLITTERS).forEach(function (id) {
      var spec = SPLITTERS[id];
      if (spec.axis !== axis) return;
      var panel = document.getElementById(spec.panel);
      if (!panel || panel.classList.contains("sv-collapsed")) return;
      entries.push({ spec: spec, panel: panel });
    });
    return entries;
  }

  /* The fit reads back the sizes it writes, so it has to run with the panel
     transitions off: an animating width measures as whatever frame it is on,
     and the stage would be sized against a number still on its way. */
  function fitToViewport() {
    document.body.classList.add("sv-fitting");
    try {
      fitRegions();
    } finally {
      /* Commit the last write while the transition is still suppressed. */
      void document.body.offsetWidth;
      document.body.classList.remove("sv-fitting");
    }
  }

  function fitRegions() {
    /* A window that grew has to hand back what the last shrink took off. */
    resizablePanels("x")
      .concat(resizablePanels("y"))
      .forEach(function (entry) {
        if (entry.panel.svSize != null) {
          setPanelSize(entry.panel, entry.spec.axis, entry.panel.svSize);
        }
      });

    resizablePanels("y").forEach(function (entry) {
      var max = Math.max(entry.spec.min, window.innerHeight - DOCK_MAX_MARGIN);
      var height = measure(entry.panel, "y");
      if (height <= max) return;
      if (entry.panel.svSize == null) entry.panel.svSize = height;
      setPanelSize(entry.panel, "y", max);
    });

    var upper = document.querySelector(".sv-upper");
    if (!upper) return;

    /* Measured from what the columns occupy rather than from the canvas
       itself: once the canvas has been squeezed to nothing its own width no
       longer says how much room is missing. */
    var occupied = 0;
    Object.keys(SPLITTERS).forEach(function (id) {
      if (SPLITTERS[id].axis !== "x") return;
      occupied +=
        measure(document.getElementById(SPLITTERS[id].panel), "x") +
        measure(document.getElementById(id), "x");
    });

    var deficit = CANVAS_MIN - (measure(upper, "x") - occupied);
    if (deficit <= 0) return;

    var columns = resizablePanels("x");
    columns.forEach(function (entry) {
      entry.size = measure(entry.panel, "x");
      entry.slack = Math.max(0, entry.size - entry.spec.min);
    });

    /* Emptied one column at a time, widest slack first: the panel that was
       dragged out has the most to give, and a panel still at its designed
       width should not be shaved to spare it. */
    columns.sort(function (a, b) {
      return b.slack - a.slack;
    });

    var remaining = deficit;
    columns.forEach(function (entry) {
      if (remaining <= 0 || entry.slack <= 0) return;
      var give = Math.min(entry.slack, remaining);
      remaining -= give;
      if (entry.panel.svSize == null) entry.panel.svSize = entry.size;
      setPanelSize(entry.panel, "x", entry.size - give);
    });
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
        /* Collapsed, the strip shows the panel's own icon -- the same way the
           filter rail falls back to its funnel. */
        togglePanel(
          "subview-panel",
          "inspector-toggle",
          "bi-layout-sidebar-inset-reverse",
          "bi-eye"
        );
        /* A minimized section is not on screen, so its own toggle only ever
           shows the one state and the way back is the chip in the panel bar.
           Both buttons drive the same section. */
      } else if (
        event.target.closest("#camera-section-toggle") ||
        event.target.closest("#camera-restore")
      ) {
        togglePanel(
          "subview-camera-section",
          "camera-section-toggle",
          "bi-dash-lg",
          "bi-dash-lg"
        );
      } else if (
        event.target.closest("#threshold-section-toggle") ||
        event.target.closest("#threshold-restore")
      ) {
        togglePanel(
          "subview-threshold-section",
          "threshold-section-toggle",
          "bi-dash-lg",
          "bi-dash-lg"
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

    /* refitPlots dispatches this same event, so only a genuine change of the
       window is acted on -- otherwise every refit would re-enter and refit
       again for as long as the browser kept up. */
    var viewport = { w: window.innerWidth, h: window.innerHeight };
    /* A window can be too small for the designed sizes from the outset, not
       only after a drag. */
    fitToViewport();
    window.addEventListener("resize", function () {
      if (window.innerWidth === viewport.w && window.innerHeight === viewport.h) {
        return;
      }
      viewport.w = window.innerWidth;
      viewport.h = window.innerHeight;
      fitToViewport();
      refitPlots();
    });

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
