// Drawing fewer points than there are, and selecting against all of them.
//
// The dock's scatter is SVG: one DOM node per point. A scatter of every frame
// of a combined case is hundreds of thousands of rows, which is ten seconds
// to draw and as long again for every redraw a hide causes. Most of those
// points land on a pixel some other point already covers, so the scatter
// draws one point per small cell of the plot instead -- the picture is the
// same, the node count is bounded.
//
// That makes the drawn points a sample, so a selection cannot be "the points
// Plotly says it enclosed": that would hide only the sample. The region the
// user drew is taken instead, and tested against every row.

import type { Table } from './table'

/** Cells across and down. One drawn point per cell, so at most their product. */
export const THIN_GRID = { x: 200, y: 120 }

/** Fewer rows than this are drawn as they are. */
export const THIN_ABOVE = 20_000

/** A box, from Plotly's `range`: `[min, max]` on each axis, in data units. */
export interface BoxRegion {
  kind: 'box'
  x: [number, number]
  y: [number, number]
}

/** A lasso, from Plotly's `lassoPoints`: the polygon's vertices, in data units. */
export interface LassoRegion {
  kind: 'lasso'
  x: number[]
  y: number[]
}

export type Region = BoxRegion | LassoRegion

function valuesOf(table: Table, name: string): Float64Array | null {
  const column = table.columns.get(name)
  return column && column.kind === 'number' ? column.values : null
}

/**
 * One row per occupied cell of a grid over the plot.
 *
 * The grid covers `view` when one is given -- the axes as the user has zoomed
 * them -- and the rows' own extent otherwise. Rows outside the view are left
 * out, which is what lets a zoom draw the detail inside it at the same cost.
 * Rows with no x or y value are left out too; Plotly would not draw them.
 *
 * Rows keep their order, and the first row to reach a cell is the one drawn.
 *
 * @param table The table.
 * @param rows The candidate rows.
 * @param x Column on the horizontal axis.
 * @param y Column on the vertical axis.
 * @param view `{x: [lo, hi], y: [lo, hi]}` to thin within, or null.
 * @returns The rows to draw. `rows` itself when it is under `THIN_ABOVE`.
 */
export function thinRows(
  table: Table,
  rows: Int32Array,
  x: string,
  y: string,
  view: { x: [number, number]; y: [number, number] } | null = null,
  grid = THIN_GRID
): Int32Array {
  if (rows.length <= THIN_ABOVE) {
    return rows
  }
  const xs = valuesOf(table, x)
  const ys = valuesOf(table, y)
  if (!xs || !ys) {
    return rows
  }

  let [x0, x1] = view ? view.x : [Infinity, -Infinity]
  let [y0, y1] = view ? view.y : [Infinity, -Infinity]
  if (!view) {
    for (let i = 0; i < rows.length; i++) {
      const vx = xs[rows[i]!]!
      const vy = ys[rows[i]!]!
      if (Number.isFinite(vx) && Number.isFinite(vy)) {
        if (vx < x0) x0 = vx
        if (vx > x1) x1 = vx
        if (vy < y0) y0 = vy
        if (vy > y1) y1 = vy
      }
    }
  }
  if (!(x0 <= x1) || !(y0 <= y1)) {
    return new Int32Array(0)
  }
  // A degenerate axis -- every row with the same x -- is one column of cells.
  const sx = x1 > x0 ? grid.x / (x1 - x0) : 0
  const sy = y1 > y0 ? grid.y / (y1 - y0) : 0

  const taken = new Uint8Array(grid.x * grid.y)
  const kept = new Int32Array(Math.min(rows.length, grid.x * grid.y))
  let n = 0
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i]!
    const vx = xs[row]!
    const vy = ys[row]!
    if (!(vx >= x0 && vx <= x1 && vy >= y0 && vy <= y1)) {
      continue
    }
    const cx = Math.min(grid.x - 1, Math.floor((vx - x0) * sx))
    const cy = Math.min(grid.y - 1, Math.floor((vy - y0) * sy))
    const cell = cy * grid.x + cx
    if (taken[cell] === 0) {
      taken[cell] = 1
      kept[n++] = row
    }
  }
  return kept.slice(0, n)
}

