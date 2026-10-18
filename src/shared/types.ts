// The contract between the three processes.
//
// This file is the only place the IPC surface is described. The preload is
// annotated `: SensorViewBridge`, so typechecking the preload is what
// guarantees the renderer's `window.sensorview.*` calls are correct -- there is
// no codegen and no runtime validation layer.
//
// Nothing here may import from electron, react or node: it is compiled into
// all three processes and into the tests.

/**
 * Every call across the boundary answers with one of these.
 *
 * Errors do not cross as exceptions. A failed read is a value, so renderer code
 * has no try/catch around IPC and the failure is as typed as the success.
 * `status` mirrors HTTP loosely: 0 means the call never reached its handler.
 */
export interface Result<T = unknown> {
  ok: boolean
  status: number
  data?: T
  error?: string
}

export function ok<T>(data: T): Result<T> {
  return { ok: true, status: 200, data }
}

export function fail(status: number, error: string): Result<never> {
  return { ok: false, status, error }
}

/* ────────────────────────────────────────────────────────── settings ──── */

export interface Settings {
  /** Last directory the open dialog started in. */
  dataPath: string
  /** "dark" | "light"; the renderer owns the meaning, this only persists it. */
  theme: string
  /** Most recently opened case directories, newest first. */
  recent: string[]
}

export const DEFAULT_SETTINGS: Settings = {
  dataPath: '',
  theme: 'dark',
  recent: []
}

/* ────────────────────────────────────────────────────────────── data ──── */

/**
 * What the data layer can be asked for.
 *
 * One entry per method rather than one channel per endpoint: the renderer calls
 * `data(method, params)` and the main process forwards it to the utility
 * process unchanged, so adding a reader touches this type and the handler, and
 * nothing in between.
 */
export interface DataMethods {
  /** Liveness check. Returns the data process's pid. */
  ping: { params: void; result: { pid: number } }
}

export type DataMethod = keyof DataMethods
export type DataParams<M extends DataMethod> = DataMethods[M]['params']
export type DataResult<M extends DataMethod> = DataMethods[M]['result']

/* ──────────────────────────────────────────────────────────── bridge ──── */

/** Exposed by the preload as `window.sensorview`. */
export interface SensorViewBridge {
  /** Ask the data layer for something. */
  data<M extends DataMethod>(method: M, params: DataParams<M>): Promise<Result<DataResult<M>>>

  /**
   * Choose a case directory. Resolves to null when the dialog is dismissed.
   *
   * Opening a directory is also what authorises `sv://` to read from it; see
   * `src/main/protocol.ts`.
   */
  openCase(): Promise<Result<string | null>>

  settings: {
    get(): Promise<Result<Settings>>
    set(patch: Partial<Settings>): Promise<Result<Settings>>
  }

  /**
   * Which host this is running under.
   *
   * `'browser'` is the `npm run web` target -- the renderer in a plain tab
   * against a fixture. It is a real value rather than a missing one so the few
   * places that must care can branch on it honestly instead of sniffing for
   * the absence of something.
   */
  platform: NodeJS.Platform | 'browser'
}

declare global {
  interface Window {
    sensorview: SensorViewBridge
  }
}
