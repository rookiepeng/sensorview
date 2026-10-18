// Loading, upgrading and saving.
//
// Adapted from tests/test_manifest_schema.py rather than transliterated,
// because saving deliberately behaves differently now.
//
// The Python wrote a v1 file back as v1, projected down to a five-key
// whitelist -- so every key outside it was dropped. The 3D view saves on every
// axis-picker change, which made that a silent edit of the user's file on a
// mouse click. The projection existed to feed the flat config the Dash
// callbacks read, and they are gone, so a v1 file is upgraded on first save
// and the original kept as `info.json.bak`.
//
// That is a change to files on disk, so it is pinned here deliberately rather
// than left to be noticed.

import { readFileSync, existsSync, writeFileSync } from 'node:fs'
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
  // Keys a v1 file may carry that the old writer silently dropped.
  time_unit: 'us',
  x_ref: 'RefX',
  custom_thing: { kept: true }
}

describe('loading', () => {
  it('refuses a case with no manifest', async () => {
    await expect(Manifest.load(makeCase(null))).rejects.toBeInstanceOf(ManifestError)
  })

  it('refuses malformed JSON', async () => {
    const dir = makeCase({ manifest_version: 2, table: {} })
    writeFileSync(join(dir, 'info.json'), '{not json', 'utf8')
    await expect(Manifest.load(dir)).rejects.toBeInstanceOf(ManifestError)
  })

  it('refuses a JSON document that is not an object', async () => {
    const dir = makeCase({ manifest_version: 2, table: {} })
    writeFileSync(join(dir, 'info.json'), '[1, 2, 3]', 'utf8')
    await expect(Manifest.load(dir)).rejects.toBeInstanceOf(ManifestError)
  })

  it('falls back to the directory name', async () => {
    const dir = makeCase({ manifest_version: 2, table: {} }, [], 'MyCase')
    expect((await Manifest.load(dir)).name).toBe('MyCase')
  })
})

describe('upgradeToV2', () => {
  it('returns a v2 manifest untouched', () => {
    const v2 = { manifest_version: 2, table: { slider: 'Frame' }, cloud: { suffix: '.c.h5' } }
    expect(upgradeToV2(v2)).toBe(v2)
  })

  it('nests the v1 table keys', () => {
    const upgraded = upgradeToV2({ ...V1 })
    expect(upgraded.manifest_version).toBe(2)
    expect(upgraded.table.slider).toBe('Frame')
    expect(upgraded.table.x_3d).toBe('X')
    expect(upgraded.table.keys).toEqual(V1.keys)
  })

  it('keeps the name', () => {
    expect(upgradeToV2({ ...V1 }).name).toBe('Legacy Case')
  })

  it('carries a top-level reference block across', () => {
    // The block sits at the top level in both schemas, so a v1 dataset can
    // style its reference without being migrated first.
    const upgraded = upgradeToV2({ ...V1, reference: { shape: 'mesh' } })
    expect(upgraded.reference).toEqual({ shape: 'mesh' })
  })

  it('declares no sidecars', () => {
    const upgraded = upgradeToV2({ ...V1 })
    expect(upgraded.cloud).toBeUndefined()
    expect(upgraded.curve).toBeUndefined()
    expect(upgraded.image).toBeUndefined()
  })
})

