// Finding the logs in a case folder.
//
// Recorders often write one folder per run with the same file names inside,
// and put a single info.json above them. Every table under the case folder is
// a log, and the subfolder in its stem keeps same-named runs apart.

import { writeFileSync } from 'node:fs'
import { join } from 'node:path'

import pl from 'nodejs-polars'
import { describe, expect, it } from 'vitest'

import { scanCase } from '../src/data/caseScan'
import { Manifest } from '../src/data/manifest'
import { ReferenceStore } from '../src/data/referenceStore'
import { V2_MANIFEST, makeCase } from './helpers/makeCase'

describe('scanCase', () => {
  it('lists top-level logs by bare stem', async () => {
    const dir = makeCase(V2_MANIFEST, ['b.parquet', 'a.parquet'])
    const summary = await scanCase(dir)
    expect(summary.logs.map((log) => log.stem)).toEqual(['a', 'b'])
  })

  it('finds logs in subfolders and keeps same-named runs apart', async () => {
    const dir = makeCase(V2_MANIFEST, [
      'run_2/radar.parquet',
      'run_1/radar.parquet',
      'run_1/radar.cloud.h5',
      'run_1/nested/deep/radar.parquet'
    ])
    const summary = await scanCase(dir)
    expect(summary.logs.map((log) => log.stem)).toEqual([
      'run_1/nested/deep/radar',
      'run_1/radar',
      'run_2/radar'
    ])
    const run1 = summary.logs.find((log) => log.stem === 'run_1/radar')!
    const run2 = summary.logs.find((log) => log.stem === 'run_2/radar')!
    expect(run1.hasCloud).toBe(true)
    expect(run2.hasCloud).toBe(false)
  })

  it('skips reference poses and hidden folders', async () => {
    const dir = makeCase(V2_MANIFEST, [
      'run_1/radar.parquet',
      'run_1/radar.reference.parquet',
      '.cache/radar.parquet'
    ])
    const summary = await scanCase(dir)
    expect(summary.logs.map((log) => log.stem)).toEqual(['run_1/radar'])
  })
})

describe('a reference pose beside a log in a subfolder', () => {
  it('loads with the column names info.json maps', async () => {
    // The layout and mapping of a recorder that writes one folder per run.
    const manifest = {
      ...V2_MANIFEST,
      reference: {
        suffix: '.reference.parquet',
        columns: {
          frame: 'frame_id',
          x: 'Longitude',
          y: 'Latitude',
          z: 'Height',
          yaw: 'Yaw',
          pitch: 'Pitch',
          roll: 'Roll'
        }
      }
    }
    const dir = makeCase(manifest, ['run_1/radar.parquet'])
    const pose = pl.DataFrame({
      frame_id: [0, 1],
      Longitude: [1.5, 2.5],
      Latitude: [-3, -4],
      Height: [0.25, 0.5],
      Yaw: [10, 20],
      Pitch: [1, 2],
      Roll: [-1, -2],
      // Decoys a guess would reach for if the mapping were ignored.
      x: [99, 99],
      frame: [7, 8]
    })
    pose.writeParquet(join(dir, 'run_1', 'radar.reference.parquet'))
    writeFileSync(join(dir, 'run_1', 'radar.parquet'), '')

    const summary = await scanCase(dir)
    expect(summary.logs.map((log) => [log.stem, log.hasReference])).toEqual([
      ['run_1/radar', true]
    ])

    const loaded = await Manifest.load(dir)
    const store = ReferenceStore.open(loaded.referencePath('run_1/radar')!, {
      columns: loaded.referenceColumns(),
      frameKey: loaded.frameKey
    })!
    expect(store.resolvedColumns).toMatchObject({
      frame: 'frame_id',
      x: 'Longitude',
      y: 'Latitude',
      z: 'Height',
      yaw: 'Yaw',
      pitch: 'Pitch',
      roll: 'Roll'
    })
    expect(store.pose(1)).toMatchObject({ x: 2.5, y: -4, z: 0.5, yaw: 20, pitch: 2, roll: -2 })
  })
})
