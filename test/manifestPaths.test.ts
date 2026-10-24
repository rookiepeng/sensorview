// Stem resolution and sidecar discovery.
//
// All string handling, and every case is one where a reasonable-looking
// implementation gets it wrong: a sibling log whose stem shares a prefix, a
// generic suffix that swallows a file of a different kind, a stream present
// in two containers.

import { describe, expect, it } from 'vitest'

import { Manifest, logStem, suffixSourceId, tableSidecarSuffixes } from '../src/data/manifest'
import { V2_MANIFEST, makeCase } from './helpers/makeCase'

const load = (manifest: object | null, files: string[] = []) =>
  Manifest.load(makeCase(manifest, files))

const posix = (path: string | null) => path?.replace(/\\/g, '/')

/** A manifest whose curves use a generic `.h5` suffix. */
const GENERIC = { manifest_version: 2, table: {}, curve: { suffix: '.h5' } }

describe('logStem', () => {
  it.each([
    ['drive_01.parquet', undefined, 'drive_01'],
    ['/data/case/drive_01.parquet', undefined, 'drive_01'],
    ['drive_01.table.pq', '.table.pq', 'drive_01'],
    // A custom suffix still reduces a plain .parquet in the same folder.
    ['drive_01.parquet', '.table.pq', 'drive_01'],
    ['DRIVE_01.PARQUET', undefined, 'DRIVE_01'],
    ['drive_01.csv', undefined, 'drive_01'],
    ['drive.01.parquet', undefined, 'drive.01']
  ])('%s (%s) -> %s', (path, suffix, expected) => {
    expect(logStem(path, suffix)).toBe(expected)
  })
})

describe('suffixSourceId', () => {
  it.each([
    ['.curve.h5', 'curve'],
    ['.sensor_1.h5', 'sensor_1'],
    // A bare extension distinguishes nothing, so it falls back.
    ['.h5', 'curve'],
    ['h5', 'curve']
  ])('names %s as %s', (suffix, expected) => {
    expect(suffixSourceId(suffix)).toBe(expected)
  })
})

describe('stems and cloud paths', () => {
  it('keeps the subfolder in the stem and resolves sidecars beside the log', async () => {
    const dir = makeCase(V2_MANIFEST, ['run_a/drive_01.parquet', 'drive_02.parquet'])
    const manifest = await Manifest.load(dir)
    expect(manifest.stemOf(`${dir}/run_a/drive_01.parquet`)).toBe('run_a/drive_01')
    expect(manifest.stemOf(`${dir}/drive_02.parquet`)).toBe('drive_02')
    expect(posix(manifest.cloudPath('run_a/drive_01'))).toContain('run_a/drive_01.cloud.h5')
  })

  it('yields no cloud path without a cloud block', async () => {
    expect((await load({ manifest_version: 2, table: {} })).cloudPath('drive_01')).toBeNull()
  })
})

describe('curveSources', () => {
  const ids = async (manifest: object, files: string[], stem = 'drive_01') =>
    (await (await load(manifest, files)).curveSources(stem)).map((s) => s.id)

  it('yields the default source for the default suffix', async () => {
    const sources = await (await load(V2_MANIFEST, ['drive_01.curve.h5'])).curveSources('drive_01')
    expect(sources.map((s) => s.id)).toEqual(['curve'])
    expect(sources[0]!.file.endsWith('drive_01.curve.h5')).toBe(true)
  })

  it('discovers named sensors under a generic suffix, with readable labels', async () => {
    const manifest = await load(GENERIC, [
      'drive_01.h5',
      'drive_01.sensor_2.h5',
      'drive_01.radar_front_left.h5'
    ])
    const sources = await manifest.curveSources('drive_01')
    expect(sources.map((s) => s.id).sort()).toEqual(['curve', 'radar_front_left', 'sensor_2'])
    expect(sources.find((s) => s.id === 'radar_front_left')!.label).toBe('Radar Front Left')
  })

  it('does not swallow the cloud sidecar, unless declared as the curve suffix', async () => {
    const cloud = { cloud: { suffix: '.cloud.h5' } }
    expect(
      await ids({ ...GENERIC, ...cloud }, ['drive_01.h5', 'drive_01.cloud.h5'])
    ).toEqual(['curve'])
    expect(
      await ids({ ...GENERIC, ...cloud, curve: { suffix: '.cloud.h5' } }, ['drive_01.cloud.h5'])
    ).toEqual(['cloud'])
  })

  it('keeps declared order and lists a file matching two suffixes once', async () => {
    const order = { manifest_version: 2, table: {}, curve: { suffix: ['.sensor_2.h5', '.sensor_1.h5'] } }
    expect(await ids(order, ['drive_01.sensor_1.h5', 'drive_01.sensor_2.h5'])).toEqual([
      'sensor_2',
      'sensor_1'
    ])
    const both = { manifest_version: 2, table: {}, curve: { suffix: ['.curve.h5', '.h5'] } }
    expect(await ids(both, ['drive_01.curve.h5'])).toEqual(['curve'])
  })

  it('does not claim a longer stem', async () => {
    // `drive_010` merely shares a prefix with `drive_01`.
    expect(await ids(GENERIC, ['drive_01.h5', 'drive_010.h5'])).toEqual(['curve'])
  })

  it('yields nothing without a block, a stem or a readable folder', async () => {
    expect(await ids({ manifest_version: 2, table: {} }, ['drive_01.curve.h5'])).toEqual([])
    expect(await ids(V2_MANIFEST, ['drive_01.curve.h5'], '')).toEqual([])
    expect(await ids(V2_MANIFEST, ['drive_01.curve.h5'], 'nope/drive_01')).toEqual([])
  })
})

