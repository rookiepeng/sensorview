// Saving a manifest changes only what was asked for.
//
// §7 of the plan listed this as one of "three tests Python does not have and
// should", and it went unwritten until the column config gave it a caller.
// The hazard is R1: the app now writes a file the user authored, and the ways
// that goes wrong are all silent — a reserialized `Infinity`, an escaped
// non-ASCII name, a reordered key. None of them stops the file loading.

import { mkdtemp, readFile, writeFile, access } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

import { Manifest } from '../src/data/manifest'

/** A v2 manifest with the shapes that are easy to mangle on the way out. */
const V2 = `{
  "manifest_version": 2,
  "name": "Ünïcøde café",
  "table": {
    "slider": "Frame",
    "x_3d": "X",
    "y_3d": "Y",
    "z_3d": "Z",
    "keys": {
      "X": { "description": "East (m)", "decimal": 2, "type": "numerical" }
    }
  },
  "reference": {
    "columns": { "frame": "frame", "x": "x", "y": "y" }
  },
  "something_a_later_version_added": { "nested": [1, 2, 3] }
}
`

async function makeCase(contents: string): Promise<string> {
  const dir = await mkdtemp(join(tmpdir(), 'sv-manifest-'))
  await writeFile(join(dir, 'info.json'), contents, 'utf8')
  return dir
}

describe('saving a v2 manifest', () => {
  it('leaves an untouched file semantically identical', async () => {
    const dir = await makeCase(V2)
    const manifest = await Manifest.load(dir)
    await manifest.save()

    const after = JSON.parse(await readFile(join(dir, 'info.json'), 'utf8'))
    expect(after).toEqual(JSON.parse(V2))
  })

  it('keeps a non-ASCII name as itself', async () => {
    // `json.dump` defaults to ensure_ascii and would have written \\uXXXX
    // here. JSON.stringify does not, which is the behaviour to keep.
    const dir = await makeCase(V2)
    const manifest = await Manifest.load(dir)
    manifest.updateTableView({ x_3d: 'Y' })
    await manifest.save()

    const text = await readFile(join(dir, 'info.json'), 'utf8')
    expect(text).toContain('Ünïcøde café')
    expect(text).not.toContain('\\u')
  })

  it('keeps blocks it has never heard of', async () => {
    const dir = await makeCase(V2)
    const manifest = await Manifest.load(dir)
    manifest.updateTableView({ x_3d: 'Z' })
    await manifest.save()

    const after = JSON.parse(await readFile(join(dir, 'info.json'), 'utf8'))
    expect(after.something_a_later_version_added).toEqual({ nested: [1, 2, 3] })
    // And the keys it does know, that this edit did not touch.
    expect(after.table.keys.X.description).toBe('East (m)')
    expect(after.table.y_3d).toBe('Y')
  })

  it('writes the axis that changed', async () => {
    const dir = await makeCase(V2)
    const manifest = await Manifest.load(dir)
    manifest.updateTableView({ x_3d: 'Range', slider: 'Time' })
    await manifest.save()

    const after = JSON.parse(await readFile(join(dir, 'info.json'), 'utf8'))
    expect(after.table.x_3d).toBe('Range')
    expect(after.table.slider).toBe('Time')
  })

  it('records a reference column, and a cleared one', async () => {
    const dir = await makeCase(V2)
    const manifest = await Manifest.load(dir)
    manifest.updateReferenceColumns({ z: 'height', yaw: '' })
    await manifest.save()

    const after = JSON.parse(await readFile(join(dir, 'info.json'), 'utf8'))
    expect(after.reference.columns.z).toBe('height')
    // The empty string is NO_COLUMN: a decision, not an omission, and the
    // normalizer must not guess `yaw` straight back on the next read.
    expect(after.reference.columns.yaw).toBe('')
    expect(after.reference.columns.x).toBe('x')
  })

  it('writes no backup for a file that was already v2', async () => {
    const dir = await makeCase(V2)
    const manifest = await Manifest.load(dir)
    await manifest.save()

    await expect(access(join(dir, 'info.json.bak'))).rejects.toThrow()
  })
})

describe('saving a v1 manifest', () => {
  const V1 = `{
  "name": "old",
  "table": { "slider": "Frame", "x_3d": "X" },
  "keys": { "X": { "description": "East", "type": "numerical" } }
}
`

  it('upgrades it and keeps the original once', async () => {
    const dir = await makeCase(V1)
    const first = await Manifest.load(dir)
    first.updateTableView({ x_3d: 'Y' })
    await first.save()

    const backup = await readFile(join(dir, 'info.json.bak'), 'utf8')
    expect(JSON.parse(backup)).toEqual(JSON.parse(V1))

    const after = JSON.parse(await readFile(join(dir, 'info.json'), 'utf8'))
    expect(after.manifest_version).toBe(2)
    expect(after.table.x_3d).toBe('Y')
  })

  it('does not overwrite the backup on a second save', async () => {
    // The second save would otherwise replace the original with the
    // already-upgraded copy, losing the only record of what was there.
    const dir = await makeCase(V1)
    const first = await Manifest.load(dir)
    await first.save()

    const second = await Manifest.load(dir)
    second.updateTableView({ x_3d: 'Z' })
    await second.save()

    const backup = JSON.parse(await readFile(join(dir, 'info.json.bak'), 'utf8'))
    expect(backup.manifest_version).toBeUndefined()
    expect(backup.table.x_3d).toBe('X')
  })
})
