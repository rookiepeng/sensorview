// numpy's histogram machinery, checked against numpy.
//
// The fixture was captured from numpy (see `fixtures/README.md`) on the real
// table. Every numeric column is binned, because the estimator's branches are
// chosen by the data: a tight interquartile range takes the sqrt floor, a
// small sample takes Sturges, and a constant column takes neither.

import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

import { readTable } from '../src/data/parquet'

import {
  histogram2d,
  histogramBinEdges,
  linspace,
  outerEdges,
  percentile
} from '../src/shared/histogram'

interface Golden {
  cases: Array<{
    column: string
    n: number
    bins: number
    edges: number[]
    p25: number
    p75: number
  }>
  synthetic: Array<{ label: string; values: number[]; n: number; bins: number; edges: number[] }>
  hist2d: {
    shape: [number, number]
    total: number
    rowSums: number[]
    colSums: number[]
    max: number
  }
}

const golden = JSON.parse(
  readFileSync(join(__dirname, 'fixtures', 'histogram.json'), 'utf8')
) as Golden

describe('percentile', () => {
  it('interpolates linearly, as numpy does by default', () => {
    const data = Float64Array.from([1, 2, 3, 4])
    // Virtual index 1.5 between 2 and 3.
    expect(percentile(data, 50)).toBeCloseTo(2.5, 12)
    expect(percentile(data, 0)).toBe(1)
    expect(percentile(data, 100)).toBe(4)
  })

  it('is the value itself for one sample', () => {
    expect(percentile(Float64Array.from([9]), 25)).toBe(9)
  })
})

describe('outerEdges', () => {
  it('widens a constant column by half either way', () => {
    // Otherwise the bin width divides by zero.
    expect(outerEdges(Float64Array.from([5, 5, 5]))).toEqual([4.5, 5.5])
  })

  it('is 0..1 for nothing at all', () => {
    expect(outerEdges(new Float64Array(0))).toEqual([0, 1])
  })
})

describe('linspace', () => {
  it('lands exactly on the stop value', () => {
    // `start + i * step` drifts, and an edge that misses the maximum by an
    // ulp drops the largest sample out of the histogram.
    const out = linspace(0, 1, 11)
    expect(out[10]).toBe(1)
    expect(out.length).toBe(11)
  })
})

describe('histogramBinEdges', () => {
  for (const expected of golden.cases) {
    it(`matches numpy on ${expected.column}`, () => {
      const edges = histogramBinEdges(valuesFor(expected.column))
      expect(edges.length - 1).toBe(expected.bins)
      expected.edges.forEach((value, i) => expect(edges[i]).toBeCloseTo(value, 9))
    })
  }

  for (const expected of golden.synthetic) {
    it(`matches numpy for ${expected.label}`, () => {
      const values = Float64Array.from(rebuild(expected))
      const edges = histogramBinEdges(values)
      expect(edges.length - 1).toBe(expected.bins)
      expected.edges.forEach((value, i) => expect(edges[i]).toBeCloseTo(value, 9))
    })
  }
})

describe('histogram2d', () => {
  it('counts the same grid numpy counts', () => {
    const x = valuesFor('X')
    const y = valuesFor('Y')
    const xEdges = histogramBinEdges(x)
    const yEdges = histogramBinEdges(y)
    const counts = histogram2d(x, y, xEdges, yEdges)

    const [nx, ny] = golden.hist2d.shape
    expect(xEdges.length - 1).toBe(nx)
    expect(yEdges.length - 1).toBe(ny)

    let total = 0
    const rowSums = new Array(nx).fill(0)
    const colSums = new Array(ny).fill(0)
    for (let bx = 0; bx < nx; bx++) {
      for (let by = 0; by < ny; by++) {
        const value = counts[bx * ny + by]!
        total += value
        rowSums[bx] += value
        colSums[by] += value
      }
    }

    // Every sample landed in a bin: the top bin has to include its right
    // edge, or the maximum falls outside the grid.
    expect(total).toBe(golden.hist2d.total)
    expect(rowSums).toEqual(golden.hist2d.rowSums)
    expect(colSums).toEqual(golden.hist2d.colSums)
  })
})

/** Read one column of the real table back out of the fixture's own source. */
function valuesFor(column: string): Float64Array {
  // Read through the same reader the app uses, so this checks the whole path
  // rather than a copy of the numbers.
  const table = readTable(join(__dirname, '..', 'data/NuScenes/scene_0061.parquet'), [column])
  const found = table.columns.find((entry) => entry.name === column)
  const raw = found?.values ?? new Float64Array(0)
  return Float64Array.from([...raw].filter((value) => Number.isFinite(value)))
}

/** Rebuild a synthetic case from its label; the fixture carries only a head. */
function rebuild(expected: Golden['synthetic'][number]): number[] {
  switch (expected.label) {
    case 'all identical':
      return new Array(expected.n).fill(expected.values[0]!)
    case 'integers':
      return Array.from({ length: expected.n }, (_, i) => i)
    case 'tight iqr':
      return [...new Array(expected.n - 1).fill(0), 1000]
    default:
      return expected.values
  }
}
