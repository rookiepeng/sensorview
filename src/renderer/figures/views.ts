// The six analysis views, as pure functions.
//
// Each takes the filtered rows and returns a Plotly figure. Pure on purpose:
// a figure is the one thing in this app that is worth a golden test, and a
// function that reaches into a store cannot have one.
//
// These are transliterations of `viz/viz.py` and the six `view_callbacks/*`
// modules. Where the Python leaned on Plotly Express, the trace it produced is
// written out -- Express is a figure generator, not a renderer, and its output
// is what matters.

import { histogram2d, histogramBinEdges } from '@shared/histogram'
import type { ColumnMeta, Table } from '@shared/table'

import {
  baseLayout,
  emptyFigure,
  groupByLevel,
  kindOf,
  labelOf,
  levelValues,
  numericValues,
  themeOf,
  type Figure
} from './common'

export type ViewId = 'scatter' | 'histogram' | 'heatmap' | 'violin' | 'parcats'

export interface ViewOptions {
  x: string
  y: string
  color: string
  /** Extra columns, for the views that take a set rather than a pair. */
  dimensions?: string[]
  colormap: string
  keys: Record<string, ColumnMeta>
  theme: 'dark' | 'light'
  /** Histogram normalisation: Plotly's `histnorm`. */
  histnorm?: 'probability' | 'density'
  /** Heatmap: log1p the counts and draw a heatmap rather than a contour. */
  logScale?: boolean
}

/* ─────────────────────────────────────────────────────────── scatter ─── */

/**
 * 2D scatter, colored by a third column.
 *
 * SVG `scatter`, not the `scattergl` the Dash view used. Plotly's WebGL path
 * replaces the plot with "WebGL is not supported by your browser" in this
 * Electron renderer, and it is not for want of a GPU: the context is granted
 * (an RTX 3050, every extension regl asks for present), three canvases are
 * created at full size, and the three.js scene is drawing in the same window
 * at the same time. regl refuses for a reason it does not report, in the
 * assembled bundle and in Plotly's own dist alike.
 *
 * So the dock draws the trace that works. At this table's twenty thousand
 * points SVG is fine; a much larger log would want the gl path back, and the
 * smoke run times this draw so the day that stops being true is visible.
 */
export function scatterFigure(table: Table, rows: Int32Array, options: ViewOptions): Figure {
  const theme = themeOf(options.theme)
  const xLabel = labelOf(options.x, options.keys)
  const yLabel = labelOf(options.y, options.keys)
  if (rows.length === 0) {
    return emptyFigure(theme, xLabel, yLabel)
  }

  const layout = { ...baseLayout(theme, xLabel, yLabel) }
  const marker = { size: 6, opacity: 0.8, line: { color: '#FFFFFF', width: 0 } }
  if (kindOf(table, options.color) === 'number') {
    return {
      data: [
        {
          type: 'scatter',
          mode: 'markers',
          x: numericValues(table, options.x, rows),
          y: numericValues(table, options.y, rows),
          // The table row behind each point, so a lasso can say which rows it
          // enclosed. Without it a selection is a set of positions within a
          // trace and means nothing outside this figure.
          customdata: Array.from(rows),
          marker: {
            ...marker,
            color: numericValues(table, options.color, rows),
            colorscale: options.colormap,
            colorbar: {
              title: { text: labelOf(options.color, options.keys), side: 'right' },
              thickness: 10
            }
          }
        }
      ],
      layout
    }
  }

  // One trace per level, which is also what puts them in the legend.
  return {
    data: groupByLevel(table, options.color, rows).map((group) => ({
      type: 'scatter',
      mode: 'markers',
      name: group.level,
      x: numericValues(table, options.x, group.rows),
      y: numericValues(table, options.y, group.rows),
      customdata: Array.from(group.rows),
      marker
    })),
    layout: { ...layout, showlegend: true }
  }
}

/* ───────────────────────────────────────────────────────── histogram ─── */

/**
 * A histogram of one column, optionally split by a category.
 *
 * `bingroup` is set on every trace, which is R4 in the plan and not optional:
 * Plotly Express sets it automatically, and hand-built traces that omit it bin
 * each color independently, producing bars at different offsets per category.
 * Visually subtle, numerically wrong, and exactly the kind of thing that
 * ships.
 */
