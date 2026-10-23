// The contract between the three processes.
//
// This file is the only place the IPC surface is described. The preload is
// annotated `: SensorViewBridge`, so typechecking the preload is what
// guarantees the renderer's `window.sensorview.*` calls are correct -- there is
// no codegen and no runtime validation layer.
//
// Nothing here may import from electron, react or node: it is compiled into
// all three processes and into the tests.

import { PALETTE } from './palette'
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
  /**
   * The 3D view's starting axes, from `table.x_3d`/`y_3d`/`z_3d`. A field is
   * null when the manifest leaves it out.
   */
  axes: { x: string | null; y: string | null; z: string | null }
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
  /** Plotly scatter mode: `lines`, `markers` or `lines+markers`. */
  mode?: string
  /** Marker size and symbol, used when `mode` includes markers. */
  size?: number
  symbol?: string
  /** Sample positions, or null to plot against the sample index. */
  x: Float32Array | null
  y: Float32Array
}

/** One plot of a curve sidecar, for one frame. */
export interface CurvePlot {
  id: string
  /**
   * The plot this is a copy of, when logs are combined.
   *
   * Each log draws its own band, but the bands share one y range so their
   * levels can be read against each other -- which is the whole reason to
   * put two logs on one slider.
   */
  rangeKey: string
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
  /** Where the panels are, and whether they are open. */
  layout: Layout
  /** Where the window was, or null before it has been moved. */
  bounds: WindowBounds | null
  /** How each recently opened case was set up, keyed by its directory. */
  views: Record<string, CaseView>
}

/**
 * Panel geometry, as the settings file carries it.
 *
 * A size is pixels, or null for "whatever the stylesheet says" -- which is
 * how a panel nobody has dragged keeps `--sv-rail-w` and its `34vh` dock
 * without those numbers being written down a second time here.
 */
export interface Layout {
  railW: number | null
  inspectorW: number | null
  dockH: number | null
  /**
   * How tall the camera card is, with the curves taking the rest.
   *
   * Null until the splitter between them is dragged, which is when the two
   * stop dividing the column by what they hold and start dividing it by
   * what was asked for. Only read while both are on screen: one on its own
   * takes the whole height whatever this says.
   */
  cameraH: number | null
  dockCollapsed: boolean
  /**
   * Which overlays are away, by id.
   *
   * The left-hand overlays -- `display` and `filters` -- are each their own
   * panel rather than two halves of a rail, so each is shown or hidden on
   * its own. There is nothing in between: a panel narrowed to a strip of
   * icons is a third state that costs the scene a column to say what the
   * top bar already says in a place that does not move.
   *
   * A list rather than a field apiece: the overlays are a growing set, and
   * every one would otherwise be a field here, a default, a line in
   * `sanitiseLayout` and a key in the store. Shown is the default, so an id
   * that no longer exists simply never matches.
   */
  hidden: string[]
  /**
   * How many panes the analysis dock shows, one or two.
   *
   * A layout question, asked once, rather than something inferred from a
   * slot being set to nothing -- which is how it used to be said, and meant
   * choosing "Empty" from a list of chart types to change the shape of the
   * dock.
   */
  dockPanes: number
}

export const DEFAULT_LAYOUT: Layout = {
  railW: null,
  inspectorW: null,
  dockH: null,
  cameraH: null,
  dockCollapsed: false,
  hidden: [],
  dockPanes: 2
}

/**
 * Trust nothing that came off disk.
 *
 * `settings.json` is a file a user can edit, and a width of `"wide"` or
 * `-4000` would wedge a panel somewhere no drag could reach. Anything that
 * does not survive this becomes null, which is the stylesheet's own value.
 * The renderer clamps the survivors again on its own bounds.
 */
export function sanitiseLayout(raw: unknown): Layout {
  const it = (raw ?? {}) as Record<string, unknown>
  const size = (v: unknown) =>
    typeof v === 'number' && Number.isFinite(v) && v > 0 ? Math.round(v) : null
  return {
    railW: size(it.railW),
    inspectorW: size(it.inspectorW),
    dockH: size(it.dockH),
    cameraH: size(it.cameraH),
    dockCollapsed: it.dockCollapsed === true,
    // Capped and filtered: this is a list off disk, and an overlay nobody
    // can reach is still a string carried around for the life of the app.
    hidden: Array.isArray(it.hidden)
      ? it.hidden.filter((id): id is string => typeof id === 'string').slice(0, 32)
      : [],
    dockPanes: it.dockPanes === 1 ? 1 : 2
  }
}

