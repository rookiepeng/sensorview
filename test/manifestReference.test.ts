// The reference overlay's display block.
//
// Transliterated from tests/test_manifest_reference.py. This is the other half
// of the manifest: no filesystem, all normalization, and the place where
// "degrade rather than raise" is the whole design. A typo in a cosmetic field
// should not cost the user their reference point, so almost every malformed
// input here has a defined fallback rather than an error -- which means the
// fallbacks are the behaviour, and need pinning.

import { describe, expect, it } from 'vitest'

import {
  NO_COLUMN,
  normalizeCloudColumns,
  normalizeReferenceColumns,
  normalizeReferenceDisplay
} from '../src/data/manifest'

/** A unit cube, as a dataset would declare one. */
const CUBE_VERTICES = [
  [0, 0, 0],
  [1, 0, 0],
  [1, 1, 0],
  [0, 1, 0]
]
const CUBE_FACES = [
  [0, 1, 2],
  [0, 2, 3]
]

const mesh = (extra: object = {}) =>
  normalizeReferenceDisplay({
    shape: 'mesh',
    vertices: CUBE_VERTICES,
    faces: CUBE_FACES,
    ...extra
  })

describe('normalizeReferenceDisplay, marker', () => {
  it('yields the documented default for an absent block', () => {
    const display = normalizeReferenceDisplay(null)
    expect(display.shape).toBe('marker')
    expect(display.color).toBe('#ffffff')
    expect(display.size).toBe(6)
    expect(display.symbol).toBe('circle')
  })

  it('distinguishes an absent block from an empty one', () => {
    // The defaults otherwise erase the difference, and the renderer needs it:
    // a declared reference nothing can place is still drawn at the origin,
    // while a dataset that never mentioned one draws nothing.
    expect(normalizeReferenceDisplay(null).declared).toBe(false)
    expect(normalizeReferenceDisplay({}).declared).toBe(true)
  })

  it('cannot have `declared` claimed by the manifest', () => {
    // Whether the block exists is the function's reading of its input, not a
    // field the block gets to author.
    expect(normalizeReferenceDisplay({ declared: true } as object).declared).toBe(true)
    expect(normalizeReferenceDisplay(null).declared).toBe(false)
  })

  it('applies overrides', () => {
    const display = normalizeReferenceDisplay({ color: '#ff0000', size: 12 })
    expect(display.color).toBe('#ff0000')
    expect(display.size).toBe(12)
  })

  it('degrades an unknown shape to marker', () => {
    expect(normalizeReferenceDisplay({ shape: 'hologram' }).shape).toBe('marker')
  })

  it('reads the shape case-insensitively', () => {
    expect(normalizeReferenceDisplay({ shape: 'MESH', vertices: CUBE_VERTICES, faces: CUBE_FACES }).shape).toBe('mesh')
  })

  it('keeps source keys out of the display', () => {
    // `suffix` and `columns` say where the data comes from, not how it looks.
    const display = normalizeReferenceDisplay({ suffix: '.pose.parquet', columns: { x: 'X' } })
    expect(display.suffix).toBeUndefined()
    expect(display.columns).toBeUndefined()
  })

  it('carries no mesh keys', () => {
    const display = normalizeReferenceDisplay({})
    expect(display.vertices).toBeUndefined()
    expect(display.faces).toBeUndefined()
    expect(display.radius).toBeUndefined()
  })
})

