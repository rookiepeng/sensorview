// Reading the packed frame format.
//
// The mirror of `viz/gl_pack.py`; the container is documented there. The point
// of it is that nothing in here parses a number: every section becomes a typed
// array *view* onto the ArrayBuffer the fetch produced, so the coordinates go
// to the GPU without being copied, and a tooltip costs a decode of one slice
// rather than a parse of every string in the frame.
//
// The output is the same normalized frame shape `sv_decode.esm.js` produces
// from the JSON bundles, so the scene cannot tell which path a frame came
// through.

import { categoryColor } from "./sv_color.esm.js";

const MAGIC_FRAME = "SVF1";
const MAGIC_BATCH = "SVB1";
const MAGIC_CLOUD = "SVC1";
const RESET = 0xffffffff;

const decoder = new TextDecoder("utf-8");

function magic(buffer, offset = 0) {
  return String.fromCharCode(...new Uint8Array(buffer, offset, 4));
}

/**
 * A typed-array view onto one declared section.
 *
 * A view, not a copy: the whole format is aligned to four bytes so that this
 * is possible, since `new Float32Array(buffer, off, n)` throws on a misaligned
 * offset rather than falling back to copying.
 *
 * @param {ArrayBuffer} buffer The frame blob.
 * @param {number} base Where this frame starts inside it.
 * @param {Object|null} section `{off, len, dtype}` from the header.
 * @returns {Float32Array|Uint32Array|Uint8Array|null}
 */
function view(buffer, base, section) {
  if (!section || !section.len) {
    return null;
  }
  const offset = base + section.off;
  if (section.dtype === "f32") {
    return new Float32Array(buffer, offset, section.len / 4);
  }
  if (section.dtype === "u32") {
    return new Uint32Array(buffer, offset, section.len / 4);
  }
  return new Uint8Array(buffer, offset, section.len);
}

/**
 * Hover text for one point, decoded on demand.
 *
 * The frame carries every point's text, but a session shows a handful of
 * tooltips -- so the blob is held as bytes and only the slice being asked for
 * is turned into a string.
 *
 * @param {Uint32Array|null} offsets Offset table, `count + 1` entries.
 * @param {Uint8Array|null} text The group's UTF-8 blob.
 * @returns {function(number): string|null} Lookup by row.
 */
function hoverReader(offsets, text) {
  if (!offsets || !text || offsets.length < 2) {
    return () => null;
  }
  return (row) => {
    if (row < 0 || row + 1 >= offsets.length) {
      return null;
    }
    const start = offsets[row];
    const end = offsets[row + 1];
    return end > start ? decoder.decode(text.subarray(start, end)) : "";
  };
}

/**
 * Decode one packed frame.
 *
 * @param {ArrayBuffer} buffer Buffer holding the frame.
 * @param {number} base Byte offset the frame starts at.
 * @returns {Object} The normalized frame.
 */
export function decodeFrameBinary(buffer, base = 0) {
  if (magic(buffer, base) !== MAGIC_FRAME) {
    throw new Error("not a packed frame");
  }

  const headerLen = new DataView(buffer).getUint32(base + 4, true);
  const header = JSON.parse(
    decoder.decode(new Uint8Array(buffer, base + 8, headerLen))
  );

  const groups = header.groups.map((group, index) => {
    const read = hoverReader(view(buffer, base, group.hoff), view(buffer, base, group.htxt));
    return {
      name: group.name || "",
      count: group.count,
      position: view(buffer, base, group.pos) || new Float32Array(0),
      value: view(buffer, base, group.val),
      ids: view(buffer, base, group.ids),
      // The JSON path hands over an array of strings; this hands over the same
      // lookup behind a function, so the scene's consumer is unchanged.
      hover: read,
      rgb: group.rgb || (header.c_type === "numerical" ? null : categoryColor(index)),
      size: header.base_size,
      showlegend: group.showlegend !== false,
    };
  });

  const ref = { mesh: null, edges: null, marker: null, name: header.ref.name || "Reference" };
  if (header.ref.mesh) {
    ref.mesh = {
      position: view(buffer, base, header.ref.mesh.verts),
      index: view(buffer, base, header.ref.mesh.faces),
      rgb: header.ref.mesh.rgb,
      opacity: header.ref.mesh.opacity,
    };
  }
  if (header.ref.edges) {
    ref.edges = {
      position: view(buffer, base, header.ref.edges.segs),
      rgb: header.ref.edges.rgb,
    };
  }
  if (header.ref.marker) {
    ref.marker = {
      position: view(buffer, base, header.ref.marker.pos),
      count: header.ref.marker.count,
      rgb: header.ref.marker.rgb,
      size: header.ref.marker.size,
    };
  }

  return {
    index: header.index,
    cType: header.c_type,
    cRange: header.c_range,
    cLabel: header.c_label,
    baseSize: header.base_size,
    groups,
    ref,
    cloud: null,
    layout: header.layout,
  };
}

/**
 * Split a batch response into per-frame blobs.
 *
 * Each frame is handed back with the shared buffer and its own offset, so the
 * batch is never copied apart.
 *
 * @param {ArrayBuffer} buffer The batch response.
 * @returns {{reset: boolean, frames: Array<{buffer: ArrayBuffer, base: number, length: number}>}}
 */
export function splitBatch(buffer) {
  if (buffer.byteLength < 8 || magic(buffer) !== MAGIC_BATCH) {
    return { reset: false, frames: [] };
  }

  const dv = new DataView(buffer);
  const count = dv.getUint32(4, true);
  if (count === RESET) {
    return { reset: true, frames: [] };
  }

  const frames = [];
  let cursor = 8 + count * 4;
  for (let i = 0; i < count; i++) {
    const length = dv.getUint32(8 + i * 4, true);
    frames.push({ buffer, base: cursor, length });
    cursor += length;
  }
  return { reset: false, frames };
}

/**
 * Decode the packed point-cloud backdrop.
 *
 * @param {ArrayBuffer} buffer The cloud response.
 * @returns {Object|null} The decoded cloud, or null when there is none.
 */
export function decodeCloudBinary(buffer) {
  if (!buffer || buffer.byteLength < 8 || magic(buffer) !== MAGIC_CLOUD) {
    return null;
  }

  const headerLen = new DataView(buffer).getUint32(4, true);
  const header = JSON.parse(decoder.decode(new Uint8Array(buffer, 8, headerLen)));
  if (!header.count) {
    return null;
  }

  const prefix = 8 + headerLen;
  const start = prefix + ((4 - (prefix % 4)) % 4);
  return {
    position: new Float32Array(buffer, start, header.count * 3),
    count: header.count,
    rgb: header.rgb,
    size: header.size,
    opacity: header.opacity,
    name: header.name,
  };
}