/**
 * Where the window was, in screen pixels, and whether it was maximised.
 *
 * Null until the window has been moved or resized once, which is what lets a
 * first run open at the size `createWindow` asks for rather than having that
 * size written down here as well.
 *
 * The maximised flag is kept beside the bounds rather than instead of them:
 * `getNormalBounds` reports where a maximised window would go back to, so
 * un-maximising a restored window lands it where the user left it rather
 * than at the default size in the middle of the screen.
 */
export interface WindowBounds {
  x: number
  y: number
  width: number
  height: number
  maximized: boolean
}

/**
 * Trust nothing that came off disk, part two.
 *
 * A width of zero or an x of `1e9` is a window the user cannot see and cannot
 * drag back. Anything that does not survive this is no stored placement at
 * all, and the window opens where a first run would. Whether the rectangle is
 * on a display that still exists is main's question -- it needs the screen
 * module, which this file cannot import.
 */
export function sanitiseBounds(raw: unknown): WindowBounds | null {
  const it = (raw ?? {}) as Record<string, unknown>
  const at = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? Math.round(v) : null)
  const span = (v: unknown) => {
    const n = at(v)
    return n !== null && n > 0 ? n : null
  }
  const x = at(it.x)
  const y = at(it.y)
  const width = span(it.width)
  const height = span(it.height)
  if (x === null || y === null || width === null || height === null) {
    return null
  }
  return { x, y, width, height, maximized: it.maximized === true }
}

/**
 * One analysis pane, as the settings file carries it.
 *
 * Every field is optional and typed loosely -- `view` is a string here, not
 * the renderer's `ViewId` -- because a restored pane has to be reconciled
 * against the case that is actually open, and a chart type that no longer
 * exists is the same problem as a column the new log does not have.
 * `AnalysisDock` already solves that for the panes it builds itself, so the
 * narrowing happens there and this stays a shape rather than a promise.
 */
export interface DockSlot {
  view?: string
  x?: string
  y?: string
  colour?: string
  dimensions?: string[]
  logScale?: boolean
  histnorm?: string
  scope?: string
  limits?: { xMin?: string; xMax?: string; yMin?: string; yMax?: string }
}

/**
 * What the user set up for one case.
 *
 * Per case rather than once for the app, because most of it names columns:
 * restoring case A's axes onto case B would colour by a key that case does
 * not have, which reads back as zeros from every row and draws a
 * plausible-looking chart of nothing.
 *
 * Every field is optional. Two components write into this -- the display
 * panel's half through `useViewPersistence`, the panes through
 * `AnalysisDock` -- and a case whose dock nobody has touched simply has no
 * `slots`. `rememberView` merges a patch rather than replacing the entry, so
 * the two cannot clobber each other.
 */
export interface CaseView {
  axes?: { x: string; y: string; z: string; colour: string }
  colormap?: string
  decay?: number
  overlay?: boolean
  cloudOn?: boolean
  sizeVary?: boolean
  clickToHide?: boolean
  slots?: [DockSlot, DockSlot]
}

/** How many cases keep their view settings. The recent list's own length. */
export const MAX_VIEWS = 10

/**
 * Keep the fields that are the type they claim, and drop the rest.
 *
 * Shallow on purpose for `slots`: the panes are narrowed by the dock, which
 * is the only place that knows which chart types and columns exist.
 */
export function sanitiseView(raw: unknown): CaseView {
  const it = (raw ?? {}) as Record<string, unknown>
  const view: CaseView = {}
  const axes = (it.axes ?? {}) as Record<string, unknown>
  if (['x', 'y', 'z', 'colour'].every((key) => typeof axes[key] === 'string')) {
    view.axes = {
      x: axes.x as string,
      y: axes.y as string,
      z: axes.z as string,
      colour: axes.colour as string
    }
  }
  // A colormap the palette does not hold would draw every point black.
  if (typeof it.colormap === 'string' && it.colormap in PALETTE.colorscales) {
    view.colormap = it.colormap
  }
  if (typeof it.decay === 'number' && Number.isFinite(it.decay)) {
    view.decay = Math.max(0, Math.round(it.decay))
  }
  for (const flag of ['overlay', 'cloudOn', 'sizeVary', 'clickToHide'] as const) {
    if (typeof it[flag] === 'boolean') {
      view[flag] = it[flag] as boolean
    }
  }
  if (Array.isArray(it.slots) && it.slots.length === 2 && it.slots.every(isObject)) {
    view.slots = [it.slots[0] as DockSlot, it.slots[1] as DockSlot]
  }
  return view
}

