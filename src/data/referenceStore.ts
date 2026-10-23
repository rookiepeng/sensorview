// The reference pose sidecar.
//
// Ports `dataio/reference.py`. The reference overlay -- the host vehicle,
// usually -- can come from a sidecar of its own, `<stem>.reference.parquet`,
// instead of from columns embedded in the table:
//
//     frame | x | y | z | yaw | pitch | roll
//
// One row per frame, positions in meters and angles in radians, keyed on the
// same frame ids the table uses. A sidecar exists because a pose is per
// *frame*, not per detection: carrying six more columns on every one of a
// log's 300k rows to say where one vehicle was in 400 frames is a waste, and
// it cannot express orientation at all -- the table path only ever reads a
// position, so a mesh placed from it sits square to the axes however the
// vehicle is pointing.
//
// Column names are the exporter's, not this app's, so the mapping from file
// column to pose field is configured, in the manifest's `reference.columns`
// block. A file that already names its columns `x`/`yaw`/… needs no mapping.

import pl from 'nodejs-polars'
import { statSync } from 'node:fs'

import { rotationMatrix } from '../shared/calibration'

import { NO_COLUMN } from './manifest'

/**
 * Pose fields in the order the renderer wants them.
 *
 * Position in meters, orientation in radians (ZYX intrinsic: yaw about z,
 * pitch about y, roll about x), matching the convention `shared/calibration`
 * uses for mountings.
 */
export const POSE_FIELDS = ['x', 'y', 'z', 'yaw', 'pitch', 'roll'] as const
export const POSITION_FIELDS = ['x', 'y', 'z'] as const

/**
 * Every field the manifest's `reference.columns` block can map.
 *
 * `frame` is not a pose field -- it is what pairs a sidecar row with a table
 * frame -- but it is just as configurable, so anything keyed on "how is this
 * file mapped" has to count it.
 */
export const MAPPED_FIELDS = [...POSE_FIELDS, 'frame'] as const

export type PoseField = (typeof POSE_FIELDS)[number]
export type Pose = Record<PoseField, number>
export type Extent = Record<(typeof POSITION_FIELDS)[number], [number, number]>

/**
 * Identify one version of a file on disk.
 *
 * @returns `[mtime, size]`, or `[0, -1]` when the file cannot be stat'ed --
 *     distinct from any real file, so an unreadable path never returns a
 *     cached table belonging to a different one.
 */
function fingerprint(path: string): [number, number] {
  try {
    const stat = statSync(path)
    return [stat.mtimeMs, stat.size]
  } catch {
    return [0, -1]
  }
}

/**
 * Normalize a frame id to a stable key.
 *
 * The Python had to fold numpy scalars, ints and floats onto one key because
 * all three hash differently there. Every number here is already a double, so
 * this only has to reject what is not a number at all -- and it keeps the name
 * so the two files still read alike.
 */