/** Whether a point is inside a polygon, by counting edge crossings. */
function inPolygon(px: number, py: number, xs: number[], ys: number[]): boolean {
  let inside = false
  for (let i = 0, j = xs.length - 1; i < xs.length; j = i++) {
    const xi = xs[i]!
    const yi = ys[i]!
    const xj = xs[j]!
    const yj = ys[j]!
    if (yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) {
      inside = !inside
    }
  }
  return inside
}

/**
 * Every row inside any of the regions.
 *
 * @param table The table.
 * @param rows The rows the plot is of -- all of them, not the drawn sample.
 * @param x Column on the horizontal axis.
 * @param y Column on the vertical axis.
 * @param regions What the user drew. Several when shift added to a selection.
 * @returns The enclosed rows, in `rows` order.
 */
export function rowsInRegions(
  table: Table,
  rows: Int32Array,
  x: string,
  y: string,
  regions: Region[]
): number[] {
  const xs = valuesOf(table, x)
  const ys = valuesOf(table, y)
  if (!xs || !ys || regions.length === 0) {
    return []
  }
  // A lasso's bounding box first: most rows are outside it, and that test is
  // four comparisons where the polygon's is a pass over every edge.
  const bounds = regions.map((region) =>
    region.kind === 'box'
      ? { x: region.x, y: region.y }
      : {
          x: [Math.min(...region.x), Math.max(...region.x)] as [number, number],
          y: [Math.min(...region.y), Math.max(...region.y)] as [number, number]
        }
  )

  const out: number[] = []
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i]!
    const vx = xs[row]!
    const vy = ys[row]!
    for (let r = 0; r < regions.length; r++) {
      const box = bounds[r]!
      if (!(vx >= box.x[0] && vx <= box.x[1] && vy >= box.y[0] && vy <= box.y[1])) {
        continue
      }
      const region = regions[r]!
      if (region.kind === 'box' || inPolygon(vx, vy, region.x, region.y)) {
        out.push(row)
        break
      }
    }
  }
  return out
}

/**
 * The regions a `plotly_selected` event describes.
 *
 * `selections` is every shape drawn so far -- more than one when shift added
 * to the selection -- and is preferred when it has them. `range` and
 * `lassoPoints` describe only the latest, and are the fallback.
 *
 * @returns The regions, or null when the event carries none (a deselect, or
 *     a click-select of single points, which the points themselves answer).
 */
export function regionsOfEvent(event: unknown): Region[] | null {
  const e = (event ?? {}) as {
    selections?: { type?: string; x0?: unknown; x1?: unknown; y0?: unknown; y1?: unknown; path?: string }[]
    range?: Record<string, [number, number]>
    lassoPoints?: Record<string, number[]>
  }

  const regions: Region[] = []
  for (const shape of e.selections ?? []) {
    if (shape.type === 'rect') {
      const xa = Number(shape.x0)
      const xb = Number(shape.x1)
      const ya = Number(shape.y0)
      const yb = Number(shape.y1)
      if ([xa, xb, ya, yb].every(Number.isFinite)) {
        regions.push({
          kind: 'box',
          x: [Math.min(xa, xb), Math.max(xa, xb)],
          y: [Math.min(ya, yb), Math.max(ya, yb)]
        })
      }
    } else if (shape.type === 'path' && typeof shape.path === 'string') {
      const lasso = parsePath(shape.path)
      if (lasso) {
        regions.push(lasso)
      }
    }
  }
  if (regions.length > 0) {
    return regions
  }

  if (e.range?.x && e.range?.y) {
    return [{ kind: 'box', x: e.range.x, y: e.range.y }]
  }
  if (e.lassoPoints?.x && e.lassoPoints?.y) {
    return [{ kind: 'lasso', x: e.lassoPoints.x.map(Number), y: e.lassoPoints.y.map(Number) }]
  }
  return null
}

/** `M1,2L3,4L5,6Z` -> a lasso, or null when it is not one. */
function parsePath(path: string): LassoRegion | null {
  const xs: number[] = []
  const ys: number[] = []
  for (const part of path.split(/[MLZ]/i)) {
    const trimmed = part.trim()
    if (!trimmed) {
      continue
    }
    const [a, b] = trimmed.split(',').map(Number)
    if (!Number.isFinite(a) || !Number.isFinite(b)) {
      return null
    }
    xs.push(a!)
    ys.push(b!)
  }
  return xs.length >= 3 ? { kind: 'lasso', x: xs, y: ys } : null
}
