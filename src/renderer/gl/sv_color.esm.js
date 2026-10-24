// Color for the GL renderer: continuous colormaps as a lookup texture, and
// the categorical palette.
//
// Neither palette is defined here. Both are Plotly's, shipped to the browser in
// the `gl-palette` store (see `layouts/app_layout.py`), because the two
// renderers have to agree exactly -- a user toggling between them must not see
// the colors move. Re-typing Plotly's tables in JS would make that agreement a
// thing to maintain rather than a thing that is true by construction.

import { DataTexture, RGBAFormat, UnsignedByteType, LinearFilter, ClampToEdgeWrapping } from "three";

// Width of the generated lookup texture. 256 is the usual choice: finer than
// any colormap's own stop count, and one texel per byte of the normalized
// value, so no colormap is resampled visibly.
const LUT_SIZE = 256;

// Fallbacks for a page that somehow has no palette store. Grey everywhere is
// legible and obviously wrong, which is better than failing to draw.
const FALLBACK_SCALE = [
  [0, "rgb(68,1,84)"],
  [0.5, "rgb(33,145,140)"],
  [1, "rgb(253,231,37)"],
];
const FALLBACK_COLORWAY = ["#636efa"];

let palette = { colorscales: {}, colorway: FALLBACK_COLORWAY.slice() };

const lutCache = new Map();

/**
 * Adopt the palette shipped from the server.
 *
 * @param {{colorscales: Object, colorway: string[]}} next Store contents.
 */
export function setPalette(next) {
  if (!next) {
    return;
  }
  palette = {
    colorscales: next.colorscales || {},
    colorway: (next.colorway && next.colorway.length ? next.colorway : FALLBACK_COLORWAY).slice(),
  };
  // Stops may have changed under a name; nothing cached is trustworthy.
  lutCache.forEach((texture) => texture.dispose());
  lutCache.clear();
}

/**
 * Parse a CSS color as Plotly writes it into a colorscale.
 *
 * Only the two forms Plotly's built-in scales use -- `rgb(r,g,b)` and `#rrggbb`
 * -- plus `#rgb` for safety. Anything else returns mid grey rather than
 * throwing: one unparseable stop should not blank the scene.
 *
 * @param {string} value Color string.
 * @returns {number[]} `[r, g, b]`, each 0-255.
 */
export function parseColor(value) {
  if (typeof value !== "string") {
    return [128, 128, 128];
  }

  const rgb = value.match(/rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)/i);
  if (rgb) {
    return [Number(rgb[1]) | 0, Number(rgb[2]) | 0, Number(rgb[3]) | 0];
  }

  const hex = value.trim().replace(/^#/, "");
  if (hex.length === 6) {
    return [
      parseInt(hex.slice(0, 2), 16),
      parseInt(hex.slice(2, 4), 16),
      parseInt(hex.slice(4, 6), 16),
    ];
  }
  if (hex.length === 3) {
    return [
      parseInt(hex[0] + hex[0], 16),
      parseInt(hex[1] + hex[1], 16),
      parseInt(hex[2] + hex[2], 16),
    ];
  }

  return [128, 128, 128];
}

/**
 * Sample a Plotly colorscale into a flat RGBA byte array.
 *
 * Plotly interpolates linearly between stops in RGB, so this does the same.
 *
 * @param {Array} scale Plotly colorscale: `[[t, color], ...]`, t ascending 0-1.
 * @returns {Uint8Array} `LUT_SIZE * 4` bytes.
 */
function sample(scale) {
  const stops = (scale && scale.length ? scale : FALLBACK_SCALE).map((stop) => ({
    t: Number(stop[0]),
    rgb: parseColor(stop[1]),
  }));
  stops.sort((a, b) => a.t - b.t);

  const data = new Uint8Array(LUT_SIZE * 4);
  let cursor = 0;

  for (let i = 0; i < LUT_SIZE; i++) {
    const t = i / (LUT_SIZE - 1);
    while (cursor < stops.length - 2 && t > stops[cursor + 1].t) {
      cursor++;
    }

    const lo = stops[cursor];
    const hi = stops[Math.min(cursor + 1, stops.length - 1)];
    const span = hi.t - lo.t;
    const f = span > 0 ? Math.min(Math.max((t - lo.t) / span, 0), 1) : 0;

    const o = i * 4;
    data[o] = Math.round(lo.rgb[0] + (hi.rgb[0] - lo.rgb[0]) * f);
    data[o + 1] = Math.round(lo.rgb[1] + (hi.rgb[1] - lo.rgb[1]) * f);
    data[o + 2] = Math.round(lo.rgb[2] + (hi.rgb[2] - lo.rgb[2]) * f);
    data[o + 3] = 255;
  }

  return data;
}

/**
 * The lookup texture for a named colormap, built once and cached.
 *
 * @param {string} name Colormap name, as `colormap-3d` holds it.
 * @returns {DataTexture} A 256x1 RGBA texture, sampled linearly.
 */
export function lutTexture(name) {
  const key = String(name || "Portland");
  const cached = lutCache.get(key);
  if (cached) {
    return cached;
  }

  const texture = new DataTexture(
    sample(palette.colorscales[key]),
    LUT_SIZE,
    1,
    RGBAFormat,
    UnsignedByteType
  );
  texture.minFilter = LinearFilter;
  texture.magFilter = LinearFilter;
  texture.wrapS = ClampToEdgeWrapping;
  texture.wrapT = ClampToEdgeWrapping;
  texture.generateMipmaps = false;
  texture.needsUpdate = true;

  lutCache.set(key, texture);
  return texture;
}

/**
 * CSS stops for a colorbar drawn as a `linear-gradient`.
 *
 * Built from the same sampled table as the texture, so the HUD swatch and the
 * points cannot drift apart.
 *
 * @param {string} name Colormap name.
 * @param {number} steps How many stops to emit.
 * @returns {string} The gradient's color-stop list.
 */
export function gradientStops(name, steps = 16) {
  const data = sample(palette.colorscales[String(name || "Portland")]);
  const out = [];
  for (let i = 0; i < steps; i++) {
    const t = i / (steps - 1);
    const o = Math.round(t * (LUT_SIZE - 1)) * 4;
    out.push(`rgb(${data[o]},${data[o + 1]},${data[o + 2]}) ${(t * 100).toFixed(1)}%`);
  }
  return out.join(", ");
}

/**
 * The categorical color for the nth group.
 *
 * Plotly assigns colorway entries in trace order and wraps, and the categorical
 * branch of `get_scatter3d_data` emits one trace per group in sorted order --
 * so indexing the same way reproduces the same assignment.
 *
 * @param {number} index Group's position in the frame.
 * @returns {number[]} `[r, g, b]`, each 0-255.
 */
export function categoryColor(index) {
  const way = palette.colorway;
  return parseColor(way[((index % way.length) + way.length) % way.length]);
}

/**
 * The categorical color as CSS, for legend swatches.
 *
 * @param {number} index Group's position in the frame.
 * @returns {string} A `#rrggbb` string.
 */
export function categoryCss(index) {
  const [r, g, b] = categoryColor(index);
  return `#${((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1)}`;
}