export function histogramFigure(table: Table, rows: Int32Array, options: ViewOptions): Figure {
  const theme = themeOf(options.theme)
  const xLabel = labelOf(options.x, options.keys)
  const yLabel = options.histnorm === 'density' ? 'Density' : 'Probability'
  if (rows.length === 0) {
    return emptyFigure(theme, xLabel, yLabel)
  }

  const common = {
    // `as const` throughout: Plotly discriminates its trace union on `type`,
    // so a widened `string` matches none of them.
    type: 'histogram' as const,
    histnorm: options.histnorm ?? 'probability',
    opacity: 1,
    bingroup: 'shared'
  }

  // The frame column is discrete, so it gets one bin per value rather than
  // whatever a continuous estimator would choose.
  const nbins =
    options.x === table.frameKey ? { nbinsx: table.frameIds.length } : {}

  const layout = {
    ...baseLayout(theme, xLabel, yLabel),
    barmode: 'group' as const
  }

  if (!options.color || options.color === 'None') {
    return {
      data: [{ ...common, ...nbins, x: numericValues(table, options.x, rows) }],
      layout
    }
  }

  return {
    data: groupByLevel(table, options.color, rows).map((group) => ({
      ...common,
      ...nbins,
      name: group.level,
      x: numericValues(table, options.x, group.rows)
    })),
    layout: { ...layout, showlegend: true }
  }
}

/* ─────────────────────────────────────────────────────────── heatmap ─── */

/**
 * A 2D density, as a contour or as a log-scaled count grid.
 *
 * The log path bins here rather than in Plotly, because `log1p` has to be
 * applied to counts and Plotly has no way to express that -- which is why
 * numpy's binning had to be ported at all.
 */
export function heatmapFigure(table: Table, rows: Int32Array, options: ViewOptions): Figure {
  const theme = themeOf(options.theme)
  const xLabel = labelOf(options.x, options.keys)
  const yLabel = labelOf(options.y, options.keys)
  const layout = baseLayout(theme, xLabel, yLabel)
  if (rows.length === 0) {
    return emptyFigure(theme, xLabel, yLabel)
  }

  if (!options.logScale) {
    return {
      data: [
        {
          type: 'histogram2dcontour',
          x: numericValues(table, options.x, rows),
          y: numericValues(table, options.y, rows),
          colorscale: options.colormap,
          colorbar: { thickness: 10 }
        }
      ],
      layout
    }
  }

  // Paired, so a row missing either value is out of both -- the Python
  // dropped each column's NaN separately, which silently mismatched the two
  // axes whenever they had gaps in different rows. Pairing them is the same
  // answer whenever the gaps line up, and a correct one when they do not.
  const xs = numericValues(table, options.x, rows)
  const ys = numericValues(table, options.y, rows)
  let kept = 0
  for (let i = 0; i < xs.length; i++) {
    if (Number.isFinite(xs[i]!) && Number.isFinite(ys[i]!)) {
      xs[kept] = xs[i]!
      ys[kept] = ys[i]!
      kept++
    }
  }
  const x = xs.subarray(0, kept)
  const y = ys.subarray(0, kept)
  if (kept === 0) {
    return emptyFigure(theme, xLabel, yLabel)
  }

  const xEdges = histogramBinEdges(x)
  const yEdges = histogramBinEdges(y)
  const counts = histogram2d(x, y, xEdges, yEdges)
  const nx = xEdges.length - 1
  const ny = yEdges.length - 1

  // Plotly wants z as rows of y, so the grid is transposed on the way out --
  // numpy's histogram2d is (nx, ny).
  const z: number[][] = []
  for (let by = 0; by < ny; by++) {
    const row = new Array<number>(nx)
    for (let bx = 0; bx < nx; bx++) {
      row[bx] = Math.log1p(counts[bx * ny + by]!)
    }
    z.push(row)
  }

  return {
    data: [
      {
        type: 'heatmap',
        x: centers(xEdges),
        y: centers(yEdges),
        z,
        colorscale: options.colormap,
        colorbar: { title: { text: 'log(count+1)' }, thickness: 10 }
      }
    ],
    layout
  }
}

