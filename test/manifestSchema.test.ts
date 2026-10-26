// Loading and saving a manifest.
//
// The app writes a file the user authored, and the ways that goes wrong are
// all silent: a dropped block, an escaped non-ASCII name.

import { readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

import { Manifest, ManifestError } from '../src/data/manifest'
import { makeCase } from './helpers/makeCase'

const EMPTY_V2 = { manifest_version: 2, table: {} }

const read = (dir: string, file = 'info.json') =>
  JSON.parse(readFileSync(join(dir, file), 'utf8'))

describe('loading', () => {
  it('refuses a missing, malformed or non-object manifest', async () => {
    await expect(Manifest.load(makeCase(null))).rejects.toBeInstanceOf(ManifestError)
    for (const text of ['{not json', '[1, 2, 3]']) {
      const dir = makeCase(EMPTY_V2)
      writeFileSync(join(dir, 'info.json'), text, 'utf8')
      await expect(Manifest.load(dir)).rejects.toBeInstanceOf(ManifestError)
    }
  })

  it('falls back to the directory name', async () => {
    expect((await Manifest.load(makeCase(EMPTY_V2, [], 'MyCase'))).name).toBe('MyCase')
  })

  it('refuses a v1 manifest', async () => {
    const v1 = { name: 'Legacy Case', slider: 'Frame', x_3d: 'X', keys: {} }
    await expect(Manifest.load(makeCase(v1))).rejects.toThrow(/manifest_version/)
  })

  it('refuses an unknown version', async () => {
    await expect(Manifest.load(makeCase({ ...EMPTY_V2, manifest_version: 3 }))).rejects.toBeInstanceOf(
      ManifestError
    )
  })
})

describe('saving a manifest', () => {
  it('writes back what it read, LF-terminated', async () => {
    const original = {
      manifest_version: 2,
      name: 'Ünïcøde café',
      table: { slider: 'Frame' },
      cloud: { suffix: '.cloud.h5' },
      something_new: { a: [1, 2, 3] }
    }
    const dir = makeCase(original)
    await (await Manifest.load(dir)).save()

    const text = readFileSync(join(dir, 'info.json'), 'utf8')
    expect(JSON.parse(text)).toEqual(original)
    // Not \uXXXX escapes, and no platform line endings: a picker change must
    // not rewrite every line.
    expect(text).toContain('Ünïcøde café')
    expect(text.endsWith('\n') && !text.includes('\r')).toBe(true)
  })

  it('keeps every block when only an axis changed', async () => {
    const dir = makeCase({
      manifest_version: 2,
      table: { slider: 'Frame', x_3d: 'X' },
      cloud: { suffix: '.cloud.h5' },
      curve: { suffix: '.curve.h5' },
      image: {}
    })
    const manifest = await Manifest.load(dir)
    manifest.updateTableView({ x_3d: 'East', slider: 'Time' })
    await manifest.save()

    const written = read(dir)
    expect(written.table).toEqual({ slider: 'Time', x_3d: 'East' })
    expect(written.cloud).toEqual({ suffix: '.cloud.h5' })
    expect(written.curve).toEqual({ suffix: '.curve.h5' })
    expect(written.image).toEqual({})
  })
})

describe('updateReferenceColumns', () => {
  it('records a mapping and a cleared field', async () => {
    const dir = makeCase(EMPTY_V2)
    const manifest = await Manifest.load(dir)
    // The empty string is NO_COLUMN: a decision the next read must not
    // guess back.
    manifest.updateReferenceColumns({ x: 'East', yaw: '' })
    await manifest.save()
    expect(read(dir).reference.columns).toEqual({ x: 'East', yaw: '' })
  })

  it('refuses an unknown field', async () => {
    // It would be written and then silently ignored on the next read.
    const manifest = await Manifest.load(makeCase(EMPTY_V2))
    manifest.updateReferenceColumns({ speed: 'Speed' })
    expect(manifest.raw.reference.columns.speed).toBeUndefined()
  })
})
