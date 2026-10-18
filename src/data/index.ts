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
import { readCloudFrame } from './hdf5'

type Handler = (params: any) => Promise<Result<unknown>> | Result<unknown>

const handlers: Record<DataMethod, Handler> = {
  ping: () => ok({ pid: process.pid }),

  frameIds: ({ path, frameKey }) => ok(frameIds(path, frameKey)),

  readTable: ({ path, columns }) => ok(readTable(path, columns)),

  cloudFrame: async ({ path, dataset }) => ok(await readCloudFrame(path, dataset))
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
