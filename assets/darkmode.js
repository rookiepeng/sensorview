/*
 * Set the theme before first paint.
 *
 * Runs ahead of React so the shell never flashes the wrong background while
 * Dash mounts. Once mounted, workbench.js takes over from the theme switch.
 *
 * Author: Zhengyu Peng
 * License: GPL-3.0
 */

(function () {
  "use strict";

  var stored = null;
  try {
    stored = window.localStorage.getItem("sensorview-theme");
  } catch (error) {
    /* Storage blocked; fall through to the dark default. */
  }

  document.documentElement.setAttribute(
    "data-bs-theme",
    stored === "light" ? "light" : "dark"
  );
})();
