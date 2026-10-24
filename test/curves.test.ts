// Reading curves, checked against the Python it replaces.
//
// The fixture was captured from the Python (see `fixtures/README.md`) on the real sidecar
// in `data/NuScenes`. The orientation cases are the point: MATLAB writes
// column-major, so the same logical curve reads back as (N, 2) or (2, N), and
// a port that handles only one of them still draws a plausible line from the
// other.

import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { afterAll, describe, expect, it } from 'vitest'

import { closeAll, curveDataset, curveSignals, readCurve, splitXy } from '../src/data/hdf5'

interface Golden {
  path: string
  pattern: string
  signals: string[]
  samples: Array<{
    name: string
    n: number
    hasX: boolean
    // null where the value is NaN: JSON has none, and a bin with no return
    // is a real NaN rather than a zero.
    x: Array<number | null> | null
    y: Array<number | null>
    yLast: number | null
  }>
  orientations: Array<{
    label: string
    shape: number[]
    x: number[] | null
    y: number[]
  }>
}

const golden = JSON.parse(
  readFileSync(join(__dirname, 'fixtures', 'curves.json'), 'utf8')
) as Golden

const PATH = join(__dirname, '..', golden.path)

afterAll(() => closeAll())

describe('splitXy', () => {
  for (const expected of golden.orientations) {
    it(`reads a dataset whose ${expected.label}`, () => {
      // Laid out the way h5wasm hands it over: flat, row-major, with the
      // shape alongside.
      const flat: number[] = []
      if (expected.shape.length === 2) {
        const [rows, cols] = expected.shape as [number, number]
        const source =
          cols === 2
            ? expected.x!.flatMap((x, i) => [x, expected.y[i]!])
            : [...expected.x!, ...expected.y]
        flat.push(...source)
        expect(flat.length).toBe(rows * cols)
      } else {
        flat.push(...expected.y)
      }

      const curve = splitXy(Float32Array.from(flat), expected.shape)
      if (expected.x === null) {
        expect(curve.x).toBeNull()
      } else {
        expect([...curve.x!]).toEqual(expected.x)
      }
      expect([...curve.y]).toEqual(expected.y)
    })
  }
})

describe('curveDataset', () => {
  it('fills the frame and the name into the pattern', () => {
    expect(curveDataset('/frame_{frame_id}/{name}', '7', 'rcs_peak')).toBe(
      '/frame_7/rcs_peak'
    )
  })

  it('fills a sensor id for a file holding several in one tree', () => {
    expect(curveDataset('/{sensor_id}/frame_{frame_id}/{name}', '2', 'y', 'front')).toBe(
      '/front/frame_2/y'
    )
  })
})

describe('a real curve sidecar', () => {
  it('lists the series the Python listed', async () => {
    expect(await curveSignals(PATH, golden.pattern, '0')).toEqual(golden.signals)
  })

  for (const expected of golden.samples) {
    it(`reads ${expected.name} the same`, async () => {
      const curve = await readCurve(PATH, curveDataset(golden.pattern, '0', expected.name))
      expect(curve).not.toBeNull()
      expect(curve!.y.length).toBe(expected.n)
      expect(curve!.x !== null).toBe(expected.hasX)

      if (expected.x) {
        expected.x.forEach((value, i) => expect(curve!.x![i]).toBeCloseTo(value!, 5))
      }
      // NaN has to survive the read rather than being zeroed on the way
      // through: a gap in a range profile is not a return of zero.
      expected.y.forEach((value, i) => {
        if (value === null) {
          expect(curve!.y[i]).toBeNaN()
        } else {
          expect(curve!.y[i]).toBeCloseTo(value, 5)
        }
      })
    })
  }

  it('is null for a frame the file does not have', async () => {
    // A plot whose trace is absent draws the traces that are present.
    expect(await readCurve(PATH, curveDataset(golden.pattern, '99999', 'rcs_peak'))).toBeNull()
  })
})
