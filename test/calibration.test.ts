// Sensor extrinsics.
//
// Transliterated from tests/test_calibration.py. Overlaid point clouds only
// line up if every sensor's mounting transform agrees on one convention: ZYX
// intrinsic, x forward, y left, z up. A silent change to the multiplication
// order would still produce plausible-looking clouds that are wrong, so the
// composition order is pinned explicitly rather than assumed.

import { describe, expect, it } from 'vitest'

import {
  Calibration,
  applyTransform,
  rotate,
  rotationMatrix,
  type Vec3
} from '../src/shared/calibration'

const TOL = 1e-12

function expectVec(actual: Vec3, expected: Vec3, tol = TOL) {
  actual.forEach((v, i) => expect(Math.abs(v - expected[i]!)).toBeLessThan(tol))
}

describe('rotationMatrix', () => {
  it('is the identity for no rotation', () => {
    const m = rotationMatrix(0, 0, 0)
    const identity = [1, 0, 0, 0, 1, 0, 0, 0, 1]
    m.forEach((v, i) => expect(Math.abs(v - identity[i]!)).toBeLessThan(TOL))
  })

  it('turns forward to left with yaw', () => {
    // +90 deg about z takes x forward onto y left.
    expectVec(rotate(rotationMatrix(0, 0, Math.PI / 2), [1, 0, 0]), [0, 1, 0])
  })

  it('turns left to up with roll', () => {
    expectVec(rotate(rotationMatrix(Math.PI / 2, 0, 0), [0, 1, 0]), [0, 0, 1])
  })

  it('turns forward to down with pitch', () => {
    expectVec(rotate(rotationMatrix(0, Math.PI / 2, 0), [1, 0, 0]), [0, 0, -1])
  })

  it('composes as ZYX', () => {
    // Rz(yaw) @ Ry(pitch) @ Rx(roll). Applying roll first sends y up to z up,
    // which yaw then leaves alone. The reverse order gives [-1, 0, 0], so this
    // value is what distinguishes the two conventions.
    expectVec(rotate(rotationMatrix(Math.PI / 2, 0, Math.PI / 2), [0, 1, 0]), [0, 0, 1])
  })

  it('is orthonormal with unit determinant', () => {
    const m = rotationMatrix(0.3, -0.7, 1.1)
    const det =
      m[0] * (m[4] * m[8] - m[5] * m[7]) -
      m[1] * (m[3] * m[8] - m[5] * m[6]) +
      m[2] * (m[3] * m[7] - m[4] * m[6])
    expect(Math.abs(det - 1)).toBeLessThan(1e-12)

    // Rows are unit length and mutually perpendicular.
    const rows: Vec3[] = [
      [m[0], m[1], m[2]],
      [m[3], m[4], m[5]],
      [m[6], m[7], m[8]]
    ]
    for (let i = 0; i < 3; i++) {
      for (let j = 0; j < 3; j++) {
        const dot = rows[i]![0] * rows[j]![0] + rows[i]![1] * rows[j]![1] + rows[i]![2] * rows[j]![2]
        expect(Math.abs(dot - (i === j ? 1 : 0))).toBeLessThan(1e-12)
      }
    }
  })
})

describe('Calibration', () => {
  it('is the identity when nothing is declared', () => {
    expect(new Calibration().isIdentity).toBe(true)
    expect(Calibration.fromDict(null).isIdentity).toBe(true)
    expect(Calibration.fromDict({}).isIdentity).toBe(true)
  })

  it('is not the identity with a translation', () => {
    expect(new Calibration([1, 0, 0]).isIdentity).toBe(false)
  })

  it('is not the identity with a rotation', () => {
    expect(new Calibration(null, [0, 0, 90]).isIdentity).toBe(false)
  })

  it('reads rotation in degrees', () => {
    // The manifest writes degrees; the matrix is built in radians. Getting
    // this wrong is a rotation of about 57 times too much, which is obvious --
    // unlike getting the order wrong.
    const c = new Calibration(null, [0, 0, 90])
    expectVec(rotate(c.rotationMatrix(), [1, 0, 0]), [0, 1, 0], 1e-9)
  })

  it('pads a short or missing vector with zeros', () => {
    expect(new Calibration([5]).translation).toEqual([5, 0, 0])
    expect(new Calibration(null, []).rpy).toEqual([0, 0, 0])
  })
})

describe('applyTransform', () => {
  it('returns the input untouched for the identity', () => {
    // The fast path matters: it is skipped once per frame per cloud, and the
    // identity is the common case.
    const points = new Float32Array([1, 2, 3])
    expect(applyTransform(points, new Calibration())).toBe(points)
  })

  it('translates', () => {
    const out = applyTransform(new Float32Array([1, 2, 3]), new Calibration([10, 20, 30]))
    expectVec([out[0]!, out[1]!, out[2]!], [11, 22, 33], 1e-5)
  })

  it('rotates then translates, not the other way round', () => {
    // Translating first would put the point at [11, 0, 0] and then rotate it
    // to [0, 11, 0]. Rotating first gives [0, 1, 0] + [10, 0, 0].
    const out = applyTransform(new Float32Array([1, 0, 0]), new Calibration([10, 0, 0], [0, 0, 90]))
    expectVec([out[0]!, out[1]!, out[2]!], [10, 1, 0], 1e-5)
  })

  it('transforms every point', () => {
    const out = applyTransform(new Float32Array([1, 0, 0, 0, 1, 0]), new Calibration([1, 1, 1]))
    expect(Array.from(out).map((v) => Math.round(v))).toEqual([2, 1, 1, 1, 2, 1])
  })

  it('leaves an empty array alone', () => {
    expect(applyTransform(new Float32Array(0), new Calibration([1, 1, 1])).length).toBe(0)
  })
})
