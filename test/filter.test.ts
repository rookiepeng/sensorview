// The filter agrees with the Python, over the real table.
//
// `filterAll` runs on every filter change, and a row that should have dropped
// out and did not is a point drawn that the user filtered away. The fixture
// (`fixtures/filters.json`) holds seeded cases over `scene_0061.parquet`,
// including the edge cases, with the expected rows as a base64 bitmask.

import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { beforeAll, describe, expect, it } from 'vitest'

import { readTable } from '../src/data/parquet'
import {
  buildTable,
  clampFrameIndex,
  filterAll,
  frameRows,
  rangeOf,
  visibleRows,
  type Column,
  type FilterState,
  type Table,
  type Visibility
} from '../src/shared/table'

interface Case {
  label: string
  numeric: Array<{ column: string; min: number; max: number }>
  categorical: Array<{ column: string; allowed: string[] }>
  visible: Visibility[] | null
  kept_count: number
  /** One bit per row, LSB first, base64. */
  kept_bits: string
}

interface Fixture {
  table: string
  rows: number
  hidden_every: number
  cases: Case[]
}

const fixture: Fixture = JSON.parse(
  readFileSync(join(__dirname, 'fixtures', 'filters.json'), 'utf8')
)

/** Unpack a base64 bitmask, LSB first, into a mask one byte per row. */
function unpackMask(bits: string, rows: number): Uint8Array {
  const packed = Buffer.from(bits, 'base64')
  const mask = new Uint8Array(rows)
  for (let row = 0; row < rows; row++) {
    mask[row] = (packed[row >> 3]! >> (row & 7)) & 1
  }
  return mask
}

let table: Table

beforeAll(() => {
  const root = join(__dirname, '..')
  const data = readTable(join(root, fixture.table))
  table = buildTable(data.rows, data.columns as Column[], 'Frame')

  // The same deterministic scatter the generator used.
  for (let row = 0; row < table.rows; row++) {
    table.visible[row] = row % fixture.hidden_every === 0 ? 1 : 0
  }
})

describe('the reader and the Python agree about the table', () => {
  it('reads every row into one ascending frame index', () => {
    expect(table.rows).toBe(fixture.rows)
    expect(table.frameStart[table.frameIds.length]).toBe(table.rows)
    expect(new Set(table.rowOrder).size).toBe(table.rows)
    for (let i = 1; i < table.frameIds.length; i++) {
      expect(table.frameIds[i]!).toBeGreaterThan(table.frameIds[i - 1]!)
    }
  })
})

describe('filterAll matches Python', () => {
  it.each(fixture.cases.map((c, i) => [i, c.label, c] as const))(
    'case %i: %s',
    (_index, _label, testCase) => {
      const filters: FilterState = {
        numeric: testCase.numeric,
        categorical: testCase.categorical,
        ...(testCase.visible === null ? {} : { visible: testCase.visible })
      }
      const mask = filterAll(table, filters)
      const expected = unpackMask(testCase.kept_bits, table.rows)

      // The count first, because it is the readable failure.
      expect(mask.reduce((total, bit) => total + bit, 0)).toBe(testCase.kept_count)
      const differing: number[] = []
      for (let row = 0; row < table.rows && differing.length < 10; row++) {
        if (mask[row] !== expected[row]) {
          differing.push(row)
        }
      }
      expect(differing).toEqual([])
    }
  )
})

describe('frameRows', () => {
  it('slices each frame and covers every row', () => {
    const frameColumn = table.columns.get('Frame') as { values: Float64Array }
    for (const row of frameRows(table, 0)) {
      expect(frameColumn.values[row]).toBe(table.frameIds[0])
    }
    let total = 0
    for (let i = 0; i < table.frameIds.length; i++) {
      total += frameRows(table, i).length
    }
    expect(total).toBe(table.rows)
  })

  it('returns nothing for a position out of range', () => {
    expect(frameRows(table, table.frameIds.length).length).toBe(0)
    expect(frameRows(table, -1).length).toBe(0)
  })
})

it('visibleRows intersects a frame with a mask, in frame order', () => {
  const mask = filterAll(table, { numeric: [], categorical: [], visible: ['visible'] })
  const all = frameRows(table, 3)
  expect(Array.from(visibleRows(table, 3, mask))).toEqual(
    Array.from(all).filter((row) => mask[row] === 1)
  )
})

it.each([
  [0, 5, null],
  [10, 99, 9],
  [10, -3, 0],
  [10, null, 0]
])('clampFrameIndex(%j, %j) is %j', (frames, position, expected) => {
  expect(clampFrameIndex(frames, position)).toBe(expected)
})

describe('rangeOf', () => {
  const small = buildTable(
    4,
    [
      { name: 'Frame', kind: 'number', values: Float64Array.from([0, 0, 1, 1]) },
      { name: 'V', kind: 'number', values: Float64Array.from([-50, 2, NaN, 25]) },
      { name: 'Nothing', kind: 'number', values: Float64Array.from([NaN, NaN, NaN, NaN]) }
    ],
    'Frame'
  )

  it('ignores non-finite values, and counts only the rows a mask keeps', () => {
    expect(rangeOf(small, 'V')).toEqual([-50, 25])
    expect(rangeOf(small, 'V', Uint8Array.from([0, 1, 1, 0]))).toEqual([2, 2])
  })

  it('degenerates rather than raising on an empty or unknown column', () => {
    expect(rangeOf(small, 'Nothing')).toEqual([0, 0])
    expect(rangeOf(small, 'NotAColumn')).toEqual([0, 0])
  })
})
