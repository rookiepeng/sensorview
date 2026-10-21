// The data layer, in its own process.
//
// Everything that reads a file lives here: Parquet through polars, HDF5
// through h5wasm, video through ffmpeg. None of it is loaded yet -- this is
// the dispatch skeleton, and each reader is added beside `ping` as it lands.
//
// The shape is a plain method table rather than one channel per reader, so a
// new reader touches `DataMethods` in src/shared/types.ts, the table below,
// and nothing in between.

import type { DataMethod, Result } from '../shared/types'
import { fail, ok } from '../shared/types'
import { frameIds, readTable } from './parquet'
import { curveDataset, hdf5Id, readCloudFrame, readCurve } from './hdf5'
import { Manifest } from './manifest'
import { scanCase } from './caseScan'
import { poseEdges, poseMesh, ReferenceStore } from './referenceStore'
import { playableFile, streamFrameCount } from './video'

type Handler = (params: any) => Promise<Result<unknown>> | Result<unknown>

const handlers: Record<DataMethod, Handler> = {
  ping: () => ok({ pid: process.pid }),

  frameIds: ({ path, frameKey }) => ok(frameIds(path, frameKey)),

  readTable: ({ path, columns }) => ok(readTable(path, columns)),

  cloudFrame: async ({ path, dataset }) => ok(await readCloudFrame(path, dataset)),

  scanCase: async ({ dir }) => ok(await scanCase(dir)),

  logCloudFrame: async ({ dir, stem, frameId }) => {
    const manifest = await Manifest.load(dir)
    const path = manifest.cloudPath(stem)
    if (!path) {
      return ok(null)
    }
    const dataset = manifest
      .cloudDatasetPattern()
      .replace('{frame_id}', hdf5Id(frameId))
      .replace(/^\//, '')
    return ok(await readCloudFrame(path, dataset, manifest.cloudColumns()))
  },

  logFrameOwners: async ({ dir, stems }) => {
    const manifest = await Manifest.load(dir)
    const owners: Record<string, string[]> = {}
    for (const stem of stems) {
      // The table beside the stem, by the manifest's own suffix -- the same
      // path `scanCase` listed it from.
      const path = manifest.tablePath(stem)
      if (!path) {
        continue
      }
      for (const id of frameIds(path, manifest.frameKey)) {
        const key = String(id)
        ;(owners[key] ??= []).push(stem)
      }
    }
    return ok(owners)
  },

  logImageStreams: async ({ dir, stem }) => {
    const manifest = await Manifest.load(dir)
    const streams = await manifest.imageStreams(stem)
    const resolved = []
    for (const stream of streams) {
      // Resolving can transcode, so it happens one at a time rather than as a
      // fan-out: five recordings encoding at once would saturate the machine
      // for a panel showing one of them.
      const file = await playableFile(stream.file)
      if (!file) {
        continue
      }
      resolved.push({
        id: stream.id,
        label: stream.label,
        file,
        // Measured off the source, not the transcode: the two are
        // frame-for-frame, and probing the source avoids forcing an encode
        // just to answer this.
        frames: await streamFrameCount(stream.file)
      })
    }
    return ok(resolved)
  },

  logCurveSources: async ({ dir, stems }) => {
    const manifest = await Manifest.load(dir)
    const seen = new Map<string, { id: string; label: string }>()
    for (const stem of stems) {
      for (const source of await manifest.curveSources(stem)) {
        if (!seen.has(source.id)) {
          seen.set(source.id, { id: source.id, label: source.label })
        }
      }
    }
    return ok([...seen.values()])
  },

  logCurves: async ({ dir, stem, sourceId, frameId }) => {
    const manifest = await Manifest.load(dir)
    const path = await manifest.curvePath(stem, sourceId)
    if (!path) {
      return ok([])
    }

    const id = hdf5Id(frameId)
    const plots = []
    for (const plot of manifest.curvePlots()) {
      const traces = []
      for (const trace of (plot.traces ?? []) as Dict[]) {
        // `curvePlots` has already filled `{name}` and left `{frame_id}`
        // standing, because a plot definition is per log and the frame is
        // per read. Filling it here is what makes the dataset addressable.
        const dataset = curveDataset(trace.dataset as string, id)
        const curve = await readCurve(path, dataset.replace(/^\//, ''))
        if (!curve) {
          // A plot whose trace is absent for this frame draws the traces that
          // are present, rather than going blank.
          continue
        }
        traces.push({
          name: trace.name as string,
          label: (trace.label as string) ?? (trace.name as string),
          color: trace.color as string | undefined,
          dash: trace.dash as string | undefined,
          width: trace.width as number | undefined,
          x: curve.x,
          y: curve.y
        })
      }
      if (traces.length > 0) {
        plots.push({
          id: plot.id as string,
          rangeKey: plot.id as string,
          label: (plot.label as string) ?? (plot.id as string),
          xLabel: (plot.x_label as string) ?? '',
          yLabel: (plot.y_label as string) ?? '',
          traces
        })
      }
    }
    return ok(plots)
  },

  logReference: async ({ dir, stem, frameId }) => {
    const { store, display } = await openReference(dir, stem)
    const pose = store?.pose(frameId) ?? null
    if (!store || !pose) {
      return ok(null)
    }

    const vertices = (display.vertices as number[][]) ?? []
    const faces = (display.faces as number[][]) ?? []
    const edges = (display.edges as number[][]) ?? []

    return ok({
      pose,
      mesh: faces.length > 0 ? poseMesh(vertices, faces, pose) : null,
      edges: edges.length > 0 ? poseEdges(vertices, edges, pose) : null,
      name: (display.name as string) ?? 'Reference',
      color: (display.color as string) ?? '#ffffff',
      opacity: (display.opacity as number) ?? 0.3,
      edgeColor: (display.edge_color as string) ?? '#ffffff',
      edgeWidth: (display.edge_width as number) ?? 1
    })
  },

  logReferenceBounds: async ({ dir, stems }) => {
    let merged: Record<string, [number, number]> | null = null
    for (const stem of stems) {
      const { store } = await openReference(dir, stem)
      const bounds = store?.bounds()
      if (!bounds) {
        continue
      }
      if (!merged) {
        merged = { ...bounds }
        continue
      }
      for (const axis of ['x', 'y', 'z'] as const) {
        const have = merged[axis]!
        merged[axis] = [Math.min(have[0], bounds[axis][0]), Math.max(have[1], bounds[axis][1])]
      }
    }
    return ok(merged as never)
  }
}

type Dict = Record<string, unknown>

/** Open a log's reference sidecar with the mapping the manifest configured. */
async function openReference(
  dir: string,
  stem: string
): Promise<{ store: ReferenceStore | null; display: Dict }> {
  const manifest = await Manifest.load(dir)
  const path = manifest.referencePath(stem)
  return {
    store: path
      ? ReferenceStore.open(path, {
          columns: manifest.referenceColumns(),
          frameKey: manifest.frameKey
        })
      : null,
    display: manifest.referenceDisplay() as Dict
  }
}

interface Call {
  id: number
  method: DataMethod
  params: never
}

process.parentPort.on('message', (event) => {
  const [port] = event.ports
  if (!port) {
    return
  }

  port.on('message', async (message) => {
    const { id, method, params } = message.data as Call

    const handler = handlers[method]
    if (!handler) {
      port.postMessage({ id, result: fail(404, `unknown method: ${method}`) })
      return
    }

    try {
      port.postMessage({ id, result: await handler(params) })
    } catch (error) {
      // A reader throwing is a failed read, not a crashed process. The one
      // thing that must not happen is this process dying and taking every
      // other in-flight call with it.
      port.postMessage({ id, result: fail(500, String(error)) })
    }
  })
  port.start()
})
