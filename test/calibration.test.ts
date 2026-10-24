// Sensor extrinsics: ZYX intrinsic, x forward, y left, z up.
//
// A silent change to the multiplication order still produces plausible
// clouds that are wrong, so the convention is pinned explicitly. The bulk
// numeric check against numpy is in golden.test.ts.

import { describe, expect, it } from 'vitest'

import {
  Calibration,
  applyTransform,
  rotate,
  rotationMatrix,
  type Vec3
} from '../src/shared/calibration'

function expectVec(actual: ArrayLike<number>, expected: Vec3, tol = 1e-9) {
  expected.forEach((v, i) => expect(Math.abs(actual[i]! - v)).toBeLessThan(tol))
}

const Q = Math.PI / 2

describe('rotationMatrix', () => {
  it.each([
    ['no rotation leaves a vector alone', [0, 0, 0], [1, 2, 3], [1, 2, 3]],
    ['yaw turns forward to left', [0, 0, Q], [1, 0, 0], [0, 1, 0]],
    ['roll turns left to up', [Q, 0, 0], [0, 1, 0], [0, 0, 1]],
    ['pitch turns forward to down', [0, Q, 0], [1, 0, 0], [0, 0, -1]],
    // Rz(yaw) @ Ry(pitch) @ Rx(roll). The reverse order gives [-1, 0, 0].
    ['composes as ZYX', [Q, 0, Q], [0, 1, 0], [0, 0, 1]]
  ] as Array<[string, Vec3, Vec3, Vec3]>)('%s', (_, [roll, pitch, yaw], input, expected) => {
    expectVec(rotate(rotationMatrix(roll, pitch, yaw), input), expected)
  })
})

describe('Calibration', () => {
  it('is the identity only when nothing is declared', () => {
    expect(new Calibration().isIdentity).toBe(true)
    expect(Calibration.fromDict(null).isIdentity).toBe(true)
    expect(Calibration.fromDict({}).isIdentity).toBe(true)
    expect(new Calibration([1, 0, 0]).isIdentity).toBe(false)
    expect(new Calibration(null, [0, 0, 90]).isIdentity).toBe(false)
  })

  it('reads rotation in degrees', () => {
    expectVec(rotate(new Calibration(null, [0, 0, 90]).rotationMatrix(), [1, 0, 0]), [0, 1, 0])
  })

  it('pads a short or missing vector with zeros', () => {
    expect(new Calibration([5]).translation).toEqual([5, 0, 0])
    expect(new Calibration(null, []).rpy).toEqual([0, 0, 0])
  })
})

describe('applyTransform', () => {
  it('returns the input itself for the identity', () => {
    const points = new Float32Array([1, 2, 3])
    expect(applyTransform(points, new Calibration())).toBe(points)
  })

  it('rotates then translates, every point', () => {
    // Translating first would give [0, 11, 0] for the first point.
    const out = applyTransform(
      new Float32Array([1, 0, 0, 0, 1, 0]),
      new Calibration([10, 0, 0], [0, 0, 90])
    )
    expectVec(out.subarray(0, 3), [10, 1, 0], 1e-5)
    expectVec(out.subarray(3, 6), [9, 0, 0], 1e-5)
  })
})
