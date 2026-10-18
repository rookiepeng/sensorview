// Reading the cloud and curve sidecars.
//
// HDF5 through h5wasm, which is the HDF5 C library compiled to WebAssembly --
// so the gzip-chunked float32 these files use is handled by the same code
// h5py was calling, not a reimplementation of the format.
//
// Handles are kept open here, unlike `dense_store.py`, which reopened per read
// because Dash's background callbacks ran in forked processes that could not
// share one. There is one process now.

import type { File as H5File } from 'h5wasm/node'

type H5 = typeof import('h5wasm/node')

let h5: H5 | null = null

/** Load the WASM once. Every read waits on this. */
async function library(): Promise<H5> {
  if (!h5) {
    const module = await import('h5wasm/node')
    await module.ready
    h5 = module
  }
  return h5
}

const open = new Map<string, H5File>()

async function file(path: string): Promise<H5File> {
  const cached = open.get(path)
  if (cached) {
    return cached
  }
  const module = await library()
  const handle = new module.File(path, 'r')
  open.set(path, handle)
  return handle
}

/** Close every open handle. Called when a case is closed. */
export function closeAll(): void {
  for (const handle of open.values()) {
    handle.close()
  }
  open.clear()
}

/**
 * The dataset path for a frame id.
 *
 * Deliberately matches Python's `str()`, because the ids were written with it:
 * an integral float wrote `/frame_3.0`, not `/frame_3`. JavaScript's `String`
 * drops the `.0`, so a float frame column would send the two languages looking
 * for different datasets -- and the one that is wrong finds nothing and
 * renders an empty frame rather than failing.
 *
 * @param id Frame id.
 * @param isFloat Whether the table's frame column is floating point.
 */
export function hdf5Id(id: number, isFloat = false): string {
  if (!isFloat || !Number.isInteger(id)) {
    return String(id)
  }
  return `${id}.0`
}

/**
 * Resolve which columns of a cloud dataset are x, y and z.
 *
 * Three passes, in the order `dense_store.py` used them: the manifest's own
 * mapping wins; then a `columns` attribute written beside the data; then the
 * leftmost three columns. A file that declares nothing is still readable,
 * which is the common case for an exporter that wrote a bare (N, 3).
 *
 * @param declared Mapping from the manifest, by field name.
 * @param attr The dataset's or file's `columns` attribute.
 * @param width How many columns the dataset has.
 */
export function xyzIndices(
  declared: Partial<Record<'x' | 'y' | 'z', string | number>> | null,
  attr: string[] | null,
  width: number
): [number, number, number] {
  const axes = ['x', 'y', 'z'] as const
  const found: Array<number | null> = [null, null, null]

  // Pass one: the manifest, by name against the attribute or by position.
  axes.forEach((axis, i) => {
    const want = declared?.[axis]
    if (want === undefined || want === null) {
      return
    }
    if (typeof want === 'number') {
      found[i] = want
      return
    }
    const at = attr?.indexOf(want) ?? -1
    if (at >= 0) {
      found[i] = at
    }
  })

  // Pass two: the attribute's own names.
  axes.forEach((axis, i) => {
    if (found[i] !== null) {
      return
    }
    const at = attr?.indexOf(axis) ?? -1
    if (at >= 0) {
      found[i] = at
    }
  })

  // Pass three: whatever positions are left, in order.
  const taken = new Set(found.filter((v): v is number => v !== null))
  let next = 0
  for (let i = 0; i < 3; i++) {
    if (found[i] !== null) {
      continue
    }
    while (taken.has(next) && next < width) {
      next++
    }
    found[i] = Math.min(next, Math.max(0, width - 1))
    taken.add(found[i]!)
    next++
  }

  return [found[0]!, found[1]!, found[2]!]
}

export interface CloudFrame {
  /** Interleaved xyz. */
  position: Float32Array
  count: number
}

/**
 * Read one cloud frame as interleaved xyz.
 *
 * The slice is built here rather than in the renderer so only the three
 * columns that are drawn cross the process boundary -- a cloud with intensity
 * and ring columns is half again as large as the points in it.
 */
export async function readCloudFrame(
  path: string,
  dataset: string,
  declared: Partial<Record<'x' | 'y' | 'z', string | number>> | null = null
): Promise<CloudFrame | null> {
  const handle = await file(path)
  const node = handle.get(dataset)
  if (!node || !('shape' in node) || !node.shape) {
    return null
  }

  const [rows, width = 1] = node.shape as number[]
  if (!rows) {
    return null
  }

  const attr = handle.attrs?.columns?.value as string[] | undefined
  const [ix, iy, iz] = xyzIndices(declared, attr ?? null, width)

  const raw = node.value as Float32Array | Float64Array
  const position = new Float32Array(rows * 3)
  for (let r = 0; r < rows; r++) {
    const base = r * width
    position[r * 3] = raw[base + ix]!
    position[r * 3 + 1] = raw[base + iy]!
    position[r * 3 + 2] = raw[base + iz]!
  }
  return { position, count: rows }
}

/** Frame dataset names present in a cloud file. */
export async function cloudFrames(path: string): Promise<string[]> {
  const handle = await file(path)
  return handle.keys()
}
