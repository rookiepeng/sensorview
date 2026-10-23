// Finding the logs in a case folder.
//
// Recorders often write one folder per run with the same file names inside,
// and put a single info.json above them. Every table under the case folder is
// a log, and the subfolder in its stem keeps same-named runs apart.

import { describe, expect, it } from 'vitest'

import { scanCase } from '../src/data/caseScan'
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