function centers(edges: Float64Array): number[] {
  const out: number[] = []
  for (let i = 0; i + 1 < edges.length; i++) {
    out.push((edges[i]! + edges[i + 1]!) / 2)
  }
  return out
}

/* ──────────────────────────────────────────────────────────── violin ─── */

/** A violin per category, with its box, optionally split again by color. */
export function violinFigure(table: Table, rows: Int32Array, options: ViewOptions): Figure {
  const theme = themeOf(options.theme)
  const xLabel = labelOf(options.x, options.keys)
  const yLabel = labelOf(options.y, options.keys)
  if (rows.length === 0) {
    return emptyFigure(theme, xLabel, yLabel)
  }

  const layout = {
    ...baseLayout(theme, xLabel, yLabel),
    violinmode: 'group' as const
  }

  const common = {
    type: 'violin' as const,
    box: { visible: true },
    meanline: { visible: false },
    points: false as const
  }

  if (!options.color || options.color === 'None') {
    return {
      data: [
        {
          ...common,
          x: levelValues(table, options.x, rows),
          y: numericValues(table, options.y, rows)
        }
      ],
      layout
    }
  }

  return {
    data: groupByLevel(table, options.color, rows).map((group) => ({
      ...common,
      name: group.level,
      x: levelValues(table, options.x, group.rows),
      y: numericValues(table, options.y, group.rows)
    })),
    layout: { ...layout, showlegend: true }
  }
}

/* ─────────────────────────────────────────────────────────── parcats ─── */

/**
 * Parallel categories across however many dimensions are chosen.
 *
 * Ribbons colored by a numeric column directly; by a categorical one through
 * its level index, since the trace colors by number and a level has none.
 */
export function parcatsFigure(table: Table, rows: Int32Array, options: ViewOptions): Figure {
  const theme = themeOf(options.theme)
  const dimensions = (options.dimensions ?? []).filter((name) => table.columns.has(name))
  if (rows.length === 0 || dimensions.length === 0) {
    return emptyFigure(theme)
  }

  const dims = dimensions.map((name) => ({
    label: labelOf(name, options.keys),
    values:
      kindOf(table, name) === 'string'
        ? levelValues(table, name, rows)
        : Array.from(numericValues(table, name, rows))
  }))

  const trace: Record<string, unknown> = {
    type: 'parcats',
    dimensions: dims,
    arrangement: 'freeform',
    hoverinfo: 'count+probability'
  }

  if (options.color && options.color !== 'None') {
    if (kindOf(table, options.color) === 'number') {
      trace.line = {
        color: numericValues(table, options.color, rows),
        colorscale: options.colormap,
        colorbar: { title: { text: labelOf(options.color, options.keys) }, thickness: 10 }
      }
      trace.hoveron = 'color'
    } else {
      // The level's position in sorted order, which is the same index the
      // colorway is assigned by everywhere else.
      const order = new Map(
        groupByLevel(table, options.color, rows).map((group, index) => [group.level, index])
      )
      const levels = levelValues(table, options.color, rows)
      trace.line = {
        color: levels.map((level) => order.get(level || '(none)') ?? 0),
        colorscale: options.colormap
      }
    }
  }

  const { xaxis: _x, yaxis: _y, ...layout } = baseLayout(theme, '', '')
  return { data: [trace], layout: { ...layout, margin: { l: 60, r: 60, t: 24, b: 24 } } }
}

/* ────────────────────────────────────────────────────────────── table ─── */

const BUILDERS: Record<ViewId, (t: Table, r: Int32Array, o: ViewOptions) => Figure> = {
  scatter: scatterFigure,
  histogram: histogramFigure,
  heatmap: heatmapFigure,
  violin: violinFigure,
  parcats: parcatsFigure
}

export function buildView(
  id: ViewId,
  table: Table,
  rows: Int32Array,
  options: ViewOptions
): Figure {
  return BUILDERS[id](table, rows, options)
}

export const VIEW_LABELS: Record<ViewId, string> = {
  scatter: 'Scatter',
  histogram: 'Histogram',
  heatmap: 'Heatmap',
  violin: 'Violin',
  parcats: 'Parallel categories'
}
