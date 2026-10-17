// The HUD: the chrome that reads the scene rather than controlling the app.
//
// Everything here is built from the frame the renderer already has, so none of
// it costs a Dash callback. The colorbar and legend are DOM rather than drawn
// into the scene: they are flat, they need to stay legible at any camera angle,
// and as DOM they re-theme with the rest of the chrome instead of needing a
// texture regenerated.

import { gradientStops, categoryCss } from "./sv_color.esm.js";

const PRESETS = [
  { id: "iso", label: "Iso", icon: "bi-box", title: "Isometric view" },
  { id: "top", label: "Top", icon: "bi-arrow-down-square", title: "Top-down view" },
  { id: "front", label: "Front", icon: "bi-arrow-right-square", title: "Front view" },
  { id: "side", label: "Side", icon: "bi-arrow-left-square", title: "Side view" },
];

function div(className, parent) {
  const element = document.createElement("div");
  element.className = className;
  if (parent) {
    parent.appendChild(element);
  }
  return element;
}

/**
 * The HUD overlay.
 */
export class Hud {
  /**
   * @param {HTMLElement} container The element the HUD is drawn into.
   * @param {Object} handlers `onPreset(id)`, `onToggleGroup(key)`.
   */
  constructor(container, handlers) {
    this.handlers = handlers || {};
    this.hidden = new Set();
    this.root = container;

    this.colorbar = div("sv-hud sv-gl-colorbar", container);
    this.colorbar.id = "gl-colorbar";
    this.colorbarLabel = div("sv-gl-colorbar-label", this.colorbar);
    const strip = div("sv-gl-colorbar-strip", this.colorbar);
    this.gradient = div("sv-gl-colorbar-gradient", strip);
    this.ticks = div("sv-gl-colorbar-ticks", strip);

    this.legend = div("sv-hud sv-gl-legend", container);
    this.legend.id = "gl-legend";

    this.readout = div("sv-hud sv-gl-readout", container);
    this.readout.id = "gl-readout";

    this.presets = div("sv-hud sv-gl-presets", container);
    this.presets.id = "gl-camera-presets";
    PRESETS.forEach((preset) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "sv-gl-preset";
      button.title = preset.title;
      button.setAttribute("aria-label", preset.title);
      button.innerHTML = `<i class="bi ${preset.icon}"></i>`;
      button.addEventListener("click", () => {
        if (this.handlers.onPreset) {
          this.handlers.onPreset(preset.id);
        }
      });
      this.presets.appendChild(button);
    });

    this.stats = div("sv-hud sv-gl-stats", container);
    this.stats.id = "gl-stats";

    this.tooltip = div("sv-gl-tooltip", container);
    this.tooltip.id = "gl-tooltip";
    this.tooltip.style.display = "none";