function isObject(value: unknown): boolean {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** Every case's view settings, capped and shape-checked. */
export function sanitiseViews(raw: unknown): Record<string, CaseView> {
  if (!isObject(raw)) {
    return {}
  }
  const views: Record<string, CaseView> = {}
  // Oldest first in insertion order, so the slice keeps the newest.
  for (const [dir, view] of Object.entries(raw as Record<string, unknown>).slice(-MAX_VIEWS)) {
    views[dir] = sanitiseView(view)
  }
  return views
}

export const DEFAULT_SETTINGS: Settings = {
  dataPath: '',
  theme: 'dark',
  recent: [],
  layout: DEFAULT_LAYOUT,
  bounds: null,
  views: {}
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
    params: { path: string | string[]; columns?: string[] }
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
   * Record the axis, slider and reference column choices in `info.json`.
   *
   * The manifest mutates only the paths given and writes the parsed object
   * back as-is, so unknown blocks and key order survive -- see R1. A v1 file
   * is upgraded to v2 on the first save, with the original kept once as
   * `info.json.bak`; the result says whether that happened so the UI can
   * mention it rather than rewriting someone's file silently.
   */
  saveManifest: {
    params: {
      dir: string
      /** `x_3d`, `y_3d`, `z_3d`, `slider`. */
      table?: Record<string, string>
      /** Pose field -> column name; the empty string means "no column". */
      reference?: Record<string, string>
    }
    result: { path: string; upgraded: boolean }
  }

  /**
   * A log's reference sidecar: the columns it has, and what each pose field
   * currently resolves to.
   *
   * The pickers are populated from the sidecar's own columns, not the
   * table's -- it is a different file with its own names.
   */
  logReferenceColumns: {
    params: { dir: string; stem: string }
    result: { available: string[]; resolved: Record<string, string | null> } | null
  }

  /**
   * Which logs recorded each frame id.
   *
   * Read by projection rather than by loading the tables: it is one column
   * per file, and on a multi-GB table the difference is opening a case in a
   * second or in a minute. Keyed by the id's string form, because the ids
   * come back from the scan as scalars and are matched against the ones the
   * loaded table carries.
   */
  logFrameOwners: {
    params: { dir: string; stems: string[] }
    result: Record<string, string[]>
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

  /**
   * The curve sidecars a case's logs carry, as a union.
   *
   * Combined logs need not carry the same sensors, and a selector listing
   * only the primary's would hide a sidecar the second log was combined in
   * for.
   */
  logCurveSources: {
    params: { dir: string; stems: string[] }
    result: Array<{ id: string; label: string }>
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
   * The reference's position extent across every open log.
   *
   * The scene fixes its axis ranges once for the load, so a reference that
   * travels outside them would be clipped rather than widening them -- and
   * with logs combined the box has to cover wherever *any* of their
   * references goes, or the second one is clipped the moment the slider
   * reaches it.
   */
  logReferenceBounds: {
    params: { dir: string; stems: string[] }
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
    /**
     * Merge a patch into one case's view settings.
     *
     * A method of its own rather than `set({ views })`, because `set` merges
     * only the top level: two components each patching their own half of a
     * case's view would write the whole map back and lose the other's half.
     */
    rememberView(dir: string, patch: CaseView): Promise<Result<Settings>>
  }

  /**
   * The case to open as soon as the app is up, or null.
   *
   * A call rather than a value, because main answers it: the path comes from
   * SENSORVIEW_OPEN_CASE or, failing that, the most recent case that still
   * exists, and either way main has to authorise it for `sv://` before the
   * renderer asks for a frame of video from inside it.
   */
  initialCase(): Promise<Result<string | null>>

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
