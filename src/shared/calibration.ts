// Sensor extrinsics.
//
// A mounting description -- translation plus roll/pitch/yaw -- becomes a 4x4
// homogeneous transform, so clouds from different sensors land in the same
// reference frame when overlaid.
//
// The convention is ZYX intrinsic (yaw, then pitch, then roll): x forward,
// y left, z up, which is the usual automotive one. It is stated here and
// pinned by tests because the wrong multiplication order still produces a
// plausible-looking cloud -- just one that is wrong, in a way nothing on
// screen would flag.

/** A 3x3 matrix, row-major. */
export type Matrix3 = [number, number, number, number, number, number, number, number, number]

export type Vec3 = [number, number, number]

/**
 * Build a rotation matrix from roll/pitch/yaw in radians.
 *
 * @returns `Rz(yaw) @ Ry(pitch) @ Rx(roll)`, row-major.
 */
export function rotationMatrix(roll: number, pitch: number, yaw: number): Matrix3 {
  const cr = Math.cos(roll)
  const sr = Math.sin(roll)
  const cp = Math.cos(pitch)
  const sp = Math.sin(pitch)
  const cy = Math.cos(yaw)
  const sy = Math.sin(yaw)

  // Written out rather than composed from three matrices: the product is
  // fixed, and multiplying three of them per call to recover it is both
  // slower and one more place for the order to be wrong.
  return [
    cy * cp,
    cy * sp * sr - sy * cr,
    cy * sp * cr + sy * sr,
    sy * cp,
    sy * sp * sr + cy * cr,
    sy * sp * cr - cy * sr,
    -sp,
    cp * sr,
    cp * cr
  ]
}

/** Apply a row-major 3x3 to a vector. */
export function rotate(matrix: Matrix3, v: Vec3): Vec3 {
  return [
    matrix[0] * v[0] + matrix[1] * v[1] + matrix[2] * v[2],
    matrix[3] * v[0] + matrix[4] * v[1] + matrix[5] * v[2],
    matrix[6] * v[0] + matrix[7] * v[1] + matrix[8] * v[2]
  ]
}

export interface CalibrationSpec {
  translation?: number[] | null
  /** Roll, pitch, yaw, in **degrees** -- as the manifest writes them. */
  rotation_rpy_deg?: number[] | null
}

const DEG = Math.PI / 180

/** A sensor's mounting transform relative to the vehicle frame. */
export class Calibration {
  readonly translation: Vec3
  readonly rpy: Vec3

  constructor(translation?: number[] | null, rotationRpyDeg?: number[] | null) {
    this.translation = triple(translation)
    this.rpy = triple(rotationRpyDeg)
  }

  static fromDict(spec: CalibrationSpec | null | undefined): Calibration {
    return new Calibration(spec?.translation, spec?.rotation_rpy_deg)
  }

  /**
   * Whether this transform does nothing.
   *
   * Checked rather than applied: the identity case is the common one, and
   * skipping it saves a pass over every point of every frame.
   */
  get isIdentity(): boolean {
    return this.translation.every((v) => v === 0) && this.rpy.every((v) => v === 0)
  }

  rotationMatrix(): Matrix3 {
    const [roll, pitch, yaw] = this.rpy
    return rotationMatrix(roll * DEG, pitch * DEG, yaw * DEG)
  }
}

function triple(values?: number[] | null): Vec3 {
  const v = values ?? []
  return [Number(v[0] ?? 0), Number(v[1] ?? 0), Number(v[2] ?? 0)]
}

/**
 * Transform interleaved xyz in place-compatible fashion.
 *
 * @param points Interleaved xyz, `count * 3` long.
 * @param calibration The sensor's mounting transform.
 * @returns The same array when the transform is the identity, a new one
 *     otherwise. Callers must not assume a copy.
 */
export function applyTransform(
  points: Float32Array,
  calibration: Calibration
): Float32Array {
  if (calibration.isIdentity) {
    return points
  }

  const m = calibration.rotationMatrix()
  const [tx, ty, tz] = calibration.translation
  const out = new Float32Array(points.length)

  for (let i = 0; i < points.length; i += 3) {
    const x = points[i]!
    const y = points[i + 1]!
    const z = points[i + 2]!
    out[i] = m[0] * x + m[1] * y + m[2] * z + tx
    out[i + 1] = m[3] * x + m[4] * y + m[5] * z + ty
    out[i + 2] = m[6] * x + m[7] * y + m[8] * z + tz
  }
  return out
}
