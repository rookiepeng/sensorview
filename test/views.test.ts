// The six analysis views, checked against what the Dash views drew.
//
// The fixture is captured by `scripts/views_golden.py`. Not the whole figure
// dict -- Plotly's defaults are noise, and the port writes traces out by hand
// where Express generated them. What is asserted is the data: how many traces,
// in what order, with how many points each, and the values themselves where a
// port could get them subtly wrong.
//
// Trace order is the load-bearing one. It is the order the colorway is
// assigned in, so getting it wrong recolours every view at once -- and the
// scene with it, since both sort the same way for exactly this reason.

import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

import { readTable } from '../src/data/parquet'
import { buildTable, type Column } from '../src/shared/table'

import {
  heatmapFigure,
  histogramFigure,
  parcatsFigure,
  scatterFigure,
  violinFigure,
  type ViewOptions
} from '../src/renderer/figures/views'

interface Golden {
  table: string
  x: string
  y: string
  categorical: string
  levels: string[]
  rows: number
  numeric: string[]
  scatter: { groups: Array<{ name: string; n: number; firstX: number; firstY: number }> }
  heatmap: {
    shape: [number, number]
    xCenters: number[]
    yCenters: number[]
    zMax: number
    zSum: number
    nonZero: number
  }
  violin: { groups: Array<{ name: string; n: number; min: number; max: number; mean: number }> }
}

const golden = JSON.parse(
  readFileSync(join(__dirname, 'fixtures', 'views.json'), 'utf8')
) as Golden

const raw = readTable(join(__dirname, '..', golden.table))
const table = buildTable(raw.rows, raw.columns as Column[], 'Frame')
const allRows = Int32Array.from({ length: table.rows }, (_, i) => i)

/**
 * A trace as a plain record.
 *
 * `Partial<Data>` is Plotly's discriminated union, which is what makes the
 * builders type-safe -- and what stops a test reading `trace.x` without first
 * narrowing to one of forty trace types. The production code benefits from
 * the union; a test that only looks at what was built does not.
 */
function fields(trace: unknown): Record<string, any> {
  return trace as Record<string, any>
}

function options(overrides: Partial<ViewOptions> = {}): ViewOptions {
  return {
    x: golden.x,
    y: golden.y,
    colour: golden.categorical,
    colormap: 'Portland',
    keys: {},
    theme: 'dark',
    ...overrides
  }
}

describe('scatterFigure', () => {
  it('draws one trace per level, in sorted order', () => {
    const figure = scatterFigure(table, allRows, options())
    expect(figure.data.map((trace) => fields(trace).name)).toEqual(golden.levels)
  })

  it('puts the same points in each trace the Dash view did', () => {
    const figure = scatterFigure(table, allRows, options())
    figure.data.forEach((trace, i) => {
      const expected = golden.scatter.groups[i]!
      const x = fields(trace).x as Float64Array
      const y = fields(trace).y as Float64Array
      expect(x.length).toBe(expected.n)
      expect(x[0]).toBeCloseTo(expected.firstX, 5)
      expect(y[0]).toBeCloseTo(expected.firstY, 5)
    })
  })

  it('is one trace with a colorscale when the colour column is numeric', () => {
    const figure = scatterFigure(table, allRows, options({ colour: 'RCS' }))
    expect(figure.data.length).toBe(1)
    const marker = fields(figure.data[0]).marker as Record<string, unknown>
    expect(marker.colorscale).toBe('Portland')
    expect((marker.color as Float64Array).length).toBe(golden.rows)
  })

  it('still has axes with no rows', () => {
    // An empty figure with no layout is a Plotly error, not a blank plot.
    const figure = scatterFigure(table, new Int32Array(0), options())
    expect(figure.data).toEqual([])
    expect(figure.layout.xaxis).toBeDefined()
  })
})

