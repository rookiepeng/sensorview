/*
 * Floating subview panel: drag and minimize.
 *
 * Kept out of Dash callbacks entirely -- dragging fires continuously and a
 * server round trip per pointer move would be unusable. The panel is positioned
 * by direct style writes; Dash only ever sets its visibility.
 *
 * Author: Zhengyu Peng
 * License: GPL-3.0
 */

(function () {
  "use strict";

  const PANEL_ID = "subview-panel";
  const HEADER_ID = "subview-header";
  const MINIMIZE_ID = "subview-minimize";
  const MARGIN = 8;

  let dragState = null;

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  /* Keep the panel reachable: never let a drag (or a window resize) strand it
     outside the viewport where its header can't be grabbed again. */
  function clampToViewport(panel) {
    const rect = panel.getBoundingClientRect();
    const maxLeft = Math.max(MARGIN, window.innerWidth - rect.width - MARGIN);
    const maxTop = Math.max(MARGIN, window.innerHeight - rect.height - MARGIN);
    panel.style.left = clamp(rect.left, MARGIN, maxLeft) + "px";
    panel.style.top = clamp(rect.top, MARGIN, maxTop) + "px";
    panel.style.right = "auto";
    panel.style.bottom = "auto";
  }

  function onPointerDown(event) {
    const panel = document.getElementById(PANEL_ID);
    const header = document.getElementById(HEADER_ID);
    if (!panel || !header) return;

    // Let the window buttons work without starting a drag.
    if (event.target.closest("button")) return;

    const rect = panel.getBoundingClientRect();
    dragState = {
      panel: panel,
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
      width: rect.width,
      height: rect.height,
    };

    // Pin to pixel coordinates before the first move so a panel still sitting
    // at its default right-anchored position doesn't jump on grab.
    panel.style.left = rect.left + "px";
    panel.style.top = rect.top + "px";
    panel.style.right = "auto";
    panel.style.bottom = "auto";
    panel.classList.add("subview-dragging");

    header.setPointerCapture?.(event.pointerId);
    event.preventDefault();
  }

  function onPointerMove(event) {
    if (!dragState) return;

    const maxLeft = Math.max(MARGIN, window.innerWidth - dragState.width - MARGIN);
    const maxTop = Math.max(MARGIN, window.innerHeight - dragState.height - MARGIN);

    dragState.panel.style.left =
      clamp(event.clientX - dragState.offsetX, MARGIN, maxLeft) + "px";
    dragState.panel.style.top =
      clamp(event.clientY - dragState.offsetY, MARGIN, maxTop) + "px";
  }

  function onPointerUp(event) {
    if (!dragState) return;
    dragState.panel.classList.remove("subview-dragging");
    document.getElementById(HEADER_ID)?.releasePointerCapture?.(event.pointerId);
    dragState = null;
  }

  function toggleMinimize() {
    const panel = document.getElementById(PANEL_ID);
    if (!panel) return;

    const minimized = panel.classList.toggle("subview-minimized");
    const icon = document.querySelector("#" + MINIMIZE_ID + " i");
    if (icon) {
      icon.className = minimized ? "bi bi-plus-lg" : "bi bi-dash-lg";
    }
    // Height changed, so the panel may now hang off the bottom edge.
    clampToViewport(panel);
  }

  /* The panel is re-created whenever Dash re-renders the layout, so bind by
     delegation on document rather than to the elements themselves. */
  function bind() {
    document.addEventListener("pointerdown", function (event) {
      if (event.target.closest("#" + HEADER_ID)) {
        onPointerDown(event);
      }
    });
    document.addEventListener("pointermove", onPointerMove);
    document.addEventListener("pointerup", onPointerUp);
    document.addEventListener("pointercancel", onPointerUp);

    document.addEventListener("click", function (event) {
      if (event.target.closest("#" + MINIMIZE_ID)) {
        toggleMinimize();
      }
    });

    window.addEventListener("resize", function () {
      const panel = document.getElementById(PANEL_ID);
      if (panel && panel.style.left) {
        clampToViewport(panel);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }
})();