function frameKeyOf(value: unknown): number | null {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

export interface ReferenceOptions {
  /**
   * Pose field -> column name, as configured. A field the mapping omits falls
   * back to a column named after the field itself, so a self-describing file
   * needs no configuration; one it names as NO_COLUMN has no column at all.
   */
  columns?: Record<string, string | null>
  /** The table's frame column name, used when the mapping does not name one. */
  frameKey?: string | null
}

/** One log's per-frame reference pose, read from its Parquet sidecar. */
export class ReferenceStore {
  /**
   * The whole sidecar is one row per frame -- a few hundred rows against the
   * table's hundreds of thousands -- so it is read once and kept, rather than
   * re-read on the per-frame path the chunked HDF5 stores use.
   */
  private static cache = new Map<string, ReferenceStore>()

  private frames: Map<number, Pose> = new Map()
  private resolved: Record<string, string | null> = {}
  private columnNames: string[] = []
  private extent: Extent | null = null

  private constructor(
    readonly path: string,
    private readonly columns: Record<string, string | null>,
    private readonly frameKey: string | null
  ) {
    this.load()
  }

  /**
   * Open a sidecar, reusing the parsed table when nothing changed on disk.
   *
   * @returns A store, or null when the file does not exist.
   */
  static open(path: string, options: ReferenceOptions = {}): ReferenceStore | null {
    if (!path) {
      return null
    }
    const [mtime, size] = fingerprint(path)
    if (size < 0) {
      return null
    }

    const columns = options.columns ?? {}
    // The mapping is part of the key: repointing a picker has to re-derive the
    // poses, and a mapping change leaves the file itself untouched. That
    // includes `frame` -- pointing it at another column re-keys every pose in
    // the file, which is the largest change a picker can make, not one to
    // answer out of the cache.
    const key = [
      path,
      options.frameKey ?? null,
      ...MAPPED_FIELDS.map((field) => `${field}=${columns[field] ?? null}`),
      mtime,
      size
    ].join('|')

    const cached = ReferenceStore.cache.get(key)
    if (cached) {
      return cached
    }

    const store = new ReferenceStore(path, columns, options.frameKey ?? null)
    // One log at a time is the norm; a handful covers flipping between logs
    // without letting an all-day session accumulate every case ever opened.
    if (ReferenceStore.cache.size > 8) {
      ReferenceStore.cache.clear()
    }
    ReferenceStore.cache.set(key, store)
    return store
  }

  /** Forget every parsed sidecar. */
  static clearCache(): void {
    ReferenceStore.cache.clear()
  }

  /**
   * Decide which file column feeds each pose field.
   *
   * A field the mapping names as nothing resolves to nothing: the guesses
   * below are for a file nobody has mapped yet, and running them over an
   * explicit choice would make the pickers' empty dropdown inert -- pick it,
   * and the column it was meant to clear comes straight back.
   */
  private resolve(available: string[]): void {
    const lowered = new Map(available.map((name) => [name.toLowerCase(), name]))

    const pick = (field: string): string | null => {
      const configured = this.columns[field]
      if (configured === NO_COLUMN) {
        return null
      }
      if (configured && available.includes(configured)) {
        return configured
      }
      // Unnamed, or named as a column this file does not have: a column named
      // after the field is the obvious intent either way.
      return lowered.get(field) ?? null
    }

    this.resolved = {}
    for (const field of POSE_FIELDS) {
      this.resolved[field] = pick(field)
    }

    let frameColumn = this.columns['frame']
    if (frameColumn === NO_COLUMN) {
      frameColumn = null
    } else if (!frameColumn || !available.includes(frameColumn)) {
      frameColumn = null
      for (const candidate of [this.frameKey, 'frame', 'frame_id', 'frame_idx']) {
        if (!candidate) {
          continue
        }
        if (available.includes(candidate)) {
          frameColumn = candidate
          break
        }
        const insensitive = lowered.get(candidate.toLowerCase())
        if (insensitive) {
          frameColumn = insensitive
          break
        }
      }
    }
    this.resolved['frame'] = frameColumn ?? null
  }

  /** Read the sidecar and index its poses by frame id. */
  private load(): void {
    let table: pl.DataFrame
    try {
      table = pl.readParquet(this.path)
    } catch {
      return
    }

    this.columnNames = table.columns
    this.resolve(this.columnNames)

    const frameColumn = this.resolved['frame']
    if (!frameColumn || !this.isUsable) {
      return
    }

    const frames = table.getColumn(frameColumn).toArray() as unknown[]
    const values: Record<string, number[]> = {}
    for (const field of POSE_FIELDS) {
      const column = this.resolved[field]
      if (!column) {
        values[field] = new Array(frames.length).fill(0)
        continue
      }
      // Angles or positions written as ints read back as ints; the renderer
      // wants floats either way, and a null or a NaN is a zero rather than a
      // hole -- an unrotated reference, not a missing one.
      values[field] = (table.getColumn(column).toArray() as unknown[]).map((raw) => {
        const number = Number(raw)
        return Number.isFinite(number) ? number : 0
      })
    }

    for (let row = 0; row < frames.length; row++) {
      const key = frameKeyOf(frames[row])
      if (key === null) {
        continue
      }
      const pose = {} as Pose
      for (const field of POSE_FIELDS) {
        pose[field] = values[field]![row]!
      }
      this.frames.set(key, pose)
    }
  }

  /**
   * Whether the sidecar carries enough to place a reference.
   *
   * A pose with no x or y column places nothing; z and the three angles all
   * default to zero, which is a flat, unrotated reference rather than a
   * missing one.
   */
  get isUsable(): boolean {
    return Boolean(this.resolved['x'] && this.resolved['y'])
  }

  /** Column names in the sidecar, in file order. */
  get availableColumns(): string[] {
    return [...this.columnNames]
  }

  /** The column actually feeding each pose field, plus `frame`. */
  get resolvedColumns(): Record<string, string | null> {
    return { ...this.resolved }
  }

  /**
   * Read the reference pose for one frame.
   *
   * @returns Every field in POSE_FIELDS, or null when the sidecar has no row
   *     for that frame -- a gap draws nothing rather than stranding the
   *     reference at its last known pose.
   */
  pose(frameId: unknown): Pose | null {
    const key = frameKeyOf(frameId)
    return key === null ? null : (this.frames.get(key) ?? null)
  }

  /**
   * Position extent across every frame in the sidecar.
   *
   * The 3D scene fixes its axis ranges from the table's filter ranges, and a
   * reference that travels beyond them would simply be clipped away, so the
   * ranges have to be widened by what this returns.
   *
   * @returns `{x: [min, max], …}`, or null when the sidecar holds no usable
   *     rows.
   */
  bounds(): Extent | null {
    if (this.extent) {
      return this.extent
    }
    if (this.frames.size === 0) {
      return null
    }

    const extent = {} as Extent
    for (const field of POSITION_FIELDS) {
      let min = Infinity
      let max = -Infinity
      for (const pose of this.frames.values()) {
        const value = pose[field]
        if (value < min) min = value
        if (value > max) max = value
      }
      extent[field] = [min, max]
    }

    this.extent = extent
    return extent
  }
}

/**
 * Place a mesh where a pose puts it.
 *
 * The vertices sit in the reference's own frame, in meters. Without a
 * rotation they are placed by translation alone, which is both cheaper and
 * exactly what the table-column path produced -- a reference read from table
 * columns carries a position and no orientation at all.
 *
 * Triangles are expanded here rather than shipped as vertices plus indices:
 * the mesh is a dozen triangles, the scene draws it as plain geometry, and
 * an index buffer for thirty-six floats is bookkeeping without a payer.
 *
 * @param vertices Mesh vertices, `[[x, y, z], …]`.
 * @param faces Vertex-index triangles.
 * @param pose Where the reference is, or null to leave the mesh as authored.
 * @returns Triangle vertices in world space, three per triangle.
 */
export function poseMesh(
  vertices: number[][],
  faces: number[][],
  pose: Pose | null
): Float32Array {
  const placed = placeVertices(vertices, pose)
  const out = new Float32Array(faces.length * 9)
  faces.forEach((face, f) => {
    for (let corner = 0; corner < 3; corner++) {
      const vertex = placed[face[corner] ?? 0] ?? [0, 0, 0]
      out[f * 9 + corner * 3] = vertex[0]!
      out[f * 9 + corner * 3 + 1] = vertex[1]!
      out[f * 9 + corner * 3 + 2] = vertex[2]!
    }
  })
  return out
}

/**
 * Place a wireframe where a pose puts it.
 *
 * @returns Segment endpoints in world space, two per edge.
 */
export function poseEdges(
  vertices: number[][],
  edges: number[][],
  pose: Pose | null
): Float32Array {
  const placed = placeVertices(vertices, pose)
  const out = new Float32Array(edges.length * 6)
  edges.forEach((edge, e) => {
    for (let end = 0; end < 2; end++) {
      const vertex = placed[edge[end] ?? 0] ?? [0, 0, 0]
      out[e * 6 + end * 3] = vertex[0]!
      out[e * 6 + end * 3 + 1] = vertex[1]!
      out[e * 6 + end * 3 + 2] = vertex[2]!
    }
  })
  return out
}

function placeVertices(vertices: number[][], pose: Pose | null): number[][] {
  if (!pose) {
    return vertices
  }
  const origin = [pose.x, pose.y, pose.z]
  // A level pose is placed by translation alone. Skipping the matrix is
  // cheaper, and it keeps a reference with no orientation exactly where the
  // table-column path put it rather than a rounding away from it.
  if (pose.yaw === 0 && pose.pitch === 0 && pose.roll === 0) {
    return vertices.map((v) => [
      (v[0] ?? 0) + origin[0]!,
      (v[1] ?? 0) + origin[1]!,
      (v[2] ?? 0) + origin[2]!
    ])
  }

  const m = rotationMatrix(pose.roll, pose.pitch, pose.yaw)
  return vertices.map((v) => {
    const [x, y, z] = [v[0] ?? 0, v[1] ?? 0, v[2] ?? 0]
    return [
      m[0] * x + m[1] * y + m[2] * z + origin[0]!,
      m[3] * x + m[4] * y + m[5] * z + origin[1]!,
      m[6] * x + m[7] * y + m[8] * z + origin[2]!
    ]
  })
}