    this.notice = div("sv-hud sv-gl-notice", container);
    this.notice.id = "gl-notice";
    this.notice.style.display = "none";
  }

  /**
   * Keep the HUD clear of the floating panels.
   *
   * The rail, inspector and transport are user-resizable, so where they end is
   * measured rather than read from the layout tokens -- those go stale as soon
   * as a splitter is dragged, and a colorbar half under the inspector is the
   * kind of thing that only shows up on someone else's window size.
   */
  reflow() {
    // Edges, not widths: the panels carry a margin in HUD mode, so a width
    // alone would place the HUD inside the gap rather than clear of it.
    const edge = (selector, side) => {
      const element = document.querySelector(selector);
      if (!element || element.offsetParent === null) {
        return 0;
      }
      const rect = element.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) {
        return 0;
      }
      if (side === "left") {
        return rect.right;
      }
      if (side === "right") {
        return window.innerWidth - rect.left;
      }
      return window.innerHeight - rect.top;
    };

    const style = this.root.style;
    style.setProperty("--sv-hud-left", `${Math.round(edge("#filter-sidebar-col", "left")) + 12}px`);
    style.setProperty("--sv-hud-right", `${Math.round(edge("#subview-panel", "right")) + 12}px`);
    style.setProperty("--sv-hud-bottom", `${Math.round(edge(".sv-transport", "bottom")) + 12}px`);
  }

  /**
   * Redraw the colorbar, legend and readout for a frame.
   *
   * @param {Object} frame The decoded frame.
   * @param {string} colormap Active colormap name.
   */
  setFrame(frame, colormap) {
    if (!frame) {
      return;
    }

    const numerical = frame.cType === "numerical";
    this.colorbar.style.display = numerical ? "" : "none";
    if (numerical) {
      const [lo, hi] = frame.cRange;
      this.gradient.style.background = `linear-gradient(to top, ${gradientStops(colormap)})`;
      this.colorbarLabel.textContent = frame.cLabel || "";
      this.ticks.innerHTML = "";
      [hi, (lo + hi) / 2, lo].forEach((value) => {
        const tick = div("sv-gl-colorbar-tick", this.ticks);
        tick.textContent = Number.isFinite(value) ? String(Number(value.toPrecision(4))) : "";
      });
    }

    this._buildLegend(frame);
    this._buildReadout(frame);
  }

  _buildLegend(frame) {
    const entries = [];

    if (frame.cType === "categorical") {
      frame.groups.forEach((group, index) => {
        if (group.showlegend === false) {
          return;
        }
        entries.push({
          key: `group:${index}`,
          label: group.name || `Group ${index + 1}`,
          color: categoryCss(index),
        });
      });
    }

    if (frame.ref && (frame.ref.mesh || frame.ref.edges || frame.ref.marker)) {
      const source = frame.ref.mesh || frame.ref.marker || frame.ref.edges;
      // One entry for the whole reference: the mesh and its outline share a
      // legendgroup in the Plotly figure, and toggling the body without its
      // edges would leave a wireframe floating where the vehicle was.
      entries.push({
        key: "ref",
        label: frame.ref.name || "Reference",
        color: `rgb(${source.rgb.join(",")})`,
      });
    }

    if (frame.cloud) {
      entries.push({
        key: "cloud",
        label: frame.cloud.name || "Point Cloud",
        color: `rgb(${frame.cloud.rgb.join(",")})`,
      });
    }

    this.legend.style.display = entries.length ? "" : "none";
    this.legend.innerHTML = "";

    entries.forEach((entry) => {
      const row = div("sv-gl-legend-row", this.legend);
      row.setAttribute("role", "button");
      row.tabIndex = 0;
      if (this.hidden.has(entry.key)) {
        row.classList.add("sv-gl-legend-off");
      }
      const swatch = div("sv-gl-legend-swatch", row);
      swatch.style.background = entry.color;
      const text = div("sv-gl-legend-name", row);
      text.textContent = entry.label;

      const toggle = () => {
        if (this.hidden.has(entry.key)) {
          this.hidden.delete(entry.key);
        } else {
          this.hidden.add(entry.key);
        }
        row.classList.toggle("sv-gl-legend-off", this.hidden.has(entry.key));
        if (this.handlers.onToggleGroup) {
          this.handlers.onToggleGroup(this.hidden);
        }
      };

      row.addEventListener("click", toggle);
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          toggle();
        }
      });
    });
  }

  _buildReadout(frame) {
    const { ranges, aspect } = frame.layout;
    const fmt = (range) => `${Number(range[0].toPrecision(3))} … ${Number(range[1].toPrecision(3))}`;

    this.readout.innerHTML = "";
    [
      ["X", fmt(ranges.x)],
      ["Y", fmt(ranges.y)],
      ["Z", fmt(ranges.z)],
      ["Aspect", `${aspect.x.toFixed(2)} : ${aspect.y.toFixed(2)} : ${aspect.z.toFixed(2)}`],
    ].forEach(([name, value]) => {
      const row = div("sv-gl-readout-row", this.readout);
      const key = div("sv-gl-readout-key", row);
      key.textContent = name;
      const val = div("sv-gl-readout-value", row);
      val.textContent = value;
    });
  }

  /**
   * Update the performance line.
   *
   * @param {Object} stats `{fps, points, calls, software}`.
   */
  setStats(stats) {
    const points = stats.points >= 1000
      ? `${(stats.points / 1000).toFixed(1)}k`
      : String(stats.points);
    // Rendering is on demand, so between interactions there is no frame rate
    // to report -- and printing "0 fps" for a scene that is simply finished
    // reads as a stall. A number appears while the scene is actually moving.
    const rate = stats.fps >= 1 ? `${stats.fps.toFixed(0)} fps` : "idle";
    this.stats.textContent = `${rate} · ${points} pts · ${stats.calls} draws`;
    this.stats.classList.toggle("sv-gl-stats-warn", Boolean(stats.software));
    if (stats.software) {
      this.stats.title =
        "WebGL is running on a software rasteriser, so this may be slower than the Plotly renderer.";
    }
  }

  /**
   * Show the tooltip for a point, or hide it.
   *
   * @param {string|null} text Hover text, with `<br>` already turned into
   *     newlines, or null to hide.
   * @param {number} x Client x.
   * @param {number} y Client y.
   */
  setTooltip(text, x, y) {
    if (!text) {
      this.tooltip.style.display = "none";
      return;
    }

    // textContent, not innerHTML: these strings are built from dataset column
    // descriptions and there is no reason for the page to execute them. The
    // stylesheet carries `white-space: pre-line`, so newlines break lines.
    this.tooltip.textContent = text;
    this.tooltip.style.display = "";

    // Flip across the pointer near the edges so the tooltip stays on screen.
    const rect = this.tooltip.getBoundingClientRect();
    const padding = 14;
    const left = x + padding + rect.width > window.innerWidth ? x - rect.width - padding : x + padding;
    const top = y + padding + rect.height > window.innerHeight ? y - rect.height - padding : y + padding;
    this.tooltip.style.left = `${Math.max(4, left)}px`;
    this.tooltip.style.top = `${Math.max(4, top)}px`;
  }

  /**
   * Show a persistent message over the scene, or clear it.
   *
   * @param {string|null} text Message, or null to hide.
   */
  setNotice(text) {
    if (!text) {
      this.notice.style.display = "none";
      return;
    }
    this.notice.textContent = text;
    this.notice.style.display = "";
  }

  /** Whether a legend key is currently toggled off. */
  isHidden(key) {
    return this.hidden.has(key);
  }

  dispose() {
    [
      this.colorbar, this.legend, this.readout,
      this.presets, this.stats, this.tooltip, this.notice,
    ].forEach((element) => {
      if (element && element.parentNode) {
        element.parentNode.removeChild(element);
      }
    });
  }
}
