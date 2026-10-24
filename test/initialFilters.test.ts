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
  levelsOf,
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
  it('opens every declared column but the slider on its full range', () => {
    const table = makeTable([FRAME, X, SENSOR])
    const filters = initialFilters(table, KEYS)
    // Filtering the frame column would hide frames rather than points.
    expect(filters.numeric).toEqual([{ column: 'X', min: 1, max: 4 }])
    expect(filters.categorical).toEqual([{ column: 'Sensor', allowed: ['front', 'rear'] }])
    expect([...filterAll(table, filters)]).toEqual([1, 1, 1, 1])
  })

  it('skips a declared column the table does not have', () => {
    expect(initialFilters(makeTable([FRAME, X]), KEYS).categorical).toEqual([])
  })

  it('drops a row with no value in a declared column', () => {
    // A slider at the full range still excludes NaN, as in the app this
    // replaces.
    const gappy: Column = { name: 'X', kind: 'number', values: Float64Array.from([1, NaN, 3, 4]) }
    const table = makeTable([FRAME, gappy, SENSOR])
    expect([...filterAll(table, initialFilters(table, KEYS))]).toEqual([1, 0, 1, 1])
  })

  it('treats a column stored as text as categorical whatever the manifest says', () => {
    // A range over level codes would compare meaningless numbers.
    const filters = initialFilters(makeTable([FRAME, X, SENSOR]), { ...KEYS, Sensor: { type: 'numerical' } })
    expect(filters.numeric.map((entry) => entry.column)).toEqual(['X'])
    expect(filters.categorical[0]!.column).toBe('Sensor')
  })

  it('gives an all-NaN column a degenerate range rather than failing', () => {
    const empty: Column = { name: 'X', kind: 'number', values: new Float64Array(4).fill(NaN) }
    expect(initialFilters(makeTable([FRAME, empty]), KEYS).numeric[0]).toEqual({
      column: 'X',
      min: 0,
      max: 0
    })
  })
})

describe('a categorical column stored as numbers', () => {
  const BISTATIC: Column = {
    name: 'Bistatic',
    kind: 'number',
    values: Float64Array.from([1, 0, NaN, 1])
  }
  const keys: Record<string, ColumnMeta> = { ...KEYS, Bistatic: { type: 'categorical' } }

  it('gets chips, one per distinct value, and filters by them', () => {
    const table = makeTable([FRAME, X, BISTATIC])
    const filters = initialFilters(table, keys)
    expect(filters.numeric.map((entry) => entry.column)).toEqual(['X'])
    expect(filters.categorical).toEqual([{ column: 'Bistatic', allowed: ['0', '1'] }])
    expect(levelsOf(table, 'Bistatic')).toEqual(['0', '1'])

    filters.categorical = [{ column: 'Bistatic', allowed: ['1'] }]
    expect([...filterAll(table, filters)]).toEqual([1, 0, 0, 1])
  })

  it('keeps a slider when there are too many values, or none', () => {
    const many = buildTable(
      100,
      [
        { name: 'Frame', kind: 'number', values: new Float64Array(100) },
        { name: 'Bistatic', kind: 'number', values: Float64Array.from({ length: 100 }, (_, i) => i) }
      ],
      'Frame'
    )
    const filters = initialFilters(many, { Bistatic: { type: 'categorical' } })
    expect(filters.categorical).toEqual([])
    expect(filters.numeric.map((entry) => entry.column)).toEqual(['Bistatic'])

    const empty: Column = { name: 'Bistatic', kind: 'number', values: new Float64Array(4).fill(NaN) }
    expect(initialFilters(makeTable([FRAME, empty]), keys).categorical).toEqual([])
  })
})
