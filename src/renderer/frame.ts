// The shape the scene draws.
//
// One representation. Under Dash a frame existed four times over -- a pandas
// DataFrame, a set of Plotly trace dicts, a packed binary blob, and finally
// typed arrays -- because it crossed a network boundary as JSON and the
// per-point hover text had to be kept out of that. None of those boundaries
// are left, so the table is turned into this directly.
//
// Positions are interleaved xyz. Colors are `[r, g, b]` in 0-255, resolved
// here so no later stage parses CSS.

/** One drawn group: a color category, or the single group of a numeric key. */
export interface Group {
  name: string
  count: number
  /** Interleaved xyz, `count * 3` long. */
  position: Float32Array
  /** The color-key value per point, when the key is numeric. */
  value: Float32Array | null
  /** The table's own row index per point; what a click reports. */
  ids: Float64Array | Uint32Array | null
  /** Hover text by row, built on demand. */
  hover: (row: number) => string | null
  /** Flat color for a categorical group; null when a colormap applies. */
  rgb: [number, number, number] | null
  size: number
  showlegend: boolean
  /** Pick colors, written by the picker before upload. */
  pick?: Float32Array
}

export interface ReferenceMesh {
  position: Float32Array
  index: Uint32Array
  rgb: [number, number, number]
  opacity: number
}

export interface Reference {
  mesh: ReferenceMesh | null
  edges: { position: Float32Array; rgb: [number, number, number] } | null
  marker: {
    position: Float32Array
    count: number
    rgb: [number, number, number]
    size: number
  } | null
  name: string
}

export interface Cloud {
  position: Float32Array
  count: number
  rgb: [number, number, number]
  size: number
  opacity: number
  name: string
}

export interface SceneLayout {
  /** Axis ranges in data units. Fixed by the filters, never derived from the points. */
  ranges: { x: [number, number]; y: [number, number]; z: [number, number] }
  /** Relative edge lengths the box is drawn with. */
  aspect: { x: number; y: number; z: number }
  labels: { x: string; y: string; z: string }
  title: string
}

export interface Frame {
  index: number
  cType: 'numerical' | 'categorical'
  cRange: [number, number]
  cLabel: string
  baseSize: number
  groups: Group[]
  ref: Reference
  cloud: Cloud | null
  layout: SceneLayout
}

/**
 * What `sv_scene.create(...).setFrame` takes.
 *
 * `frames` is newest first: index 0 is the live frame and the rest are the
 * decay trail, which fades across them.
 */
export interface ScenePayload {
  frames: Frame[]
  colormap: string
  sizeVary: boolean
  /** Hover text is only built for a paused view, as it was under Dash. */
  paused: boolean
}
