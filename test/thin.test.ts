// Thinning a large scatter, and selecting against the rows it left out.

import { describe, expect, it } from 'vitest'

import { buildTable, type Column } from '../src/shared/table'
import { THIN_ABOVE, regionsOfEvent, rowsInRegions, thinRows } from '../src/shared/thin'

/** `n` rows on a `side` x `side` lattice, each spot repeated. */
function lattice(n: number, side: number) {
  const x = new Float64Array(n)
  const y = new Float64Array(n)
  for (let i = 0; i < n; i++) {
    x[i] = i % side
    y[i] = Math.floor(i / side) % side
  }
  const columns: Column[] = [
    { name: 'Frame', kind: 'number', values: new Float64Array(n) },
    { name: 'X', kind: 'number', values: x },
    { name: 'Y', kind: 'number', values: y }
  ]
  const table = buildTable(n, columns, 'Frame')
  return { table, rows: Int32Array.from({ length: n }, (_, i) => i) }
}

describe('thinRows', () => {
  it('leaves a small scatter alone', () => {
    const { table, rows } = lattice(THIN_ABOVE, 10)
    expect(thinRows(table, rows, 'X', 'Y')).toBe(rows)
  })

  it('draws one row per occupied cell of a large one', () => {
    // 100 distinct spots, each repeated 300 times.
    const { table, rows } = lattice(30_000, 10)
    const kept = thinRows(table, rows, 'X', 'Y')
    expect(kept.length).toBe(100)
    // The first row to reach each spot, in table order.
    expect(Array.from(kept.slice(0, 3))).toEqual([0, 1, 2])
  })

  it('never draws more than the grid holds', () => {
    const n = 100_000
    const x = Float64Array.from({ length: n }, (_, i) => Math.sin(i) * 1000)
    const y = Float64Array.from({ length: n }, (_, i) => Math.cos(i * 1.7) * 1000)
    const table = buildTable(
      n,
      [
        { name: 'Frame', kind: 'number', values: new Float64Array(n) },
        { name: 'X', kind: 'number', values: x },
        { name: 'Y', kind: 'number', values: y }
      ],
      'Frame'
    )
    const rows = Int32Array.from({ length: n }, (_, i) => i)
    expect(thinRows(table, rows, 'X', 'Y').length).toBeLessThanOrEqual(200 * 120)
  })

  it('thins only inside a zoomed view', () => {
    const { table, rows } = lattice(30_000, 10)
    const kept = thinRows(table, rows, 'X', 'Y', { x: [0, 1], y: [0, 1] })
    // The four lattice spots in [0, 1] x [0, 1].
    expect(kept.length).toBe(4)
  })
})

describe('rowsInRegions', () => {
  it('finds every row in a box, not just the drawn ones', () => {
    const { table, rows } = lattice(30_000, 10)
    // x in [0, 4], y in [0, 9]: half the spots, so half the rows.
    const inside = rowsInRegions(table, rows, 'X', 'Y', [{ kind: 'box', x: [-0.5, 4.5], y: [-0.5, 9.5] }])
    expect(inside.length).toBe(15_000)
  })

  it('tests a lasso as a polygon, not as its bounding box', () => {
    const { table, rows } = lattice(30_000, 10)
    // A triangle over the lower-left half of the lattice.
    const lasso = { kind: 'lasso' as const, x: [-0.5, 9.5, -0.5], y: [-0.5, -0.5, 9.5] }
    const inside = rowsInRegions(table, rows, 'X', 'Y', [lasso])
    const box = rowsInRegions(table, rows, 'X', 'Y', [{ kind: 'box', x: [-0.5, 9.5], y: [-0.5, 9.5] }])
    expect(inside.length).toBeGreaterThan(0)
    expect(inside.length).toBeLessThan(box.length)
    for (const row of inside) {
      const vx = (table.columns.get('X') as { values: Float64Array }).values[row]!
      const vy = (table.columns.get('Y') as { values: Float64Array }).values[row]!
      expect(vx + vy).toBeLessThanOrEqual(9)
    }
  })

  it('unions several regions without counting a row twice', () => {
    const { table, rows } = lattice(30_000, 10)
    const a = { kind: 'box' as const, x: [-0.5, 0.5] as [number, number], y: [-0.5, 9.5] as [number, number] }
    const inside = rowsInRegions(table, rows, 'X', 'Y', [a, a])
    expect(inside.length).toBe(3_000)
  })
})

describe('regionsOfEvent', () => {
  it('reads a box from range', () => {
    expect(regionsOfEvent({ range: { x: [1, 2], y: [3, 4] } })).toEqual([
      { kind: 'box', x: [1, 2], y: [3, 4] }
    ])
  })

  it('reads a lasso from lassoPoints', () => {
    expect(regionsOfEvent({ lassoPoints: { x: [0, 1, 0], y: [0, 0, 1] } })).toEqual([
      { kind: 'lasso', x: [0, 1, 0], y: [0, 0, 1] }
    ])
  })

  it('prefers every shape in selections, rect and path alike', () => {
    const regions = regionsOfEvent({
      range: { x: [9, 9], y: [9, 9] },
      selections: [
        { type: 'rect', x0: 2, x1: 1, y0: 0, y1: 5 },
        { type: 'path', path: 'M0,0L1,0L0,1Z' }
      ]
    })
    expect(regions).toEqual([
      { kind: 'box', x: [1, 2], y: [0, 5] },
      { kind: 'lasso', x: [0, 1, 0], y: [0, 0, 1] }
    ])
  })

  it('has nothing for a deselect', () => {
    expect(regionsOfEvent(undefined)).toBeNull()
    expect(regionsOfEvent({ points: [] })).toBeNull()
  })
})
