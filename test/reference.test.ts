// The reference pose sidecar, checked against the Python it replaces.
//
// The fixture was captured from the Python (see `fixtures/README.md`) on the real
// sidecar in `data/NuScenes`. Column resolution is the part worth pinning:
// an unmapped file, an explicitly mapped one, a field a picker cleared, and a
// field pointed at a column the file does not have all resolve differently,
// and every one of them still draws something plausible if it is wrong.

import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { beforeEach, describe, expect, it } from 'vitest'

import { POSE_FIELDS, ReferenceStore } from '../src/data/referenceStore'

interface Case {
  label: string
  columns: Record<string, string | null> | null
  frameKey: string | null
  usable: boolean
  available: string[]
  resolved: Record<string, string | null>
  bounds: Record<string, [number, number]> | null
  poses: Record<string, Record<string, number> | null>
}

const golden = JSON.parse(
  readFileSync(join(__dirname, 'fixtures', 'reference.json'), 'utf8')
) as { path: string; cases: Case[] }

const PATH = join(__dirname, '..', golden.path)

describe('ReferenceStore', () => {
  beforeEach(() => {
    // The cache is keyed on the mapping as well as the file, so these cannot
    // collide -- but a test that depended on the cache rather than on the
    // reading would pass for the wrong reason.
    ReferenceStore.clearCache()
  })

  it.each(golden.cases.map((c) => [c.label, c] as const))('%s', (_, expected) => {
    const store = ReferenceStore.open(PATH, {
      columns: expected.columns ?? undefined,
      frameKey: expected.frameKey
    })!
    expect(store.resolvedColumns).toEqual(expected.resolved)
    expect(store.isUsable).toBe(expected.usable)
    expect(store.availableColumns).toEqual(expected.available)

    for (const [frame, pose] of Object.entries(expected.poses)) {
      const got = store.pose(Number(frame))
      // A gap draws nothing rather than stranding the reference.
      if (pose === null) {
        expect(got).toBeNull()
        continue
      }
      for (const field of POSE_FIELDS) {
        expect(got![field]).toBeCloseTo(pose[field]!, 12)
      }
    }

    const bounds = store.bounds()
    if (expected.bounds === null) {
      expect(bounds).toBeNull()
    } else {
      for (const axis of ['x', 'y', 'z'] as const) {
        expect(bounds![axis][0]).toBeCloseTo(expected.bounds[axis]![0], 12)
        expect(bounds![axis][1]).toBeCloseTo(expected.bounds[axis]![1], 12)
      }
    }
  })

  it('reuses a parsed sidecar, and re-reads it for a different mapping', () => {
    const first = ReferenceStore.open(PATH, { frameKey: 'Frame' })
    expect(ReferenceStore.open(PATH, { frameKey: 'Frame' })).toBe(first)
    // Repointing a picker has to re-derive the poses, so the mapping is part
    // of the key -- `frame` most of all, since it re-keys every row.
    expect(ReferenceStore.open(PATH, { frameKey: 'Frame', columns: { yaw: '' } })).not.toBe(
      first
    )
  })

  it('is null for a file that is not there', () => {
    expect(ReferenceStore.open(join(__dirname, 'no-such.parquet'))).toBeNull()
  })
})
