// The filters a log opens on.
//
// The rail generates its controls from this, so what it returns decides what
// the user sees as much as what passes -- a column missing here has no control
// and silently cannot be filtered.

import { describe, expect, it } from 'vitest'

import {
  buildTable,
  filterAll,
  initialFilters,
  type Column,
  type ColumnMeta
} from '../src/shared/table'

function makeTable(columns: Column[]) {
  const rows = columns[0]!.kind === 'number' ? columns[0]!.values.length : 0
  return buildTable(rows, columns, 'Frame')
}

const FRAME: Column = { name: 'Frame', kind: 'number', values: Float64Array.from([0, 0, 1, 1]) }
const X: Column = { name: 'X', kind: 'number', values: Float64Array.from([1, 2, 3, 4]) }
const SENSOR: Column = {
  name: 'Sensor',
  kind: 'string',
  codes: Int32Array.from([0, 1, 0, 1]),
  levels: ['front', 'rear']
}

const KEYS: Record<string, ColumnMeta> = {
  Frame: { type: 'numerical' },
  X: { type: 'numerical' },
  Sensor: { type: 'categorical' }
}

describe('initialFilters', () => {
  it('gives every declared column a filter', () => {
    const filters = initialFilters(makeTable([FRAME, X, SENSOR]), KEYS)

    expect(filters.numeric.map((entry) => entry.column)).toEqual(['X'])
    expect(filters.categorical.map((entry) => entry.column)).toEqual(['Sensor'])
  })

  it('leaves the slider column out', () => {
    const filters = initialFilters(makeTable([FRAME, X, SENSOR]), KEYS)

    // Filtering the frame column would hide frames rather than points.
    expect(filters.numeric.some((entry) => entry.column === 'Frame')).toBe(false)
  })

  it('skips a declared column the table does not have', () => {
    const filters = initialFilters(makeTable([FRAME, X]), KEYS)

    expect(filters.categorical).toEqual([])
  })

  it('opens on the data range, with every level allowed', () => {
    const filters = initialFilters(makeTable([FRAME, X, SENSOR]), KEYS)

    expect(filters.numeric[0]).toEqual({ column: 'X', min: 1, max: 4 })
    expect(filters.categorical[0]!.allowed).toEqual(['front', 'rear'])
  })

  it('passes every row that has a value', () => {
    const table = makeTable([FRAME, X, SENSOR])
    const mask = filterAll(table, initialFilters(table, KEYS))

    expect([...mask]).toEqual([1, 1, 1, 1])
  })

  it('drops a row with no value in a declared column', () => {
    // Not an oversight: a slider sitting at the full range still excludes NaN,
    // and every numeric column had a slider in the app this replaces.
    const gappy: Column = { name: 'X', kind: 'number', values: Float64Array.from([1, NaN, 3, 4]) }
    const table = makeTable([FRAME, gappy, SENSOR])
    const mask = filterAll(table, initialFilters(table, KEYS))

    expect([...mask]).toEqual([1, 0, 1, 1])
  })

  it('treats a column stored as text as categorical whatever the manifest says', () => {
    const table = makeTable([FRAME, X, SENSOR])
    const filters = initialFilters(table, { ...KEYS, Sensor: { type: 'numerical' } })

    // A range filter over level codes would compare meaningless numbers.
    expect(filters.numeric.some((entry) => entry.column === 'Sensor')).toBe(false)
    expect(filters.categorical[0]!.column).toBe('Sensor')
  })

  it('gives an all-NaN column a degenerate range rather than failing', () => {
    const empty: Column = {
      name: 'X',
      kind: 'number',
      values: Float64Array.from([NaN, NaN, NaN, NaN])
    }
    const filters = initialFilters(makeTable([FRAME, empty]), KEYS)

    expect(filters.numeric[0]).toEqual({ column: 'X', min: 0, max: 0 })
  })
})
