// Turns what the buffer holds into what the scene draws.
//
// The buffer holds Plotly traces, because the same bundles still feed the
// Plotly renderer and the background pre-compute that fills them is shared. The
// scene wants flat typed arrays. This module is the join, and it is the only
// place that knows the trace shapes `viz/graph_data.py` emits -- everything
// downstream sees the normalized frame described below.
//
// A frame:
//
//     { index, cType, cRange, cLabel, baseSize,
//       groups: [{ name, count, position, value, rgb, ids, hover }],
//       ref:    { mesh, edges, marker },
//       cloud:  { position, count, rgb, size, opacity } | null,
//       layout: { ranges, aspect, labels, title } }
//
// `position` is always a Float32Array of interleaved xyz. `rgb` is always
// `[r, g, b]` in 0-255, resolved here so no later stage has to parse CSS.

import { parseColor, categoryColor } from "./sv_color.esm.js";

const DEFAULT_RANGE = [-20, 20];

/**
 * Interleave three coordinate arrays into one Float32Array.
 *
 * Skips any vertex with a non-finite component, which is how Plotly line
 * traces mark a pen lift and how a filtered frame can carry NaNs.
 *
 * @param {Array} xs X values.
 * @param {Array} ys Y values.
 * @param {Array} zs Z values.
 * @returns {{position: Float32Array, count: number, kept: number[]}}
 */
function interleave(xs, ys, zs) {
  const n = Math.min(xs ? xs.length : 0, ys ? ys.length : 0, zs ? zs.length : 0);
  const position = new Float32Array(n * 3);
  const kept = [];
  let count = 0;

  for (let i = 0; i < n; i++) {
    const x = xs[i];
    const y = ys[i];
    const z = zs[i];
    if (x === null || y === null || z === null) {
      continue;
    }
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) {
      continue;
    }
    const o = count * 3;
    position[o] = x;
    position[o + 1] = y;
    position[o + 2] = z;
    kept.push(i);
    count++;
  }

  return { position, count, kept };
}

/**
 * Decode a line trace into discrete segments.
 *
 * `_edge_trace` draws a whole wireframe as one polyline with a `null` vertex
 * between edges to lift the pen. LineSegments wants vertex pairs, so each run
 * between lifts becomes its own chain of pairs -- which handles a run of two
 * (the only thing that file emits today) without assuming it.
 *
 * @param {Object} trace A Plotly `mode: "lines"` scatter3d trace.
 * @returns {{position: Float32Array, rgb: number[]}|null}
 */
function decodeEdges(trace) {
  const xs = trace.x || [];
  const ys = trace.y || [];
  const zs = trace.z || [];
  const n = Math.min(xs.length, ys.length, zs.length);

  const segments = [];
  let run = [];

  const flush = () => {
    for (let i = 0; i + 1 < run.length; i++) {
      segments.push(run[i], run[i + 1]);
    }
    run = [];
  };

  for (let i = 0; i < n; i++) {
    const x = xs[i];
    const y = ys[i];
    const z = zs[i];
    if (x === null || y === null || z === null || !Number.isFinite(x)) {
      flush();
      continue;
    }
    run.push([x, y, z]);
  }
  flush();

  if (segments.length === 0) {
    return null;
  }

  const position = new Float32Array(segments.length * 3);
  for (let i = 0; i < segments.length; i++) {
    position[i * 3] = segments[i][0];
    position[i * 3 + 1] = segments[i][1];
    position[i * 3 + 2] = segments[i][2];
  }

  return {
    position,
    rgb: parseColor((trace.line && trace.line.color) || "#ffffff"),
  };
}

/**
 * Decode a mesh3d trace.
 *
 * @param {Object} trace A Plotly mesh3d trace.
 * @returns {{position: Float32Array, index: Uint32Array, rgb: number[], opacity: number}|null}
 */
function decodeMesh(trace) {
  const { position, count } = interleave(trace.x, trace.y, trace.z);
  if (count === 0) {
    return null;
  }

  const faces = Math.min(
    trace.i ? trace.i.length : 0,
    trace.j ? trace.j.length : 0,
    trace.k ? trace.k.length : 0
  );
  const index = new Uint32Array(faces * 3);
  for (let f = 0; f < faces; f++) {
    index[f * 3] = trace.i[f];
    index[f * 3 + 1] = trace.j[f];
    index[f * 3 + 2] = trace.k[f];
  }

  return {
    position: position.subarray(0, count * 3),
    index,
    rgb: parseColor(trace.color || "#ffffff"),
    opacity: trace.opacity === undefined ? 0.35 : trace.opacity,
  };
}

/**
 * Decode the detection traces of one frame.
 *
 * Which colour mode the frame is in is read off the traces rather than passed
 * in: the numerical branch of `get_scatter3d_data` puts an array in
 * `marker.color` and emits exactly one trace, and the categorical branch sets
 * no marker colour at all and emits one trace per group. So an array there is
 * the discriminator, and it is the same fact in both renderers.
 *
 * @param {Array} traces The bundle's `fig`.
 * @param {Array} hoverStrings The bundle's `hover_strings`, parallel to it.
 * @returns {{groups: Array, cType: string, cRange: number[], cLabel: string, baseSize: number}}
 */