describe('normalizeReferenceDisplay, mesh', () => {
  it('normalizes a valid mesh', () => {
    const display = mesh()
    expect(display.shape).toBe('mesh')
    expect(display.vertices).toEqual(CUBE_VERTICES)
    expect(display.faces).toEqual(CUBE_FACES)
  })

  it('gains extent and radius', () => {
    const display = mesh()
    expect(display.extent).toEqual([
      [0, 1],
      [0, 1],
      [0, 0]
    ])
    expect(display.radius).toBeCloseTo(Math.SQRT2, 10)
  })

  it('is translucent by default', () => {
    // A solid body at full opacity would bury every detection inside it.
    expect(mesh().opacity).toBe(0.35)
    expect(normalizeReferenceDisplay({}).opacity).toBe(1.0)
  })

  it('derives the wireframe from the faces by default', () => {
    const edges = mesh().edges as number[][]
    // Two triangles sharing edge 0-2: five edges, not six.
    expect(edges.length).toBe(5)
  })

  it('does not duplicate a shared edge', () => {
    const edges = mesh().edges as number[][]
    const keys = edges.map(([a, b]) => (a! < b! ? `${a}:${b}` : `${b}:${a}`))
    expect(new Set(keys).size).toBe(keys.length)
  })

  it('draws no edges when asked for none', () => {
    expect(mesh({ edges: false }).edges).toEqual([])
  })

  it('uses explicit pairs verbatim', () => {
    expect(mesh({ edges: [[0, 2]] }).edges).toEqual([[0, 2]])
  })

  it('drops out-of-range pairs', () => {
    expect(mesh({ edges: [[0, 99]] }).edges).toEqual([])
  })

  it('drops malformed pairs', () => {
    expect(mesh({ edges: [[0], 'nope', [0, 1, 2]] }).edges).toEqual([])
  })

  it('follows the colour when edge_color is unset', () => {
    expect(mesh({ color: '#abcdef' }).edge_color).toBe('#abcdef')
  })

  it('lets an explicit edge colour win', () => {
    expect(mesh({ color: '#abcdef', edge_color: '#123456' }).edge_color).toBe('#123456')
  })

  it('degrades to marker without faces', () => {
    // Vertices with no face enclose nothing, and a mesh with no triangles is
    // an invisible reference. A dot in the right place beats nothing at all.
    const display = normalizeReferenceDisplay({ shape: 'mesh', vertices: CUBE_VERTICES, faces: [] })
    expect(display.shape).toBe('marker')
  })

  it('degrades to marker without vertices', () => {
    const display = normalizeReferenceDisplay({ shape: 'mesh', vertices: [], faces: CUBE_FACES })
    expect(display.shape).toBe('marker')
  })

  it('drops faces pointing past the vertices', () => {
    const display = mesh({ faces: [[0, 1, 2], [0, 1, 99]] })
    expect(display.faces).toEqual([[0, 1, 2]])
  })

  it('drops malformed vertices', () => {
    const display = normalizeReferenceDisplay({
      shape: 'mesh',
      vertices: [[0, 0, 0], 'nope', [1, 0, 0], [1, 1, 0]],
      faces: [[0, 1, 2]]
    })
    expect(display.vertices).toEqual([
      [0, 0, 0],
      [1, 0, 0],
      [1, 1, 0]
    ])
  })

  it('renumbers when a vertex is dropped, which can invalidate a face', () => {
    // Dropping one renumbers everything after it, so a face addressing the
    // old last index now points past the end and goes too.
    const display = normalizeReferenceDisplay({
      shape: 'mesh',
      vertices: [[0, 0, 0], [1, 0, 0], 'nope'],
      faces: [[0, 1, 2]]
    })
    expect(display.shape).toBe('marker')
  })

  it('keeps other overrides when degrading to marker', () => {
    const display = normalizeReferenceDisplay({
      shape: 'mesh',
      vertices: [],
      faces: [],
      color: '#ff0000',
      name: 'Ego'
    })
    expect(display.shape).toBe('marker')
    expect(display.color).toBe('#ff0000')
    expect(display.name).toBe('Ego')
  })

  it('accepts the mapping form of a vertex', () => {
    // Both forms read naturally in a hand-written manifest.
    const display = normalizeReferenceDisplay({
      shape: 'mesh',
      vertices: [{ x: 0, y: 0, z: 0 }, { x: 1, y: 0, z: 0 }, { x: 1, y: 1, z: 0 }],
      faces: [[0, 1, 2]]
    })
    expect(display.vertices).toEqual([
      [0, 0, 0],
      [1, 0, 0],
      [1, 1, 0]
    ])
  })

  it('has a radius exceeding its per-axis extent on a diagonal', () => {
    // A mesh that turns with a pose reaches further along an axis than its own
    // extent on that axis, which is the reason radius exists separately.
    const display = normalizeReferenceDisplay({
      shape: 'mesh',
      vertices: [[0, 0, 0], [3, 4, 0], [3, 0, 0]],
      faces: [[0, 1, 2]]
    })
    expect(display.radius).toBeCloseTo(5, 10)
    expect(display.radius as number).toBeGreaterThan(4)
  })
})

describe('normalizeReferenceColumns', () => {
  it('leaves every field unmapped for an absent block', () => {
    const columns = normalizeReferenceColumns(null)
    expect(Object.values(columns).every((v) => v === null)).toBe(true)
    expect(Object.keys(columns).sort()).toEqual(['frame', 'pitch', 'roll', 'x', 'y', 'yaw', 'z'])
  })

  it('distinguishes unnamed from named-as-nothing', () => {
    // null means "guess a column from the field's own name"; NO_COLUMN means
    // the user saying the file has no such column. For `frame` that switches
    // the whole overlay off, so conflating them is not cosmetic.
    const columns = normalizeReferenceColumns({ x: 'East', y: null, z: '', yaw: 'None' })
    expect(columns.x).toBe('East')
    expect(columns.y).toBe(NO_COLUMN)
    expect(columns.z).toBe(NO_COLUMN)
    expect(columns.yaw).toBe(NO_COLUMN)
    expect(columns.pitch).toBeNull()
  })

  it('ignores unknown fields', () => {
    expect('speed' in normalizeReferenceColumns({ speed: 'Speed' })).toBe(false)
  })
})

describe('normalizeCloudColumns', () => {
  it('leaves every field unmapped for an absent block', () => {
    expect(normalizeCloudColumns(null)).toEqual({ x: null, y: null, z: null })
  })

  it('ignores a list, which older manifests carried as provenance', () => {
    expect(normalizeCloudColumns(['x', 'y', 'z'])).toEqual({ x: null, y: null, z: null })
  })

  it('maps named columns', () => {
    expect(normalizeCloudColumns({ x: 'east', y: 'north', z: 'up' })).toEqual({
      x: 'east',
      y: 'north',
      z: 'up'
    })
  })

  it('has no named-as-nothing spelling', () => {
    // A pose without a z is still a pose on the ground plane; a point without
    // an x is not a point, so every cloud field resolves to something.
    expect(normalizeCloudColumns({ x: '', y: null, z: 'None' })).toEqual({
      x: null,
      y: null,
      z: null
    })
  })
})
