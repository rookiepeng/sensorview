// Stem resolution and sidecar discovery.
//
// Transliterated from tests/test_manifest_paths.py. This is the half of the
// manifest that touches the filesystem: which file belongs to which log, and
// which of several sidecars is which. It is all string handling, and every
// case here is one where a reasonable-looking implementation gets it wrong --
// a sibling log whose stem shares a prefix, a generic suffix that swallows a
// file of a different kind, a stream present in two containers.

import { describe, expect, it } from 'vitest'

import {
  Manifest,
  logStem,
  suffixSourceId,
  tableSidecarSuffixes
} from '../src/data/manifest'
import { V2_MANIFEST, makeCase } from './helpers/makeCase'

const load = (manifest: object | null, files: string[] = []) =>
  Manifest.load(makeCase(manifest, files))

describe('logStem', () => {
  it('strips the default suffix', () => {
    expect(logStem('drive_01.parquet')).toBe('drive_01')
  })

  it('reduces a path to its basename', () => {
    expect(logStem('/data/case/drive_01.parquet')).toBe('drive_01')
  })

  it('strips a custom suffix', () => {
    expect(logStem('drive_01.table.pq', '.table.pq')).toBe('drive_01')
  })

  it('reduces a plain parquet under a custom suffix', () => {
    // A dataset declaring a custom suffix still reduces the default one, so a
    // plain .parquet log in the same folder is not left with its extension.
    expect(logStem('drive_01.parquet', '.table.pq')).toBe('drive_01')
  })

  it('matches case-insensitively', () => {
    expect(logStem('DRIVE_01.PARQUET')).toBe('DRIVE_01')
  })

  it('falls back to dropping the extension', () => {
    expect(logStem('drive_01.csv')).toBe('drive_01')
  })

  it('keeps dots inside the stem', () => {
    expect(logStem('drive.01.parquet')).toBe('drive.01')
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

describe('logs in subfolders', () => {
  it('keeps the subfolder in the stem', async () => {
    const dir = makeCase(V2_MANIFEST, ['run_a/drive_01.parquet'])
    const manifest = await Manifest.load(dir)
    expect(manifest.stemOf(`${dir}/run_a/drive_01.parquet`)).toBe('run_a/drive_01')
  })

  it('leaves a top-level log bare', async () => {
    const dir = makeCase(V2_MANIFEST, ['drive_01.parquet'])
    const manifest = await Manifest.load(dir)
    expect(manifest.stemOf(`${dir}/drive_01.parquet`)).toBe('drive_01')
  })

  it('resolves sidecars in the log own folder', async () => {
    const dir = makeCase(V2_MANIFEST, ['run_a/drive_01.parquet', 'run_a/drive_01.cloud.h5'])
    const manifest = await Manifest.load(dir)
    const path = manifest.cloudPath('run_a/drive_01')!
    expect(path.replace(/\\/g, '/')).toContain('run_a/drive_01.cloud.h5')
  })
})

describe('cloud paths', () => {
  it('yields nothing without a cloud block', async () => {
    const manifest = await load({ manifest_version: 2, table: {} })
    expect(manifest.cloudPath('drive_01')).toBeNull()
  })

  it('builds the path from stem and suffix', async () => {
    const manifest = await load(V2_MANIFEST)
    expect(manifest.cloudPath('drive_01')!.replace(/\\/g, '/')).toContain(
      'drive_01.cloud.h5'
    )
  })
})

describe('curveSources', () => {
  it('yields the default source for the default suffix', async () => {
    const manifest = await load(V2_MANIFEST, ['drive_01.curve.h5'])
    const sources = await manifest.curveSources('drive_01')
    expect(sources.map((s) => s.id)).toEqual(['curve'])
    expect(sources[0]!.file.endsWith('drive_01.curve.h5')).toBe(true)
  })

  it('discovers named sensors under a generic suffix', async () => {
    const manifest = await load({ manifest_version: 2, table: {}, curve: { suffix: '.h5' } }, [
      'drive_01.h5',
      'drive_01.sensor_2.h5',
      'drive_01.sensor_6.h5'
    ])
    const ids = (await manifest.curveSources('drive_01')).map((s) => s.id).sort()
    expect(ids).toEqual(['curve', 'sensor_2', 'sensor_6'])
  })

  it('does not swallow the cloud sidecar', async () => {
    // ".h5" matches the cloud file too; it is a different kind of file and
    // must stay out of the curve picker.
    const manifest = await load(
      {
        manifest_version: 2,
        table: {},
        cloud: { suffix: '.cloud.h5' },
        curve: { suffix: '.h5' }
      },
      ['drive_01.h5', 'drive_01.cloud.h5']
    )
    expect((await manifest.curveSources('drive_01')).map((s) => s.id)).toEqual(['curve'])
  })

  it('never reserves an explicitly declared suffix', async () => {
    // Declaring ".cloud.h5" as the curve suffix means exactly that, even
    // though it is also the cloud default.
    const manifest = await load(
      {
        manifest_version: 2,
        table: {},
        cloud: { suffix: '.cloud.h5' },
        curve: { suffix: '.cloud.h5' }
      },
      ['drive_01.cloud.h5']
    )
    expect((await manifest.curveSources('drive_01')).map((s) => s.id)).toEqual(['cloud'])
  })

  it('preserves declared order', async () => {
    const manifest = await load(
      { manifest_version: 2, table: {}, curve: { suffix: ['.sensor_2.h5', '.sensor_1.h5'] } },
      ['drive_01.sensor_1.h5', 'drive_01.sensor_2.h5']
    )
    // Declared order, not alphabetical: that is the reason to list them.
    expect((await manifest.curveSources('drive_01')).map((s) => s.id)).toEqual([
      'sensor_2',
      'sensor_1'
    ])
  })

  it('lists a file matching two suffixes once', async () => {
    const manifest = await load(
      { manifest_version: 2, table: {}, curve: { suffix: ['.curve.h5', '.h5'] } },
      ['drive_01.curve.h5']
    )
    expect((await manifest.curveSources('drive_01')).map((s) => s.id)).toEqual(['curve'])
  })

  it('does not claim a longer stem', async () => {
    // `drive_010` merely shares a prefix with `drive_01`; its sidecars are not
    // `drive_01`'s. The text between stem and suffix has to start with a dot.
    const manifest = await load({ manifest_version: 2, table: {}, curve: { suffix: '.h5' } }, [
      'drive_01.h5',
      'drive_010.h5'
    ])
    expect((await manifest.curveSources('drive_01')).map((s) => s.id)).toEqual(['curve'])
  })

  it('humanises the label from the id', async () => {
    const manifest = await load({ manifest_version: 2, table: {}, curve: { suffix: '.h5' } }, [
      'drive_01.radar_front_left.h5'
    ])
    const sources = await manifest.curveSources('drive_01')
    expect(sources[0]!.label).toBe('Radar Front Left')
  })

  it('yields nothing without a curve block', async () => {
    const manifest = await load({ manifest_version: 2, table: {} }, ['drive_01.curve.h5'])
    expect(await manifest.curveSources('drive_01')).toEqual([])
  })

  it('yields nothing for an empty stem', async () => {
    const manifest = await load(V2_MANIFEST, ['drive_01.curve.h5'])
    expect(await manifest.curveSources('')).toEqual([])
  })

  it('yields nothing for an unreadable directory', async () => {
    const manifest = await load(V2_MANIFEST, ['drive_01.curve.h5'])
    expect(await manifest.curveSources('nope/drive_01')).toEqual([])
  })
})

describe('curvePath', () => {
  it('defaults to the first source', async () => {
    const manifest = await load({ manifest_version: 2, table: {}, curve: { suffix: '.h5' } }, [
      'drive_01.h5',
      'drive_01.sensor_2.h5'
    ])
    expect(await manifest.curvePath('drive_01')).toBeTruthy()
  })

  it('selects a named source', async () => {
    const manifest = await load({ manifest_version: 2, table: {}, curve: { suffix: '.h5' } }, [
      'drive_01.h5',
      'drive_01.sensor_2.h5'
    ])
    const path = await manifest.curvePath('drive_01', 'sensor_2')
    expect(path!.endsWith('drive_01.sensor_2.h5')).toBe(true)
  })

  it('yields null for an unknown source', async () => {
    const manifest = await load(V2_MANIFEST, ['drive_01.curve.h5'])
    expect(await manifest.curvePath('drive_01', 'nope')).toBeNull()
  })

  it('yields null for a log with no curves', async () => {
    const manifest = await load(V2_MANIFEST, [])
    expect(await manifest.curvePath('drive_01')).toBeNull()
  })

  it('tracks discovery in hasCurve', async () => {
    const withCurve = await load(V2_MANIFEST, ['drive_01.curve.h5'])
    const without = await load(V2_MANIFEST, [])
    expect(await withCurve.hasCurve('drive_01')).toBe(true)
    expect(await without.hasCurve('drive_01')).toBe(false)
  })
})

describe('imageStreams', () => {
  it('treats a bare stem as the default stream', async () => {
    const manifest = await load(V2_MANIFEST, ['drive_01.mp4'])
    const streams = await manifest.imageStreams('drive_01')
    expect(streams.map((s) => s.id)).toEqual(['image'])
    expect(streams[0]!.label).toBe('Image')
  })

  it('discovers named streams', async () => {
    const manifest = await load(V2_MANIFEST, ['drive_01.mp4', 'drive_01.back.mp4'])
    expect((await manifest.imageStreams('drive_01')).map((s) => s.id)).toEqual([
      'image',
      'back'
    ])
  })

  it('sorts the default stream first', async () => {
    // Alphabetically "back" precedes "image"; the default still leads.
    const manifest = await load(V2_MANIFEST, ['drive_01.back.mp4', 'drive_01.mp4'])
    expect((await manifest.imageStreams('drive_01'))[0]!.id).toBe('image')
  })

  it('prefers mp4 over avi for the same stream', async () => {
    // A log shipped in both containers serves the mp4 and skips the transcode.
    const manifest = await load(V2_MANIFEST, ['drive_01.mp4', 'drive_01.avi'])
    const streams = await manifest.imageStreams('drive_01')
    expect(streams.length).toBe(1)
    expect(streams[0]!.file.endsWith('.mp4')).toBe(true)
  })

  it('serves an avi when it is alone', async () => {
    const manifest = await load(V2_MANIFEST, ['drive_01.avi'])
    const streams = await manifest.imageStreams('drive_01')
    expect(streams[0]!.file.endsWith('.avi')).toBe(true)
  })

  it('does not claim a longer stem', async () => {
    const manifest = await load(V2_MANIFEST, ['drive_01.mp4', 'drive_010.mp4'])
    expect((await manifest.imageStreams('drive_01')).map((s) => s.id)).toEqual(['image'])
  })

  it('yields nothing without an image block', async () => {
    const manifest = await load({ manifest_version: 2, table: {} }, ['drive_01.mp4'])
    expect(await manifest.imageStreams('drive_01')).toEqual([])
  })

  it('tracks discovery in hasImage', async () => {
    const withImage = await load(V2_MANIFEST, ['drive_01.mp4'])
    const without = await load(V2_MANIFEST, [])
    expect(await withImage.hasImage('drive_01')).toBe(true)
    expect(await without.hasImage('drive_01')).toBe(false)
  })
})

describe('tableSidecarSuffixes', () => {
  it('applies the defaults without a manifest', async () => {
    // The picker must still not offer a pose sidecar as a log.
    expect(await tableSidecarSuffixes(makeCase(null))).toEqual(['.reference.parquet'])
  })

  it('includes a custom reference suffix', async () => {
    const dir = makeCase({ manifest_version: 2, table: {}, reference: { suffix: '.pose.parquet' } })
    expect(await tableSidecarSuffixes(dir)).toEqual(['.pose.parquet', '.reference.parquet'])
  })

  it('deduplicates and lowercases', async () => {
    const dir = makeCase({
      manifest_version: 2,
      table: {},
      reference: { suffix: '.REFERENCE.PARQUET' }
    })
    expect(await tableSidecarSuffixes(dir)).toEqual(['.reference.parquet'])
  })
})
