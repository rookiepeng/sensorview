// The port agrees with the Python it replaces, on real numbers.
//
// The transliterated suites check the port against the spec as I read it.
// This checks it against the implementation being replaced, which is a
// different question: a transposed matrix, a degrees-for-radians slip or the
// wrong rounding rule all pass a hand-written test that shares the
// misunderstanding, and all of them show up only as a cloud that is subtly in
// the wrong place.
//
// `test/fixtures/golden.json` was captured by `scripts/golden.py` from the
// Python, seeded so re-running it produces the same file. Both go when the
// Python does -- at which point these numbers stop being a cross-check and
// become an ordinary regression fixture, which is still worth having.

import { readFileSync } from 'node:fs'
import { basename, join } from 'node:path'

import { describe, expect, it } from 'vitest'

import { Manifest, normalizeReferenceDisplay } from '../src/data/manifest'
import { Calibration, applyTransform, rotationMatrix } from '../src/shared/calibration'
import { videoFrameFor } from '../src/shared/videoFrame'

interface Golden {
  rotation: Array<{ rpy: [number, number, number]; matrix: number[] }>
  transform: Array<{
    translation: number[]
    rpy_deg: number[]
    points: number[]
    result: number[]
  }>
  video: Array<[number, number, number, number]>
  manifest: Record<string, any> | null
}

const golden: Golden = JSON.parse(
  readFileSync(join(__dirname, 'fixtures', 'golden.json'), 'utf8')
)

describe('rotationMatrix matches numpy', () => {
  it('has cases to check', () => {
    expect(golden.rotation.length).toBeGreaterThan(100)
  })

  it('agrees on every case', () => {
    // Row-major on both sides. A transpose is the failure this is really
    // looking for, and it survives every symmetry test a hand-written case
    // would use.
    let worst = 0
    for (const { rpy, matrix } of golden.rotation) {
      const mine = rotationMatrix(rpy[0], rpy[1], rpy[2])
      for (let i = 0; i < 9; i++) {
        worst = Math.max(worst, Math.abs(mine[i]! - matrix[i]!))
      }
    }
    expect(worst).toBeLessThan(1e-12)
  })
})

describe('applyTransform matches numpy', () => {
  it('agrees on every case', () => {
    let worst = 0
    for (const entry of golden.transform) {
      const calibration = new Calibration(entry.translation, entry.rpy_deg)
      const out = applyTransform(Float32Array.from(entry.points), calibration)
      for (let i = 0; i < entry.result.length; i++) {
        worst = Math.max(worst, Math.abs(out[i]! - entry.result[i]!))
      }
    }
    // The Python works in float64 and this stores float32, which is the same
    // narrowing the renderer does anyway -- so the tolerance is float32
    // precision over coordinates up to 50, not a fudge factor.
    expect(worst).toBeLessThan(1e-3)
  })
})

describe('videoFrameFor matches Python', () => {
  it('agrees exactly on every case', () => {
    // Integers, so this is exact or it is wrong. The half-up rule is the one
    // that matters and the one a rewrite would change.
    const wrong = golden.video.filter(
      ([local, total, frames, expected]) => videoFrameFor(local, total, frames) !== expected
    )
    expect(wrong).toEqual([])
  })
})

describe('the manifest port agrees with Python on the real case', () => {
  const expected = golden.manifest

  it('has a captured manifest to check against', () => {
    // Guards the premise: without the case present the generator writes null,
    // and every assertion below would vacuously pass.
    expect(expected).not.toBeNull()
  })

  it('agrees on every normalized block', async () => {
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

    // Compared whole rather than field by field: a key the port forgot to
    // normalize is exactly the kind of omission a per-field assertion list
    // also forgets.
    expect(JSON.parse(JSON.stringify(mine))).toEqual(expected)
  })
})
