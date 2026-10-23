// A synthetic case, so the renderer can be built and checked before the
// readers exist.
//
// This is not a demo. P1 (the data layer) and P2 (this) were split to run in
// parallel, which only works if neither waits on the other -- so the scene is
// driven by something with the same shape as a real frame, built from
// arithmetic. It is also what `npm run web` renders, which is how the UI gets
// hot reload in a browser tab instead of an Electron restart per edit.
//
// Deleted once a case can be opened for real.

import type { Frame, Group, SceneLayout } from './frame'

const CATEGORIES = ['RADAR_FRONT', 'RADAR_FRONT_LEFT', 'RADAR_FRONT_RIGHT', 'RADAR_BACK_LEFT']

const RANGES: SceneLayout['ranges'] = {
  x: [-60, 60],
  y: [-20, 140],
  z: [-4, 8]
}

/** Relative edge lengths, the way `get_scatter3d_layout` computes them. */
function aspectOf(ranges: SceneLayout['ranges']): SceneLayout['aspect'] {
  const span = {
    x: ranges.x[1] - ranges.x[0],
    y: ranges.y[1] - ranges.y[0],
    z: ranges.z[1] - ranges.z[0]
  }
  const scale = Math.min(span.x, span.y, span.z)
  return scale === 0
    ? { x: 1, y: 1, z: 1 }
    : { x: span.x / scale, y: span.y / scale, z: span.z / scale }
}

/** Deterministic noise, so a frame looks the same every time it is drawn. */
function hash(n: number): number {
  const x = Math.sin(n * 12.9898) * 43758.5453
  return x - Math.floor(x)
}

/**
 * Points along a road that curves away from the sensor, drifting with the
 * frame so scrubbing visibly moves something.
 */
function buildGroup(groupIndex: number, frame: number, count: number): Group {
  const position = new Float32Array(count * 3)
  const value = new Float32Array(count)
  const ids = new Float64Array(count)
  const base = groupIndex * 10_000 + frame * 100

  for (let i = 0; i < count; i++) {
    const t = i / count
    const along = RANGES.y[0] + t * (RANGES.y[1] - RANGES.y[0])
    // A lane per group, bending with distance, plus a little scatter.
    const lane = (groupIndex - (CATEGORIES.length - 1) / 2) * 7
    const bend = Math.sin((along + frame * 2) / 45) * 14
    const jitter = (hash(base + i) - 0.5) * 3.5

    position[i * 3] = lane + bend + jitter
    position[i * 3 + 1] = along
    position[i * 3 + 2] = (hash(base + i + 0.5) - 0.3) * 2.2

    // Something monotonic to colour by, so the colormap is legible.
    value[i] = along
    ids[i] = base + i
  }

  const name = CATEGORIES[groupIndex]!
  return {
    name,
    count,
    position,
    value,
    ids,
    hover: (row) =>
      row < 0 || row >= count
        ? null
        : [
            `Sensor: ${name}`,
            `East (m): ${position[row * 3]!.toFixed(2)}`,
            `North (m): ${position[row * 3 + 1]!.toFixed(2)}`,
            `Up (m): ${position[row * 3 + 2]!.toFixed(2)}`,
            `Row: ${ids[row]}`
          ].join('\n'),
    rgb: null,
    size: 3,
    showlegend: true
  }
}

/** A box standing in for the ego vehicle, at the origin. */
function egoMesh() {
  const w = 1.0
  const l = 2.4
  const h = 0.8
  const corners: Array<[number, number, number]> = [
    [-w, -l, 0], [w, -l, 0], [w, l, 0], [-w, l, 0],
    [-w, -l, h], [w, -l, h], [w, l, h], [-w, l, h]
  ]
  const faces = [
    [0, 1, 2], [0, 2, 3], [4, 6, 5], [4, 7, 6],
    [0, 4, 5], [0, 5, 1], [1, 5, 6], [1, 6, 2],
    [2, 6, 7], [2, 7, 3], [3, 7, 4], [3, 4, 0]
  ]
  const edges = [
    [0, 1], [1, 2], [2, 3], [3, 0],
    [4, 5], [5, 6], [6, 7], [7, 4],
    [0, 4], [1, 5], [2, 6], [3, 7]
  ]

  const position = new Float32Array(corners.length * 3)
  corners.forEach((c, i) => position.set(c, i * 3))

  const index = new Uint32Array(faces.length * 3)
  faces.forEach((f, i) => index.set(f, i * 3))

  const segments = new Float32Array(edges.length * 6)
  edges.forEach(([a, b], i) => {
    segments.set(corners[a!]!, i * 6)
    segments.set(corners[b!]!, i * 6 + 3)
  })

  return {
    mesh: { position, index, rgb: [255, 255, 255] as [number, number, number], opacity: 0.3 },
    edges: { position: segments, rgb: [255, 255, 255] as [number, number, number] },
    marker: null,
    name: 'Ego Vehicle'
  }
}

/** A sparse backdrop, standing in for the lidar cloud. */
function buildCloud(frame: number, count: number) {
  const position = new Float32Array(count * 3)
  for (let i = 0; i < count; i++) {
    const h0 = hash(frame * 7919 + i)
    const h1 = hash(frame * 7919 + i + 0.33)
    const h2 = hash(frame * 7919 + i + 0.66)
    position[i * 3] = RANGES.x[0] + h0 * (RANGES.x[1] - RANGES.x[0])
    position[i * 3 + 1] = RANGES.y[0] + h1 * (RANGES.y[1] - RANGES.y[0])
    position[i * 3 + 2] = -1 + h2 * 1.2
  }
  return {
    position,
    count,
    rgb: [141, 153, 174] as [number, number, number],
    size: 1.2,
    opacity: 0.35,
    name: 'Point Cloud'
  }
}

export const FIXTURE_FRAMES = 60

/**
 * Build one synthetic frame.
 *
 * @param index Slider position.
 * @param options `categorical` colours by sensor rather than by distance;
 *     `hidden` drops rows by their id, standing in for click-to-hide.
 */
export function fixtureFrame(
  index: number,
  options: { categorical?: boolean; hidden?: Set<number> } = {}
): Frame {
  const groups = CATEGORIES.map((_, g) => buildGroup(g, index, 180))

  if (options.hidden?.size) {
    for (const group of groups) {
      const keep: number[] = []
      for (let i = 0; i < group.count; i++) {
        if (!options.hidden.has(group.ids![i]!)) {
          keep.push(i)
        }
      }
      if (keep.length === group.count) {
        continue
      }
      const position = new Float32Array(keep.length * 3)
      const value = new Float32Array(keep.length)
      const ids = new Float64Array(keep.length)
      keep.forEach((src, dst) => {
        position.set(group.position.subarray(src * 3, src * 3 + 3), dst * 3)
        value[dst] = group.value![src]!
        ids[dst] = group.ids![src]!
      })
      const original = group.hover
      group.position = position
      group.value = value
      group.ids = ids
      group.count = keep.length
      group.hover = (row) => original(keep[row] ?? -1)
    }
  }

  return {
    index,
    cType: options.categorical ? 'categorical' : 'numerical',
    cRange: [RANGES.y[0], RANGES.y[1]],
    cLabel: options.categorical ? 'Sensor' : 'North (m)',
    baseSize: 3,
    groups,
    ref: egoMesh(),
    cloud: buildCloud(index, 4000),
    layout: {
      ranges: RANGES,
      aspect: aspectOf(RANGES),
      labels: { x: 'East (m)', y: 'North (m)', z: 'Up (m)' },
      title: `Index: ${index}`
    }
  }
}
