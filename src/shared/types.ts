// The contract between the three processes.
//
// This file is the only place the IPC surface is described. The preload is
// annotated `: SensorViewBridge`, so typechecking the preload is what
// guarantees the renderer's `window.sensorview.*` calls are correct -- there is
// no codegen and no runtime validation layer.
//
// Nothing here may import from electron, react or node: it is compiled into
// all three processes and into the tests.

import type { ColumnMeta } from './table'

/** One log in a case: a table file, and which sidecars it has. */
export interface LogSummary {
  /** Stem the sidecars are keyed on. */
  stem: string
  /** Table file, absolute. */
  file: string
  hasCloud: boolean
  hasCurve: boolean
  hasImage: boolean
  hasReference: boolean
}

/**
 * What is in a case directory.
 *
 * Read once when the case opens and kept: switching between a case's logs
 * reads a table, not the directory again.
 */
export interface CaseSummary {
  dir: string
  name: string
  frameKey: string
  /** Column metadata driving the filters and hover text. */
  keys: Record<string, ColumnMeta>
  /** How the cloud is drawn, or null when the case declares none. */
  cloud: CloudDisplay | null
  logs: LogSummary[]
}

/** One camera recording beside a log, resolved to something playable. */
export interface ImageStream {
  id: string
  label: string
  /** Absolute path of the file to play -- the source, or a transcode of it. */
  file: string
  /** Frames in the recording, measured by demuxing. Null when unreadable. */
  frames: number | null
}

/** One trace of a curve plot, read for one frame. */
export interface CurveTrace {
  name: string
  label: string
  color?: string
  dash?: string
  width?: number
  /** Sample positions, or null to plot against the sample index. */
  x: Float32Array | null
  y: Float32Array
}

/** One plot of a curve sidecar, for one frame. */
export interface CurvePlot {
  id: string
  label: string
  xLabel: string
  yLabel: string
  traces: CurveTrace[]
}

/** Where the reference sits in one frame, and how it is drawn. */
export interface ReferenceFrame {
  pose: { x: number; y: number; z: number; yaw: number; pitch: number; roll: number }
  /** Triangle vertices in world space, already posed. */
  mesh: Float32Array | null
  /** Line segment endpoints in world space, already posed. */
  edges: Float32Array | null
  name: string
  color: string
  opacity: number
  edgeColor: string
  edgeWidth: number
}

/** How a case draws its cloud. Fixed per case, from the manifest. */
export interface CloudDisplay {
  color: string
  size: number
  opacity: number
  name: string
}

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

  /** Frame ids present in a table, ascending. */
  frameIds: { params: { path: string; frameKey: string }; result: number[] }

  /**
   * Read a table into columnar arrays.
   *
   * Numeric columns arrive as Float64Array with NaN for null; categoricals as
   * Int32Array level codes plus their dictionary, which is what makes a
   * category filter an integer comparison.
   */
  readTable: {
    params: { path: string; columns?: string[] }
    result: {
      rows: number
      columns: Array<{
        name: string
        kind: 'number' | 'string'
        values?: Float64Array
        codes?: Int32Array
        levels?: string[]
      }>
    }
  }

  /** One cloud frame as interleaved xyz. */
  cloudFrame: {
    params: { path: string; dataset: string }
    result: { position: Float32Array; count: number } | null
  }

  /** What is in a case directory: its logs and its column metadata. */
  scanCase: {
    params: { dir: string }
    result: CaseSummary
  }

  /**
   * A log's camera recordings, each resolved to a playable file.
   *
   * Resolving means transcoding when the recorder's container is not one a
   * browser plays, which is why this is here and not a property of the scan:
   * it can take seconds, and only the inspector needs it.
   */
  logImageStreams: {
    params: { dir: string; stem: string }
    result: ImageStream[]
  }

  /** A log's curve plots, read for one frame. */
  logCurves: {
    params: { dir: string; stem: string; sourceId?: string; frameId: number }
    result: CurvePlot[]
  }

  /** Where the reference sits in one frame, or null when it has no pose. */
  logReference: {
    params: { dir: string; stem: string; frameId: number }
    result: ReferenceFrame | null
  }

  /**
   * The reference's position extent across a whole log.
   *
   * The scene fixes its axis ranges from the filters, so a reference that
   * travels outside them would be clipped away rather than widening them.
   */
  logReferenceBounds: {
    params: { dir: string; stem: string }
    result: Record<'x' | 'y' | 'z', [number, number]> | null
  }

  /**
   * The cloud frame for one slider position of a log.
   *
   * Resolved here rather than in the renderer so a path is never built from
   * something the renderer said -- the same property the Flask routes had.
   */
  logCloudFrame: {
    params: { dir: string; stem: string; frameId: number }
    result: { position: Float32Array; count: number } | null
  }
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

  /**
   * Ask where to put an export, and write it there.
   *
   * The renderer makes the bytes and main decides where they land, so an
   * export cannot write anywhere the user did not choose -- the same
   * property the `sv://` allowlist gives reads.
   *
   * @returns The path written, or null when the dialog was dismissed.
   */
  saveFile(request: {
    suggestedName: string
    /** Text content, or base64 for a binary file. */
    data: string
    encoding: 'utf8' | 'base64'
    filters?: Array<{ name: string; extensions: string[] }>
  }): Promise<Result<string | null>>

  /**
   * The `sv://` URL for a file the data layer handed over.
   *
   * Encoding only. Whether the URL resolves is main's decision, taken from
   * the set of directories the user has opened -- the renderer can ask for
   * any path and widen nothing.
   */
  mediaUrl(path: string): string

  settings: {
    get(): Promise<Result<Settings>>
    set(patch: Partial<Settings>): Promise<Result<Settings>>
  }

  /**
   * A case to open as soon as the app is up, or null.
   *
   * Set from SENSORVIEW_OPEN_CASE. It exists so the end-to-end check can drive
   * a real case without a file dialog, and it is the hook an "open this folder"
   * command-line argument would use.
   */
  initialCase: string | null

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
