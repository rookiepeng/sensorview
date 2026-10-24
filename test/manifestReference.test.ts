// The reference overlay's display block and the column mappings.
//
// "Degrade rather than raise" is the design: a typo in a cosmetic field
// should not cost the user their reference point, so almost every malformed
// input has a defined fallback -- which makes the fallbacks the behaviour.

import { describe, expect, it } from 'vitest'

import {
  NO_COLUMN,
  normalizeCloudColumns,
  normalizeReferenceColumns,
  normalizeReferenceDisplay
} from '../src/data/manifest'

/** Two triangles sharing the edge 0-2. */
const VERTICES = [
  [0, 0, 0],
  [1, 0, 0],
  [1, 1, 0],
  [0, 1, 0]
]
const FACES = [
  [0, 1, 2],
  [0, 2, 3]
]

const mesh = (extra: object = {}) =>
  normalizeReferenceDisplay({ shape: 'mesh', vertices: VERTICES, faces: FACES, ...extra })

describe('normalizeReferenceDisplay, marker', () => {
  it('yields the documented default for an absent block', () => {
    expect(normalizeReferenceDisplay(null)).toMatchObject({
      shape: 'marker',
      color: '#ffffff',
      size: 6,
      symbol: 'circle',
      opacity: 1,
      declared: false
    })
  })

  it('marks a present block as declared, which the block cannot claim itself', () => {
    // A declared reference nothing can place is still drawn at the origin.
    expect(normalizeReferenceDisplay({}).declared).toBe(true)
    expect(normalizeReferenceDisplay({ declared: false } as object).declared).toBe(true)
  })

  it('applies overrides and degrades an unknown shape', () => {
    const display = normalizeReferenceDisplay({ color: '#ff0000', size: 12, shape: 'hologram' })
    expect(display).toMatchObject({ color: '#ff0000', size: 12, shape: 'marker' })
    expect(normalizeReferenceDisplay({ shape: 'MESH', vertices: VERTICES, faces: FACES }).shape).toBe('mesh')
  })

  it('carries neither source nor mesh keys', () => {
    const display = normalizeReferenceDisplay({ suffix: '.pose.parquet', columns: { x: 'X' } })
    for (const key of ['suffix', 'columns', 'vertices', 'faces', 'radius']) {
      expect(display[key]).toBeUndefined()
    }
  })
})

describe('normalizeReferenceDisplay, mesh', () => {
  it('normalizes a valid mesh, with its extent and radius', () => {
    const display = mesh()
    expect(display).toMatchObject({ shape: 'mesh', vertices: VERTICES, faces: FACES })
    expect(display.extent).toEqual([
      [0, 1],
      [0, 1],
      [0, 0]
    ])
    expect(display.radius).toBeCloseTo(Math.SQRT2, 10)
    // A solid body at full opacity would bury every detection inside it.
    expect(display.opacity).toBe(0.35)
  })

  it('has a radius past its per-axis extent on a diagonal', () => {
    // A mesh turning with a pose reaches further than its own extent.
    const display = normalizeReferenceDisplay({
      shape: 'mesh',
      vertices: [[0, 0, 0], [3, 4, 0], [3, 0, 0]],
      faces: [[0, 1, 2]]
    })
    expect(display.radius).toBeCloseTo(5, 10)
  })

  it('derives the wireframe from the faces without doubling a shared edge', () => {
    const edges = mesh().edges as number[][]
    const keys = edges.map(([a, b]) => (a! < b! ? `${a}:${b}` : `${b}:${a}`))
    expect(new Set(keys).size).toBe(5)
    expect(keys.length).toBe(5)
  })

  it.each([
    ['none when asked for none', false, []],
    ['explicit pairs verbatim', [[0, 2]], [[0, 2]]],
    ['no out-of-range pair', [[0, 99]], []],
    ['no malformed pair', [[0], 'nope', [0, 1, 2]], []]
  ])('draws %s', (_, edges, expected) => {
    expect(mesh({ edges }).edges).toEqual(expected)
  })

  it('colors edges like the body unless told otherwise', () => {
    expect(mesh({ color: '#abcdef' }).edge_color).toBe('#abcdef')
    expect(mesh({ color: '#abcdef', edge_color: '#123456' }).edge_color).toBe('#123456')
  })

  it.each([
    ['without faces', { vertices: VERTICES, faces: [] }],
    ['without vertices', { vertices: [], faces: FACES }],
    // Dropping a vertex renumbers the rest, so the face now points past the end.
    ['when a dropped vertex invalidates the only face', { vertices: [[0, 0, 0], [1, 0, 0], 'nope'], faces: [[0, 1, 2]] }]
  ])('degrades to a marker %s, keeping other overrides', (_, block) => {
    const display = normalizeReferenceDisplay({ shape: 'mesh', color: '#ff0000', name: 'Ego', ...block })
    expect(display).toMatchObject({ shape: 'marker', color: '#ff0000', name: 'Ego' })
  })

  it('drops bad faces and vertices, and reads the mapping form of a vertex', () => {
    expect(mesh({ faces: [[0, 1, 2], [0, 1, 99]] }).faces).toEqual([[0, 1, 2]])
    const display = normalizeReferenceDisplay({
      shape: 'mesh',
      vertices: [{ x: 0, y: 0, z: 0 }, 'nope', [1, 0, 0], { x: 1, y: 1, z: 0 }],
      faces: [[0, 1, 2]]
    })
    expect(display.vertices).toEqual([
      [0, 0, 0],
      [1, 0, 0],
      [1, 1, 0]
    ])
  })
})

describe('normalizeReferenceColumns', () => {
  it('leaves every field unmapped for an absent block', () => {
    expect(normalizeReferenceColumns(null)).toEqual({
      frame: null,
      x: null,
      y: null,
      z: null,
      yaw: null,
      pitch: null,
      roll: null
    })
  })

  it('distinguishes unnamed from named-as-nothing, and ignores unknown fields', () => {
    // null means "guess from the field's name"; NO_COLUMN means the file has
    // no such column. For `frame` that switches the whole overlay off.
    const columns = normalizeReferenceColumns({ x: 'East', y: null, z: '', yaw: 'None', speed: 'S' })
    expect(columns).toMatchObject({ x: 'East', y: NO_COLUMN, z: NO_COLUMN, yaw: NO_COLUMN, pitch: null })
    expect('speed' in columns).toBe(false)
  })
})

describe('normalizeCloudColumns', () => {
  const NONE = { x: null, y: null, z: null }

  it.each([
    ['an absent block', null, NONE],
    // Older manifests carried a list as provenance.
    ['a list', ['x', 'y', 'z'], NONE],
    ['named columns', { x: 'east', y: 'north', z: 'up' }, { x: 'east', y: 'north', z: 'up' }],
    // A point without an x is not a point, so there is no named-as-nothing.
    ['empty names', { x: '', y: null, z: 'None' }, NONE]
  ])('maps %s', (_, block, expected) => {
    expect(normalizeCloudColumns(block)).toEqual(expected)
  })
})
