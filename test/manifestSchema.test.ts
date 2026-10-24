// Loading, upgrading and saving a manifest.
//
// The app writes a file the user authored, and the ways that goes wrong are
// all silent: a dropped block, an escaped non-ASCII name, a lost original.
// A v1 file is upgraded on first save and the original kept as
// `info.json.bak`.

import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

import { Manifest, ManifestError, upgradeToV2 } from '../src/data/manifest'
import { makeCase } from './helpers/makeCase'

const V1 = {
  name: 'Legacy Case',
  slider: 'Frame',
  x_3d: 'X',
  y_3d: 'Y',
  z_3d: 'Z',
  keys: { X: { description: 'East', type: 'numerical' } },
  // Keys a v1 file may carry that the upgrade drops.
  time_unit: 'us',
  custom_thing: { kept: true }
}

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
})

describe('upgradeToV2', () => {
  it('returns a v2 manifest untouched', () => {
    const v2 = { manifest_version: 2, table: { slider: 'Frame' }, cloud: { suffix: '.c.h5' } }
    expect(upgradeToV2(v2)).toBe(v2)
  })

  it('nests the v1 table keys and declares no sidecars', () => {
    const upgraded = upgradeToV2({ ...V1, reference: { shape: 'mesh' } })
    expect(upgraded.manifest_version).toBe(2)
    expect(upgraded.name).toBe('Legacy Case')
    expect(upgraded.table).toMatchObject({ slider: 'Frame', x_3d: 'X', keys: V1.keys })
    // Top-level in both schemas, so it carries straight across.
    expect(upgraded.reference).toEqual({ shape: 'mesh' })
    expect([upgraded.cloud, upgraded.curve, upgraded.image]).toEqual([undefined, undefined, undefined])
  })
})

describe('saving a v2 manifest', () => {
  it('writes back what it read, LF-terminated and without a backup', async () => {
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
    expect(existsSync(join(dir, 'info.json.bak'))).toBe(false)
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

describe('saving a v1 manifest', () => {
  it('upgrades it and keeps the original as info.json.bak', async () => {
    const dir = makeCase(V1)
    const manifest = await Manifest.load(dir)
    expect(manifest.sourceVersion).toBe(1)
    await manifest.save()
    expect(manifest.sourceVersion).toBe(2)

    const written = read(dir)
    expect(written.manifest_version).toBe(2)
    expect(written.table.slider).toBe('Frame')
    expect(written.time_unit).toBeUndefined()
    expect(read(dir, 'info.json.bak')).toEqual(V1)
  })

  it('does not overwrite the backup on a second save', async () => {
    const dir = makeCase(V1)
    const manifest = await Manifest.load(dir)
    await manifest.save()
    manifest.updateTableView({ x_3d: 'Changed' })
    await manifest.save()
    expect(read(dir, 'info.json.bak')).toEqual(V1)
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
