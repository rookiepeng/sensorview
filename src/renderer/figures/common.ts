// What every dock view needs from the table.
//
// The views work over the **whole filtered table**, not the frame on the
// slider -- a histogram of one frame's five hundred detections says nothing,
// and the Dash views had the same scope. Filtering 19,756 rows is one pass, so
// the rows are gathered per render rather than cached.

import type { Data, Layout } from 'plotly.js'

import { PALETTE } from '@shared/palette'
import type { ColumnMeta, Table } from '@shared/table'

/** How a column is labelled on an axis, from the manifest. */
export function labelOf(name: string, keys: Record<string, ColumnMeta>): string {
  const meta = keys[name]
  if (!meta) {
    return name
  }
  const described = meta.description || name
  return meta.unit ? `${described} (${meta.unit})` : described
}

/** Whether a column is drawn as a number or as a set of levels. */
export function kindOf(table: Table, name: string): 'number' | 'string' | null {
  return table.columns.get(name)?.kind ?? null
}

/**
 * Numeric values for the rows a mask keeps.
 *
 * Non-finite values are left in. Plotly draws a gap for a null and skips it in
 * a histogram, which is what a missing reading should do -- dropping the row
 * here would unpair it from the other axis.
 */
export function numericValues(table: Table, name: string, rows: Int32Array): Float64Array {
  const column = table.columns.get(name)
  const out = new Float64Array(rows.length)
  if (!column || column.kind !== 'number') {
    return out
  }
  for (let i = 0; i < rows.length; i++) {
    out[i] = column.values[rows[i]!]!
  }
  return out
}

/** Level names for the rows a mask keeps; a null row reads as an empty string. */
export function levelValues(table: Table, name: string, rows: Int32Array): string[] {
  const column = table.columns.get(name)
  const out: string[] = new Array(rows.length)
  if (!column || column.kind !== 'string') {
    return out.fill('')
  }
  for (let i = 0; i < rows.length; i++) {
    const code = column.codes[rows[i]!]!
    out[i] = code >= 0 ? column.levels[code]! : ''
  }
  return out
}

/**
 * Split rows into one group per level of a categorical column, sorted.
 *
 * Sorted because the order is what the colorway is assigned in, so changing it
 * recolors every view at once -- the same rule `buildFrame` follows for the
 * scene, for the same reason.
 */
export function groupByLevel(
  table: Table,
  name: string,
  rows: Int32Array
): Array<{ level: string; rows: Int32Array }> {
  const column = table.columns.get(name)
  if (!column || column.kind !== 'string') {
    return [{ level: '', rows }]
  }

  const byCode = new Map<number, number[]>()
  for (let i = 0; i < rows.length; i++) {
    const code = column.codes[rows[i]!]!
    const bucket = byCode.get(code)
    if (bucket) {
      bucket.push(rows[i]!)
    } else {
      byCode.set(code, [rows[i]!])
    }
  }

  return [...byCode.keys()]
    .sort((a, b) => {
      const left = a < 0 ? '' : column.levels[a]!
      const right = b < 0 ? '' : column.levels[b]!
      return left < right ? -1 : left > right ? 1 : 0
    })
    .map((code) => ({
      level: code < 0 ? '(none)' : column.levels[code]!,
      rows: Int32Array.from(byCode.get(code)!)
    }))
}

/** The rows a mask keeps, as indices. */
export function maskedRows(mask: Uint8Array): Int32Array {
  let kept = 0
  for (let i = 0; i < mask.length; i++) {
    if (mask[i] === 1) {
      kept++
    }
  }
  const rows = new Int32Array(kept)
  let at = 0
  for (let i = 0; i < mask.length; i++) {
    if (mask[i] === 1) {
      rows[at++] = i
    }
  }
  return rows
}

export interface Theme {
  ink: string
  grid: string
}

export function themeOf(mode: 'dark' | 'light'): Theme {
  return mode === 'dark'
    // The same two values as `--sv-border` in each theme: a chart's grid
    // and a panel's rules are the same kind of line, and the charts sit
    // inside the panels.
    ? { ink: '#8a929e', grid: '#1d2b2f' }
    : { ink: '#5e6773', grid: '#dbe4e6' }
}

/**
 * The layout every dock view starts from.
 *
 * `colorway` is Plotly's own, passed explicitly rather than left to the
 * template: the scene reads the same list, and a category colored one way in
 * the view and another in the scene is the bug this prevents.
 */
export function baseLayout(theme: Theme, xLabel: string, yLabel: string) {
  return {
    autosize: true,
    margin: { l: 56, r: 16, t: 10, b: 42 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: theme.ink, size: 10 },
    colorway: PALETTE.colorway,
    showlegend: false,
    xaxis: {
      title: { text: xLabel, font: { size: 10 } },
      gridcolor: theme.grid,
      zerolinecolor: theme.grid
    },
    yaxis: {
      title: { text: yLabel, font: { size: 10 } },
      gridcolor: theme.grid,
      zerolinecolor: theme.grid
    }
  }
}

/**
 * What a built view hands to `PlotlyFigure`.
 *
 * Typed against Plotly's own shapes rather than as loose records: these are
 * figures, and the one thing a loose record buys -- writing a key Plotly does
 * not have -- is the thing worth catching.
 */
export interface Figure {
  data: Array<Partial<Data>>
  layout: Partial<Layout>
}

/** A view with nothing to draw still needs axes, or Plotly reports an error. */
export function emptyFigure(theme: Theme, xLabel = '', yLabel = ''): Figure {
  return { data: [], layout: baseLayout(theme, xLabel, yLabel) }
}