describe('curvePath', () => {
  it('defaults to the first source and selects a named one', async () => {
    const manifest = await load(GENERIC, ['drive_01.h5', 'drive_01.sensor_2.h5'])
    expect(await manifest.curvePath('drive_01')).toBeTruthy()
    expect((await manifest.curvePath('drive_01', 'sensor_2'))!.endsWith('drive_01.sensor_2.h5')).toBe(
      true
    )
    expect(await manifest.hasCurve('drive_01')).toBe(true)
  })

  it('is null for an unknown source or a log with no curves', async () => {
    expect(await (await load(V2_MANIFEST, ['drive_01.curve.h5'])).curvePath('drive_01', 'nope')).toBeNull()
    const bare = await load(V2_MANIFEST, [])
    expect(await bare.curvePath('drive_01')).toBeNull()
    expect(await bare.hasCurve('drive_01')).toBe(false)
  })
})

describe('imageStreams', () => {
  const streams = async (files: string[], manifest: object = V2_MANIFEST) =>
    (await load(manifest, files)).imageStreams('drive_01')

  it('treats a bare stem as the default stream and sorts it first', async () => {
    const found = await streams(['drive_01.back.mp4', 'drive_01.mp4'])
    expect(found.map((s) => [s.id, s.label])).toEqual([
      ['image', 'Image'],
      ['back', 'Back']
    ])
  })

  it('prefers mp4 over avi, and serves an avi alone', async () => {
    const both = await streams(['drive_01.mp4', 'drive_01.avi'])
    expect(both.map((s) => posix(s.file)!.split('.').pop())).toEqual(['mp4'])
    expect((await streams(['drive_01.avi']))[0]!.file.endsWith('.avi')).toBe(true)
  })

  it('does not claim a longer stem', async () => {
    expect((await streams(['drive_01.mp4', 'drive_010.mp4'])).map((s) => s.id)).toEqual(['image'])
  })

  it('yields nothing without an image block', async () => {
    expect(await streams(['drive_01.mp4'], { manifest_version: 2, table: {} })).toEqual([])
  })

  it('tracks discovery in hasImage', async () => {
    expect(await (await load(V2_MANIFEST, ['drive_01.mp4'])).hasImage('drive_01')).toBe(true)
    expect(await (await load(V2_MANIFEST, [])).hasImage('drive_01')).toBe(false)
  })
})

describe('tableSidecarSuffixes', () => {
  it.each([
    // Without a manifest the picker must still not offer a pose as a log.
    [null, ['.reference.parquet']],
    [{ ...V2_MANIFEST, reference: { suffix: '.pose.parquet' } }, ['.pose.parquet', '.reference.parquet']],
    [{ ...V2_MANIFEST, reference: { suffix: '.REFERENCE.PARQUET' } }, ['.reference.parquet']]
  ])('%j -> %j', async (manifest, expected) => {
    expect(await tableSidecarSuffixes(makeCase(manifest))).toEqual(expected)
  })
})