describe('saving a v2 manifest', () => {
  it('writes back what it read, unchanged', async () => {
    // Nothing is reserialized that was not changed: unknown blocks, key order
    // and anything a later version adds all survive.
    const original = {
      manifest_version: 2,
      table: { slider: 'Frame' },
      cloud: { suffix: '.cloud.h5' },
      something_new: { a: 1 }
    }
    const dir = makeCase(original)
    const manifest = await Manifest.load(dir)
    await manifest.save()

    const written = JSON.parse(readFileSync(join(dir, 'info.json'), 'utf8'))
    expect(written).toEqual(original)
  })

  it('keeps every block when only an axis changed', async () => {
    // The case the old v1 writer got wrong: moving a picker must not cost the
    // dataset its cloud, curve and image blocks.
    const dir = makeCase({
      manifest_version: 2,
      table: { slider: 'Frame', x_3d: 'X' },
      cloud: { suffix: '.cloud.h5' },
      curve: { suffix: '.curve.h5' },
      image: {}
    })
    const manifest = await Manifest.load(dir)
    manifest.updateTableView({ x_3d: 'East' })
    await manifest.save()

    const written = JSON.parse(readFileSync(join(dir, 'info.json'), 'utf8'))
    expect(written.table.x_3d).toBe('East')
    expect(written.cloud).toEqual({ suffix: '.cloud.h5' })
    expect(written.curve).toEqual({ suffix: '.curve.h5' })
    expect(written.image).toEqual({})
  })

  it('does not write a backup', async () => {
    const dir = makeCase({ manifest_version: 2, table: {} })
    await (await Manifest.load(dir)).save()
    expect(existsSync(join(dir, 'info.json.bak'))).toBe(false)
  })

  it('ends with a newline and uses LF', async () => {
    // The view saves on every axis change, and letting the platform translate
    // would rewrite every line as a side effect of moving a picker.
    const dir = makeCase({ manifest_version: 2, table: {} })
    await (await Manifest.load(dir)).save()
    const text = readFileSync(join(dir, 'info.json'), 'utf8')
    expect(text.endsWith('\n')).toBe(true)
    expect(text.includes('\r')).toBe(false)
  })
})

describe('saving a v1 manifest', () => {
  it('upgrades it to v2', async () => {
    const dir = makeCase(V1)
    const manifest = await Manifest.load(dir)
    expect(manifest.sourceVersion).toBe(1)

    await manifest.save()
    const written = JSON.parse(readFileSync(join(dir, 'info.json'), 'utf8'))
    expect(written.manifest_version).toBe(2)
    expect(written.table.slider).toBe('Frame')
  })

  it('keeps the original as info.json.bak', async () => {
    const dir = makeCase(V1)
    await (await Manifest.load(dir)).save()

    const backup = JSON.parse(readFileSync(join(dir, 'info.json.bak'), 'utf8'))
    expect(backup).toEqual(V1)
    expect(backup.manifest_version).toBeUndefined()
  })

  it('does not overwrite the backup on a second save', async () => {
    // A second save must not replace the original with the upgraded copy --
    // which is exactly what a naive "always back up first" would do.
    const dir = makeCase(V1)
    const manifest = await Manifest.load(dir)
    await manifest.save()
    manifest.updateTableView({ x_3d: 'Changed' })
    await manifest.save()

    const backup = JSON.parse(readFileSync(join(dir, 'info.json.bak'), 'utf8'))
    expect(backup.manifest_version).toBeUndefined()
    expect(backup.x_3d).toBe('X')
  })

  it('stops being v1 after the first save', async () => {
    const dir = makeCase(V1)
    const manifest = await Manifest.load(dir)
    await manifest.save()
    expect(manifest.sourceVersion).toBe(2)
  })

  it('drops the keys the old writer dropped, but only to the backup', async () => {
    // Upgrading still loses `time_unit`, `x_ref` and anything else outside the
    // v1 table whitelist -- nothing reads them. The difference from before is
    // that the original is still on disk, instead of having been overwritten.
    const dir = makeCase(V1)
    await (await Manifest.load(dir)).save()

    const written = JSON.parse(readFileSync(join(dir, 'info.json'), 'utf8'))
    expect(written.time_unit).toBeUndefined()
    expect(written.custom_thing).toBeUndefined()

    const backup = JSON.parse(readFileSync(join(dir, 'info.json.bak'), 'utf8'))
    expect(backup.time_unit).toBe('us')
    expect(backup.custom_thing).toEqual({ kept: true })
  })
})

describe('updateReferenceColumns', () => {
  it('records a mapping', async () => {
    const dir = makeCase({ manifest_version: 2, table: {} })
    const manifest = await Manifest.load(dir)
    manifest.updateReferenceColumns({ x: 'East', y: 'North' })
    await manifest.save()

    const written = JSON.parse(readFileSync(join(dir, 'info.json'), 'utf8'))
    expect(written.reference.columns).toEqual({ x: 'East', y: 'North' })
  })

  it('refuses an unknown field', async () => {
    // It would be written and then silently ignored on the next read, which is
    // worse than not accepting it.
    const dir = makeCase({ manifest_version: 2, table: {} })
    const manifest = await Manifest.load(dir)
    manifest.updateReferenceColumns({ speed: 'Speed' })
    expect(manifest.raw.reference.columns.speed).toBeUndefined()
  })
})
