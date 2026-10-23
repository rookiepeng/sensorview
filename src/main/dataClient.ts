// The main process's handle on the data layer.
//
// `src/data` runs in its own OS process, forked here. Three reasons it is not
// simply a module in this one:
//
//   - The Parquet reader is a native addon and the HDF5 reader is a WASM
//     compile. Both on the startup path of the process that pumps the window's
//     IPC means a visible stall on first open.
//   - A long collect() is hundreds of milliseconds of blocked event loop, and
//     this event loop owns the window chrome.
//   - A native fault in a worker thread takes its host down with it. A separate
//     process costs a reload of the data layer instead of the app.
//
// The cost is this file. Everything crossing it is one `call(method, params)`,
// typed by the same interface the preload is annotated with, so neither side
// can tell there is an extra hop -- and if the utility process ever proves
// unnecessary, this class is the only thing that changes.

import { utilityProcess, type MessageChannelMain, type UtilityProcess } from 'electron'
import { MessageChannelMain as Channel } from 'electron'
import { join } from 'node:path'

import { fail, type DataMethod, type DataParams, type DataResult, type Result } from '../shared/types'

// A call that has not answered in this long is treated as lost. Generous,
// because a first Parquet read includes loading the addon.
const CALL_TIMEOUT_MS = 30_000

interface Pending {
  resolve: (value: Result<unknown>) => void
  timer: NodeJS.Timeout
}

export class DataClient {
  private child: UtilityProcess | null = null
  private channel: MessageChannelMain | null = null
  private pending = new Map<number, Pending>()
  private nextId = 1

  constructor(private readonly entry: string) {}

  /**
   * Start the data process, or restart it after a crash.
   *
   * Idempotent: calling it when the child is already up is a no-op, which is
   * what lets `call()` use it as a lazy starter.
   */
  start(): void {
    if (this.child) {
      return
    }

    const channel = new Channel()
    const child = utilityProcess.fork(this.entry, [], {
      serviceName: 'sensorview-data',
      stdio: 'inherit'
    })

    child.postMessage({ type: 'port' }, [channel.port2])

    channel.port1.on('message', (event) => {
      const { id, result } = event.data as { id: number; result: Result<unknown> }
      const waiting = this.pending.get(id)
      if (!waiting) {
        return
      }
      clearTimeout(waiting.timer)
      this.pending.delete(id)
      waiting.resolve(result)
    })
    channel.port1.start()

    child.on('exit', (code) => {
      // Everything in flight is lost, and saying so is better than leaving the
      // renderer with promises that never settle.
      for (const [, waiting] of this.pending) {
        clearTimeout(waiting.timer)
        waiting.resolve(fail(0, `data process exited (${code})`))
      }
      this.pending.clear()
      this.child = null
      this.channel = null
    })

    this.child = child
    this.channel = channel
  }

  /**
   * Ask the data layer for something.
   *
   * Never rejects. A dead child, a timeout and a handler error all come back
   * as a `Result` with `ok: false`, so the renderer has one failure shape.
   */
  call<M extends DataMethod>(
    method: M,
    params: DataParams<M>
  ): Promise<Result<DataResult<M>>> {
    this.start()
    const channel = this.channel
    if (!channel) {
      return Promise.resolve(fail(0, 'data process unavailable'))
    }

    const id = this.nextId++
    return new Promise<Result<DataResult<M>>>((resolve) => {
      const timer = setTimeout(() => {
        this.pending.delete(id)
        resolve(fail(0, `${method} timed out`))
      }, CALL_TIMEOUT_MS)

      this.pending.set(id, { resolve: resolve as (v: Result<unknown>) => void, timer })
      channel.port1.postMessage({ id, method, params })
    })
  }

  stop(): void {
    this.child?.kill()
    this.child = null
    this.channel = null
  }
}

/** The built data entry, beside this file in `out/main`. */
export function dataEntry(dirname: string): string {
  return join(dirname, 'data.js')
}