describe('histogramFigure', () => {
  it('sets bingroup on every trace', () => {
    // R4: without it each colour bins independently, producing bars at
    // different offsets per category -- subtle, wrong, and shippable.
    const figure = histogramFigure(table, allRows, options())
    expect(figure.data.length).toBe(golden.levels.length)
    for (const trace of figure.data) {
      expect(fields(trace).bingroup).toBe('shared')
    }
  })

  it('gives the frame column one bin per frame', () => {
    const figure = histogramFigure(
      table,
      allRows,
      options({ x: 'Frame', colour: 'None' })
    )
    expect(fields(figure.data[0]).nbinsx).toBe(table.frameIds.length)
  })

  it('leaves a continuous column to Plotly', () => {
    const figure = histogramFigure(table, allRows, options({ colour: 'None' }))
    expect(fields(figure.data[0]).nbinsx).toBeUndefined()
    expect(fields(figure.data[0]).histnorm).toBe('probability')
  })
})

describe('heatmapFigure', () => {
  it('is a contour when counts are not log-scaled', () => {
    const figure = heatmapFigure(table, allRows, options())
    expect(fields(figure.data[0]).type).toBe('histogram2dcontour')
  })

  it('bins and log-scales exactly as numpy did', () => {
    const figure = heatmapFigure(table, allRows, options({ logScale: true }))
    const trace = fields(figure.data[0])
    expect(trace.type).toBe('heatmap')

    const z = trace.z as number[][]
    const [rows, cols] = golden.heatmap.shape
    // Plotly wants rows of y, so the grid is transposed out of numpy's
    // (nx, ny) on the way.
    expect(z.length).toBe(rows)
    expect(z[0]!.length).toBe(cols)

    golden.heatmap.xCenters.forEach((value, i) =>
      expect((trace.x as number[])[i]).toBeCloseTo(value, 9)
    )
    golden.heatmap.yCenters.forEach((value, i) =>
      expect((trace.y as number[])[i]).toBeCloseTo(value, 9)
    )

    let sum = 0
    let max = 0
    let nonZero = 0
    for (const row of z) {
      for (const value of row) {
        sum += value
        if (value > max) max = value
        if (value > 0) nonZero++
      }
    }
    expect(sum).toBeCloseTo(golden.heatmap.zSum, 6)
    expect(max).toBeCloseTo(golden.heatmap.zMax, 9)
    expect(nonZero).toBe(golden.heatmap.nonZero)
  })
})

describe('violinFigure', () => {
  it('draws one violin per level with the same samples', () => {
    const figure = violinFigure(table, allRows, options())
    expect(figure.data.map((trace) => fields(trace).name)).toEqual(golden.levels)

    figure.data.forEach((trace, i) => {
      const expected = golden.violin.groups[i]!
      const y = [...(fields(trace).y as Float64Array)].filter((v) => Number.isFinite(v))
      expect(y.length).toBe(expected.n)
      expect(Math.min(...y)).toBeCloseTo(expected.min, 5)
      expect(Math.max(...y)).toBeCloseTo(expected.max, 5)
      expect(y.reduce((a, b) => a + b, 0) / y.length).toBeCloseTo(expected.mean, 5)
    })
  })

  it('shows its box, which is what the Dash view asked for', () => {
    const figure = violinFigure(table, allRows, options())
    expect((fields(figure.data[0]).box as { visible: boolean }).visible).toBe(true)
  })
})

describe('parcatsFigure', () => {
  it('builds a dimension per chosen column', () => {
    const figure = parcatsFigure(
      table,
      allRows,
      options({ dimensions: [golden.categorical, 'Dyn_Prop'], colour: 'None' })
    )
    const dims = fields(figure.data[0]).dimensions as Array<{ label: string; values: unknown[] }>
    expect(dims.length).toBe(2)
    expect(dims[0]!.values.length).toBe(golden.rows)
  })

  it('colours a categorical column by its sorted level index', () => {
    // The trace colours by number and a level has none, so the index has to
    // be the same one the colorway is assigned by everywhere else.
    const figure = parcatsFigure(
      table,
      allRows,
      options({ dimensions: [golden.categorical], colour: golden.categorical })
    )
    const colors = (fields(figure.data[0]).line as { color: number[] }).color
    expect(new Set(colors).size).toBe(golden.levels.length)
    expect(Math.max(...colors)).toBe(golden.levels.length - 1)
  })

  it('has nothing to draw with no dimensions', () => {
    const figure = parcatsFigure(table, allRows, options({ dimensions: [] }))
    expect(figure.data).toEqual([])
  })
})
