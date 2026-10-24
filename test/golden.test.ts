// The port agrees with the Python it replaced, on real numbers.
//
// A transposed matrix, a degrees-for-radians slip or the wrong rounding rule
// all pass a hand-written test that shares the misunderstanding, and all of
// them show up only as a cloud subtly in the wrong place. The fixture was
// captured from the Python; see `fixtures/README.md`.

import { readFileSync } from 'node:fs'
import { basename, join } from 'node:path'

import { describe, expect, it } from 'vitest'

import { Manifest, normalizeReferenceDisplay } from '../src/data/manifest'
import { Calibration, applyTransform, rotationMatrix } from '../src/shared/calibration'
import { videoFrameFor } from '../src/shared/videoFrame'

interface Golden {
  rotation: Array<{ rpy: [number, number, number]; matrix: number[] }>
  transform: Array<{ translation: number[]; rpy_deg: number[]; points: number[]; result: number[] }>
  video: Array<[number, number, number, number]>
  manifest: Record<string, any>
}

const golden: Golden = JSON.parse(readFileSync(join(__dirname, 'fixtures', 'golden.json'), 'utf8'))

/** Largest absolute difference between two equal-length sequences. */
function worst(a: ArrayLike<number>, b: ArrayLike<number>): number {
  let out = 0
  for (let i = 0; i < b.length; i++) {
    out = Math.max(out, Math.abs(a[i]! - b[i]!))
  }
  return out
}

describe('matches numpy', () => {
  it('rotationMatrix, row-major', () => {
    // A transpose is the failure this is really looking for.
    expect(golden.rotation.length).toBeGreaterThan(0)
    for (const { rpy, matrix } of golden.rotation) {
      expect(worst(rotationMatrix(...rpy), matrix)).toBeLessThan(1e-12)
    }
  })

  it('applyTransform, to float32 precision', () => {
    expect(golden.transform.length).toBeGreaterThan(0)
    for (const entry of golden.transform) {
      const calibration = new Calibration(entry.translation, entry.rpy_deg)
      const out = applyTransform(Float32Array.from(entry.points), calibration)
      expect(worst(out, entry.result)).toBeLessThan(1e-3)
    }
  })
})

it('videoFrameFor agrees exactly with the Python', () => {
  const wrong = golden.video.filter(
    ([local, total, frames, expected]) => videoFrameFor(local, total, frames) !== expected
  )
  expect(wrong).toEqual([])
})

it('the manifest port agrees with the Python on the real case', async () => {
  expect(golden.manifest).not.toBeNull()
  const caseDir = join(__dirname, '..', 'data', 'NuScenes')
  const manifest = await Manifest.load(caseDir)
  const stem = 'scene_0061'
  const strip = (entries: Array<{ id: string; label: string; file: string }>) =>
    entries.map((e) => ({ id: e.id, label: e.label, file: basename(e.file) }))

  const mine = {
    name: manifest.name,
    frame_key: manifest.table.slider,
    cloud_suffix: manifest.cloudSuffix,
    cloud_display: manifest.cloudDisplay(),
    cloud_columns: manifest.cloudColumns(),
    curve_suffixes: manifest.curveSuffixes,
    curve_sources: strip(await manifest.curveSources(stem)),
    curve_plots: manifest.curvePlots(),
    image_streams: strip(await manifest.imageStreams(stem)),
    reference_columns: manifest.referenceColumns(),
    reference_display: normalizeReferenceDisplay(manifest.reference),
    stem_of: manifest.stemOf(join(caseDir, 'scene_0061.parquet'))
  }

  // Compared whole: a key the port forgot is exactly what a per-field list
  // also forgets.
  expect(JSON.parse(JSON.stringify(mine))).toEqual(golden.manifest)
})
