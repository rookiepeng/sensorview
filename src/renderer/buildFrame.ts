// Turning the table into the thing the scene draws.
//
// This is what `viz/graph_data.py` did, minus Plotly. The Python built trace
// dictionaries, which then became a packed binary blob, which the browser
// decoded back into typed arrays; here the typed arrays are built directly
// from the columns, which are already typed arrays.
//
// The grouping rule is carried over exactly, because it decides what the
// legend says and which color each point gets: a numeric color key makes one
// group colored by a lookup table, and a categorical one makes a group per
// level, sorted, each with a flat color from the palette in that order.

import type { Frame, Group, SceneLayout } from './frame'
import {
  filterAll,
  frameRows,
  rangeOf,
  type ColumnMeta,
  type FilterState,
  type Table
} from '@shared/table'

export interface BuildOptions {
  x: string
  y: string
  z: string
  /** Column driving color. */
  color: string
  filters: FilterState
  /** Column metadata, for hover text and labels. */
  keys: Record<string, ColumnMeta>
  /** Hover text is only built when the view is standing still. */
  withHover: boolean
  /**
   * The reference's extent across the log, when it has a pose sidecar.
   *
   * The box is fixed for the log rather than fitted per frame, so a reference
   * that drives outside the detections' extent has to widen it here or it is
   * clipped away at the edge of the scene.
   */
  refBounds?: Record<'x' | 'y' | 'z', [number, number]> | null
  /**
   * The columns a reference pose is in: the manifest's `x_3d`/`y_3d`/`z_3d`.
   * Missing fields fall back to `X`/`Y`/`Z`.
   */
  position?: { x: string | null; y: string | null; z: string | null }
  /**
   * Draw every filtered row rather than one frame's.
   *
   * Overlay mode. The slider position still names the frame for the title
   * and for anything placed per frame, but the geometry is the whole table.
   */
  overlay?: boolean
}

const EMPTY_LAYOUT: SceneLayout = {
  ranges: { x: [-1, 1], y: [-1, 1], z: [-1, 1] },
  aspect: { x: 1, y: 1, z: 1 },
  labels: { x: '', y: '', z: '' },
  title: ''
}

function label(name: string, keys: Record<string, ColumnMeta>): string {
  const meta = keys[name]
  if (!meta) {
    return name
  }
  const described = meta.description || name
  return meta.unit ? `${described} (${meta.unit})` : described
}

/**
 * Relative edge lengths for a box, as `get_scatter3d_layout` computes them.
 *
 * Normalizing by the shortest span rather than the longest is what keeps a
 * flat slab readable: a 400 x 400 x 20 box drawn to its own proportions is a
 * sheet of paper seen edge-on.
 */
function aspectOf(ranges: SceneLayout['ranges']): SceneLayout['aspect'] {
  const span = {
    x: ranges.x[1] - ranges.x[0],
    y: ranges.y[1] - ranges.y[0],
    z: ranges.z[1] - ranges.z[0]
  }
  const scale = Math.min(span.x, span.y, span.z)
  // A filter can collapse an axis to a single value, which would divide by
  // zero; a cube is a defensible thing to draw in that case.
  return scale === 0
    ? { x: 1, y: 1, z: 1 }
    : { x: span.x / scale, y: span.y / scale, z: span.z / scale }
}

/** Pad a degenerate range so the box has a drawable extent. */
function padded(range: [number, number]): [number, number] {
  return range[0] === range[1] ? [range[0] - 0.5, range[1] + 0.5] : range
}

/**
 * Build the hover reader for a set of rows.
 *
 * Deferred rather than materialized: a frame has thousands of points and a
 * session shows a handful of tooltips, so the strings are formatted on the way
 * out. The Python built one per point and shipped them all, which is what made
 * hover the largest thing on the wire and why the binary format existed.
 */
function hoverReader(
  table: Table,
  rows: Int32Array,
  keys: Record<string, ColumnMeta>
): (row: number) => string | null {
  const columns = [...table.columns.values()].filter((column) => column.name !== table.frameKey)

  return (index) => {
    if (index < 0 || index >= rows.length) {
      return null
    }
    const row = rows[index]!
    const lines: string[] = []
    for (const column of columns) {
      const meta = keys[column.name] ?? {}
      const name = meta.description || column.name
      if (column.kind === 'number') {
        const value = column.values[row]!
        if (!Number.isFinite(value)) {
          continue
        }
        const decimals = meta.decimal ?? 2
        lines.push(`${name}: ${value.toFixed(decimals)}`)
      } else {
        const code = column.codes[row]!
        if (code >= 0) {
          lines.push(`${name}: ${column.levels[code]}`)
        }
      }
    }
    return lines.join('\n')
  }
}

function makeGroup(
  table: Table,
  rows: Int32Array,
  name: string,
  options: BuildOptions,
  value: Float64Array | null
): Group {
  const x = table.columns.get(options.x)
  const y = table.columns.get(options.y)
  const z = table.columns.get(options.z)

  const count = rows.length
  const position = new Float32Array(count * 3)
  const ids = new Float64Array(count)
  const values = value ? new Float32Array(count) : null

  for (let i = 0; i < count; i++) {
    const row = rows[i]!
    position[i * 3] = x?.kind === 'number' ? x.values[row]! : 0
    position[i * 3 + 1] = y?.kind === 'number' ? y.values[row]! : 0
    position[i * 3 + 2] = z?.kind === 'number' ? z.values[row]! : 0
    ids[i] = row
    if (values) {
      const v = value![row]!
      values[i] = Number.isFinite(v) ? v : 0
    }
  }

  return {
    name,
    count,
    position,
    value: values,
    ids,
    hover: options.withHover ? hoverReader(table, rows, options.keys) : () => null,
    rgb: null,
    size: 3,
    showlegend: true
  }
}