export function decodeTraces(traces, hoverStrings) {
  const groups = [];
  let cType = "categorical";
  let cRange = [0, 1];
  let cLabel = "";
  let baseSize = 3;

  (traces || []).forEach((trace, i) => {
    if (!trace) {
      return;
    }

    const marker = trace.marker || {};
    const colors = Array.isArray(marker.color) ? marker.color : null;

    if (colors) {
      cType = "numerical";
      if (marker.cmin !== undefined && marker.cmax !== undefined) {
        cRange = [marker.cmin, marker.cmax];
      }
      const title = marker.colorbar && marker.colorbar.title;
      cLabel = (title && title.text) || cLabel;
    }

    if (typeof marker.size === "number") {
      baseSize = marker.size;
    }

    const { position, count, kept } = interleave(trace.x, trace.y, trace.z);

    let value = null;
    if (colors) {
      value = new Float32Array(count);
      for (let k = 0; k < count; k++) {
        const v = colors[kept[k]];
        value[k] = Number.isFinite(v) ? v : 0;
      }
    }

    let ids = null;
    if (Array.isArray(trace.ids)) {
      ids = new Float64Array(count);
      for (let k = 0; k < count; k++) {
        ids[k] = trace.ids[kept[k]];
      }
    }

    // A lookup rather than an array, so this path and the binary one hand the
    // scene the same shape -- the packed form holds its text as bytes and
    // decodes one slice on demand, which an array would force it to undo.
    const source = hoverStrings && hoverStrings[i];
    const texts = Array.isArray(source) && source.length
      ? kept.map((index) => source[index])
      : null;
    const hover = texts ? (row) => texts[row] ?? null : () => null;

    groups.push({
      name: trace.name === null || trace.name === undefined ? "" : String(trace.name),
      count,
      position,
      value,
      ids,
      hover,
      // Numerical groups colour per point; categorical groups take the
      // colorway entry for their position, which is how Plotly assigns it.
      rgb: colors ? null : categoryColor(groups.length),
      size: typeof marker.size === "number" ? marker.size : baseSize,
      showlegend: trace.showlegend !== false,
    });
  });

  return { groups, cType, cRange, cLabel, baseSize };
}

/**
 * Sort the reference traces into the three things they can be.
 *
 * @param {Array} traces The bundle's `ref_fig`.
 * @returns {{mesh: Object|null, edges: Object|null, marker: Object|null, name: string}}
 */
export function decodeReference(traces) {
  const out = { mesh: null, edges: null, marker: null, name: "Reference" };

  (traces || []).forEach((trace) => {
    if (!trace) {
      return;
    }
    if (trace.name) {
      out.name = String(trace.name);
    }

    if (trace.type === "mesh3d") {
      out.mesh = decodeMesh(trace);
      return;
    }
    if (trace.mode === "lines") {
      out.edges = decodeEdges(trace);
      return;
    }

    const { position, count } = interleave(trace.x, trace.y, trace.z);
    if (count > 0) {
      const marker = trace.marker || {};
      out.marker = {
        position: position.subarray(0, count * 3),
        count,
        rgb: parseColor(marker.color || "rgb(255,255,255)"),
        size: typeof marker.size === "number" ? marker.size : 6,
      };
    }
  });

  return out;
}

/**
 * Decode the point-cloud backdrop trace.
 *
 * @param {Object|null} trace The `/api/cloud` trace, or null.
 * @returns {Object|null} Decoded cloud, or null when there is none.
 */
export function decodeCloud(trace) {
  if (!trace) {
    return null;
  }

  const { position, count } = interleave(trace.x, trace.y, trace.z);
  if (count === 0) {
    return null;
  }

  const marker = trace.marker || {};
  return {
    position: position.subarray(0, count * 3),
    count,
    rgb: parseColor(marker.color || "#8d99ae"),
    size: typeof marker.size === "number" ? marker.size : 1.2,
    opacity: marker.opacity === undefined ? 0.35 : marker.opacity,
    name: trace.name || "Point Cloud",
  };
}

/**
 * Pull the scene geometry out of a Plotly layout.
 *
 * Ranges are taken as given: `get_scatter3d_layout` fixes them from the filter
 * sliders with `autorange: False`, so the box is the filters' box and must not
 * be re-derived from the points in it.
 *
 * @param {Object} layout The bundle's `fig_layout`.
 * @returns {{ranges: Object, aspect: Object, labels: Object, title: string}}
 */
export function decodeLayout(layout) {
  const scene = (layout && layout.scene) || {};

  const axis = (key, fallback) => {
    const config = scene[key] || {};
    const range = Array.isArray(config.range) && config.range.length === 2
      ? config.range.map(Number)
      : fallback.slice();
    const title = config.title && config.title.text;
    return { range, label: title === null || title === undefined ? "" : String(title) };
  };

  const x = axis("xaxis", DEFAULT_RANGE);
  const y = axis("yaxis", DEFAULT_RANGE);
  const z = axis("zaxis", DEFAULT_RANGE);
  const aspect = scene.aspectratio || { x: 1, y: 1, z: 1 };

  const title = layout && layout.title;
  return {
    ranges: { x: x.range, y: y.range, z: z.range },
    aspect: {
      x: Number(aspect.x) || 1,
      y: Number(aspect.y) || 1,
      z: Number(aspect.z) || 1,
    },
    labels: { x: x.label, y: y.label, z: z.label },
    title: typeof title === "string" ? title : (title && title.text) || "",
  };
}

/**
 * Decode one buffered bundle into a frame.
 *
 * @param {Object} bundle `{fig, hover_strings, ref_fig, fig_layout}`.
 * @param {number} index Slider position this bundle is for.
 * @returns {Object} The normalized frame.
 */
export function decodeFrame(bundle, index) {
  const { groups, cType, cRange, cLabel, baseSize } = decodeTraces(
    bundle.fig,
    bundle.hover_strings
  );

  return {
    index,
    cType,
    cRange,
    cLabel,
    baseSize,
    groups,
    ref: decodeReference(bundle.ref_fig),
    cloud: null,
    layout: decodeLayout(bundle.fig_layout),
  };
}
