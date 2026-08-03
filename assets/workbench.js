/*
 * Workbench chrome: panel collapse, dock resize, and Plotly re-fitting.
 *
 * All of it is clientside. Collapsing a panel or dragging the dock splitter
 * fires continuously and changes nothing the server knows about, so a Dash
 * round trip per event would only add latency to a purely visual change.
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

  var DOCK_MIN = 140;
  var DOCK_MAX_MARGIN = 220; /* pixels of stage that must survive a drag */
  var THEME_KEY = "sensorview-theme";

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

  /* ── Dock splitter ──────────────────────────────────────────────────── */

  var dragState = null;

  function onSplitterDown(event) {
    var dock = document.getElementById("analysis-dock");
    if (!dock || dock.classList.contains("sv-collapsed")) return;

    dragState = {
      dock: dock,
      startY: event.clientY,
      startHeight: dock.getBoundingClientRect().height,
    };
    document.body.classList.add("sv-resizing");
    event.preventDefault();
  }

  function onPointerMove(event) {
    if (!dragState) return;

    /* Dragging up grows the dock, so the delta is inverted. Clamped so the
       dock can never swallow the 3D stage or shrink past its own tab bar. */
    var max = window.innerHeight - DOCK_MAX_MARGIN;
    var next = dragState.startHeight + (dragState.startY - event.clientY);
    next = Math.min(Math.max(next, DOCK_MIN), Math.max(DOCK_MIN, max));

    dragState.dock.style.flexBasis = next + "px";
    dragState.dock.style.height = next + "px";
    refitPlots();
  }

  function onPointerUp() {
    if (!dragState) return;
    dragState = null;
    document.body.classList.remove("sv-resizing");
    refitPlots();
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
      if (event.target.closest("#dock-splitter")) {
        onSplitterDown(event);
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