/**
 * Build one frame.
 *
 * @param table The loaded log.
 * @param position Slider position.
 * @param options Axis and color columns, filters, column metadata.
 * @returns The frame the scene draws, with no groups when the filters leave
 *     nothing -- an empty frame is a frame, not an error.
 */
export function buildFrame(table: Table, position: number, options: BuildOptions): Frame {
  const mask = filterAll(table, options.filters)

  const kept: number[] = []
  if (options.overlay) {
    // Every filtered row, in table order. Frame order would mean walking the
    // CSR index for no gain -- nothing downstream of here cares which frame
    // a point came from once they are all drawn at once.
    for (let row = 0; row < table.rows; row++) {
      if (mask[row] === 1) {
        kept.push(row)
      }
    }
  } else {
    const all = frameRows(table, position)
    for (let i = 0; i < all.length; i++) {
      if (mask[all[i]!] === 1) {
        kept.push(all[i]!)
      }
    }
  }
  const rows = Int32Array.from(kept)

  const color = table.columns.get(options.color)
  const numeric = color?.kind === 'number'

  const groups: Group[] = []
  if (rows.length > 0) {
    if (numeric) {
      groups.push(makeGroup(table, rows, label(options.color, options.keys), options, color.values))
    } else if (color?.kind === 'string') {
      // One group per level, in sorted order -- which is the order the palette
      // is assigned in, so changing it recolors the whole scene.
      const byCode = new Map<number, number[]>()
      for (let i = 0; i < rows.length; i++) {
        const code = color.codes[rows[i]!]!
        const bucket = byCode.get(code)
        if (bucket) {
          bucket.push(rows[i]!)
        } else {
          byCode.set(code, [rows[i]!])
        }
      }

      const ordered = [...byCode.keys()].sort((a, b) => {
        const left = a < 0 ? '' : color.levels[a]!
        const right = b < 0 ? '' : color.levels[b]!
        return left < right ? -1 : left > right ? 1 : 0
      })

      for (const code of ordered) {
        const name = code < 0 ? '(none)' : color.levels[code]!
        groups.push(makeGroup(table, Int32Array.from(byCode.get(code)!), name, options, null))
      }
    } else {
      groups.push(makeGroup(table, rows, 'Detections', options, null))
    }
  }

  // The axis box comes from the filters, not from the points in it: a box that
  // re-fitted every frame would make the scene breathe as the slider moves,
  // which is why the Python fixed it with `autorange: False`.
  const ranges = {
    x: padded(widened(axisRange(table, options, 'x'), options, 'x')),
    y: padded(widened(axisRange(table, options, 'y'), options, 'y')),
    z: padded(widened(axisRange(table, options, 'z'), options, 'z'))
  }

  // Over the rows the filters leave, across the whole log: the scale follows
  // a filter change, but not the frame, so a color means the same value as
  // the slider moves. With every row filtered out there is nothing to fit,
  // and the column's own range is a better colorbar than [0, 0].
  const cRange: [number, number] = numeric
    ? rangeOf(table, options.color, mask.includes(1) ? mask : undefined)
    : [0, 1]

  return {
    index: position,
    cType: numeric ? 'numerical' : 'categorical',
    cRange,
    cLabel: label(options.color, options.keys),
    baseSize: 3,
    groups,
    ref: { mesh: null, edges: null, marker: null, name: 'Reference' },
    cloud: null,
    layout: {
      ...EMPTY_LAYOUT,
      ranges,
      aspect: aspectOf(ranges),
      labels: {
        x: label(options.x, options.keys),
        y: label(options.y, options.keys),
        z: label(options.z, options.keys)
      },
      title: options.overlay ? `All frames: ${rows.length} points` : `Index: ${position}`
    }
  }
}

/**
 * Widen an axis to contain the reference.
 *
 * Only when that axis is showing the matching position column: a plot of RCS
 * against range has nothing to do with where the vehicle drove, and widening
 * it by metres of easting would flatten the data to a line.
 */
function widened(
  range: [number, number],
  options: BuildOptions,
  axis: 'x' | 'y' | 'z'
): [number, number] {
  const bounds = options.refBounds?.[axis]
  const position = options.position?.[axis] || DEFAULT_POSITION[axis]
  if (!bounds || options[axis] !== position) {
    return range
  }
  return [Math.min(range[0], bounds[0]), Math.max(range[1], bounds[1])]
}

/**
 * The columns the reference's own x/y/z mean, when the manifest names none.
 *
 * A pose is in the log's position columns by definition, so widening an axis
 * by it only makes sense while that axis is showing one of them.
 */
const DEFAULT_POSITION = { x: 'X', y: 'Y', z: 'Z' } as const

/** The range of one axis: its filter's bounds when it has one, else the data's. */
function axisRange(table: Table, options: BuildOptions, axis: 'x' | 'y' | 'z'): [number, number] {
  const name = options[axis]
  const filter = options.filters.numeric.find((entry) => entry.column === name)
  if (filter && Number.isFinite(filter.min) && Number.isFinite(filter.max)) {
    return [filter.min, filter.max]
  }
  return rangeOf(table, name)
}
