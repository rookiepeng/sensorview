// Dataset manifest (info.json v2).
//
// The manifest describes a *case* -- a folder that may hold many logs -- and
// nothing about any individual log. It declares the table's column metadata,
// the filename suffixes that associate a log's sidecars with it, per-sensor
// calibration, the cloud's fixed styling, the curve plot definitions, and how
// the reference overlay is drawn.
//
// Two things it deliberately does not declare:
//
//   - The frame index. Frame ids come from the Parquet data, so a manifest
//     cannot drift out of sync with the log it describes.
//   - Per-log file lists. Logs sit side by side and are associated by
//     basename, so adding one is dropping files in the folder.
//
// Ported from dataio/manifest.py. One deliberate difference:
//
//   - **Nothing is reserialized that was not changed.** The parsed object is
//     mutated in place and written back, so key order, unknown blocks and
//     anything a future version adds survive a save untouched.
//
// Only v2 is read. A manifest without `manifest_version: 2` is refused.

import { promises as fs } from 'node:fs'
import { basename, dirname, extname, join, normalize, relative, sep } from 'node:path'

export const MANIFEST_VERSION = 2
export const MANIFEST_NAME = 'info.json'

/** Table keys the axis and slider pickers write back. */
const TABLE_VIEW_KEYS = ['slider', 'x_3d', 'y_3d', 'z_3d'] as const

export const DEFAULT_TABLE_SUFFIX = '.parquet'
export const DEFAULT_CLOUD_SUFFIX = '.cloud.h5'
export const DEFAULT_CURVE_SUFFIX = '.curve.h5'
export const DEFAULT_REFERENCE_SUFFIX = '.reference.parquet'
// mp4 first: a stream present in both containers is served without a transcode.
export const DEFAULT_IMAGE_SUFFIXES = ['.mp4', '.avi']

export const DEFAULT_CLOUD_PATTERN = '/frame_{frame_id}'
export const DEFAULT_CURVE_PATTERN = '/frame_{frame_id}/{name}'

/** Fallback trace colors, used in order for traces that declare none. */
const DEFAULT_TRACE_COLORS = ['#4c9be8', '#e8734c', '#5cb85c', '#c678dd', '#e8c34c', '#4cd4e8']

export const DEFAULT_CLOUD_DISPLAY = {
  color: '#8d99ae',
  size: 1.2,
  opacity: 0.35,
  name: 'Point Cloud'
}

const REFERENCE_SHAPES = ['marker', 'mesh']

export const DEFAULT_REFERENCE_DISPLAY: Record<string, unknown> = {
  name: 'Host Vehicle',
  shape: 'marker',
  color: '#ffffff',
  opacity: 1.0,
  // marker only
  size: 6,
  symbol: 'circle',
  line_color: '#000000',
  line_width: 2
}

/**
 * What a field named as nothing normalizes to.
 *
 * Distinct from a field the manifest never names, which is null: unnamed means
 * "guess a column from the field's own name", and that guess is what lets a
 * self-describing sidecar work with no mapping at all. Named-as-nothing is the
 * user saying the file has no such column -- and for `frame`, the column the
 * file is paired with the table on, that switches the whole overlay off.
 */
export const NO_COLUMN = ''

export const DEFAULT_REFERENCE_COLUMNS: Record<string, string | null> = {
  frame: null,
  x: null,
  y: null,
  z: null,
  yaw: null,
  pitch: null,
  roll: null
}

/**
 * Cloud fields the renderer places.
 *
 * There is deliberately no NO_COLUMN here, unlike the reference block. That
 * spelling exists so a picker's empty dropdown can say "this file has no such
 * column", and a pose without a `z` is still a pose on the ground plane. A
 * point without an `x` is not a point, so every cloud field resolves.
 */
export const DEFAULT_CLOUD_COLUMNS: Record<string, string | null> = { x: null, y: null, z: null }

/** Keys of `reference` describing where data comes from, not how it is drawn. */
const REFERENCE_SOURCE_KEYS = ['suffix', 'columns']

/**
 * Mesh-only defaults.
 *
 * A solid body at full opacity would bury every detection inside it, so a mesh
 * is translucent where the dot is not. The geometry is the dataset's to state:
 * nothing here generates a shape, so which end is the front is answered by the
 * mesh rather than by a setting.
 */
const DEFAULT_REFERENCE_MESH: Record<string, unknown> = {
  opacity: 0.35,
  vertices: [],
  faces: [],
  // true derives the wireframe from `faces`; a list of index pairs draws
  // exactly those; false draws none.
  edges: true,
  // null means "follow `color`".
  edge_color: null,
  edge_width: 2
}

export class ManifestError extends Error {}

type Dict = Record<string, any>

/* ───────────────────────────────────────────────────────── mesh helpers ─── */

/**
 * Coerce a manifest 3-vector to three numbers.
 *
 * Accepts the list form `[x, y, z]` and the mapping form `{x, y, z}`, since
 * both read naturally in a hand-written manifest.
 */
function vec3(value: unknown, fallback: number[]): number[] {
  let v: unknown = value
  if (v && typeof v === 'object' && !Array.isArray(v)) {
    const m = v as Dict
    v = [m.x, m.y, m.z]
  }
  if (!Array.isArray(v) || v.length !== 3) {
    return [...fallback]
  }
  const out = v.map((component) => Number(component))
  return out.some((n) => !Number.isFinite(n)) ? [...fallback] : out
}

/**
 * Coerce a `vertices` list to xyz triples.
 *
 * An unusable entry is dropped rather than raising -- but dropping one
 * renumbers everything after it, which is why `meshFaces` is given the count
 * and discards any triangle pointing past it.
 */
function meshVertices(raw: unknown): number[][] {
  if (!Array.isArray(raw)) {
    return []
  }
  const out: number[][] = []
  for (const entry of raw) {
    const vertex = vec3(entry, [])
    if (vertex.length === 3) {
      out.push(vertex)
    }
  }
  return out
}

/**
 * Coerce a `faces` list to vertex-index triangles.
 *
 * Out-of-range and malformed triangles are dropped: a renderer shows an
 * out-of-range index as a hole rather than an error, which is harder to
 * diagnose than a missing face.
 */
function meshFaces(raw: unknown, vertexCount: number): number[][] {
  if (!Array.isArray(raw)) {
    return []
  }
  const out: number[][] = []
  for (const entry of raw) {
    if (!Array.isArray(entry) || entry.length !== 3) {
      continue
    }
    const triangle = entry.map((index) => Math.trunc(Number(index)))
    if (triangle.some((index) => !Number.isFinite(index))) {
      continue
    }
    if (triangle.every((index) => index >= 0 && index < vertexCount)) {
      out.push(triangle)
    }
  }
  return out
}

/**
 * Resolve an `edges` declaration to vertex-index pairs.
 *
 * Deriving from faces outlines every triangle, diagonals included -- a mesh
 * that wants only its silhouette lists the edges it wants.
 */
function meshEdges(raw: unknown, faces: number[][], vertexCount: number): number[][] {
  if (!raw) {
    return []
  }

  if (raw === true) {
    const seen = new Set<string>()
    const out: number[][] = []
    for (const triangle of faces) {
      for (let position = 0; position < 3; position++) {
        const a = triangle[position]!
        const b = triangle[(position + 1) % 3]!
        // Unordered, so an edge shared by two triangles is drawn once.
        const key = a < b ? `${a}:${b}` : `${b}:${a}`
        if (!seen.has(key)) {
          seen.add(key)
          out.push([a, b])
        }
      }
    }
    return out
  }

  if (!Array.isArray(raw)) {
    return []
  }
  const out: number[][] = []
  for (const entry of raw) {
    if (!Array.isArray(entry) || entry.length !== 2) {
      continue
    }
    const pair = entry.map((index) => Math.trunc(Number(index)))
    if (pair.some((index) => !Number.isFinite(index))) {
      continue
    }
    if (pair.every((index) => index >= 0 && index < vertexCount)) {
      out.push(pair)
    }
  }
  return out
}

/**
 * Bounding box of a mesh, per axis.
 *
 * The scene fixes its axis ranges, so whatever the mesh adds beyond the data
 * has to be made room for or it is simply clipped away.
 */
function meshExtent(vertices: number[][]): number[][] {
  if (vertices.length === 0) {
    return [
      [0, 0],
      [0, 0],
      [0, 0]
    ]
  }
  return [0, 1, 2].map((axis) => [
    Math.min(...vertices.map((v) => v[axis]!)),
    Math.max(...vertices.map((v) => v[axis]!))
  ])
}

/**
 * Distance from the reference point to the furthest vertex.
 *
 * A mesh that turns with a pose reaches further along an axis than its own
 * extent on that axis, and this bounds it whatever the orientation.
 */
function meshRadius(vertices: number[][]): number {
  if (vertices.length === 0) {
    return 0
  }
  return Math.max(...vertices.map((v) => Math.hypot(v[0]!, v[1]!, v[2]!)))
}

/* ───────────────────────────────────────────────────────── normalizers ─── */

/**
 * Fill in a manifest `reference` block.
 *
 * An unknown `shape` falls back to `marker` rather than raising: a typo in a
 * cosmetic field should not cost the user their reference point. So does a
 * `mesh` with no drawable geometry -- a dot in the right place beats nothing.
 *
 * `declared` records whether the dataset asked for a reference at all, which
 * the defaults otherwise erase: an absent block and an empty one normalize to
 * the same white dot. The renderer needs the distinction, because a declared
 * reference nothing can place is still drawn -- at the origin -- while a
 * dataset that never mentioned one draws nothing.
 */
export function normalizeReferenceDisplay(raw: Dict | null | undefined): Dict {
  const declared = raw !== null && raw !== undefined
  const block: Dict = raw ?? {}

  const display: Dict = { ...DEFAULT_REFERENCE_DISPLAY }
  let shape = String(block.shape ?? display.shape).toLowerCase()
  if (!REFERENCE_SHAPES.includes(shape)) {
    shape = DEFAULT_REFERENCE_DISPLAY.shape as string
  }

  if (shape === 'mesh') {
    Object.assign(display, DEFAULT_REFERENCE_MESH)
  }

  for (const [key, value] of Object.entries(block)) {
    if (key !== 'shape' && !REFERENCE_SOURCE_KEYS.includes(key)) {
      display[key] = value
    }
  }
  display.shape = shape

  if (shape === 'mesh') {
    const vertices = meshVertices(display.vertices)
    const faces = meshFaces(display.faces, vertices.length)
    if (faces.length === 0) {
      // Vertices with no face enclose nothing, and a mesh with no triangles is
      // an invisible reference. Say so by falling back.
      return normalizeReferenceDisplay({ ...block, shape: DEFAULT_REFERENCE_DISPLAY.shape })
    }

    display.vertices = vertices
    display.faces = faces
    display.edges = meshEdges(display.edges, faces, vertices.length)
    display.edge_color = display.edge_color || display.color
    display.extent = meshExtent(vertices)
    display.radius = meshRadius(vertices)
  }

  // Set last so a manifest cannot claim it: whether the block exists is this
  // function's own reading of its input, not a field the block can author.
  display.declared = declared
  return display
}

/**
 * Fill in a `reference.columns` block.
 *
 * A field the block does not name is null -- resolve it by guessing. A field
 * it names as nothing is NO_COLUMN: null, the empty string and `"None"` (what
 * an empty dropdown used to emit) all mean the same, and none means "guess".
 */
export function normalizeReferenceColumns(raw: Dict | null | undefined): Record<string, string | null> {
  const columns = { ...DEFAULT_REFERENCE_COLUMNS }
  for (const [field, value] of Object.entries(raw ?? {})) {
    if (!(field in columns)) {
      continue
    }
    columns[field] =
      value === null || value === undefined || value === '' || value === 'None'
        ? NO_COLUMN
        : String(value)
  }
  return columns
}

/**
 * Fill in a `cloud.columns` block.
 *
 * Anything that is not a mapping -- notably the list of column names older
 * manifests carried here as provenance -- is ignored rather than guessed at,
 * leaving every field to resolve on its own.
 */
export function normalizeCloudColumns(raw: unknown): Record<string, string | null> {
  const columns = { ...DEFAULT_CLOUD_COLUMNS }
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return columns
  }
  for (const [field, value] of Object.entries(raw as Dict)) {
    if (!(field in columns)) {
      continue
    }
    if (value === null || value === undefined || value === '' || value === 'None') {
      continue
    }
    columns[field] = String(value)
  }
  return columns
}

/**
 * Name a source after the suffix that matched its whole filename.
 *
 * Splitting on the extension is no help: a leading dot reads as a hidden
 * filename, so `.sensor_1.h5` would come out extensionless. Stripping that dot
 * first leaves the part that actually distinguishes one sidecar from another.
 * A bare extension like `.h5` distinguishes nothing, so it falls back.
 */
export function suffixSourceId(suffix: string): string {
  const body = suffix.replace(/^\.+/, '')
  if (!body.includes('.')) {
    return 'curve'
  }
  const ext = extname(body)
  return (ext ? body.slice(0, -ext.length) : body) || 'curve'
}

/**
 * Reduce a table filename to the stem its sidecars are keyed on.
 *
 * A dataset declaring a custom suffix still reduces against the default one,
 * so a plain `.parquet` log in the same folder is not left with its extension
 * attached.
 */
export function logStem(fileName: string, tableSuffix = DEFAULT_TABLE_SUFFIX): string {
  const base = basename(fileName)
  for (const suffix of [tableSuffix, '.parquet']) {
    if (suffix && base.toLowerCase().endsWith(suffix.toLowerCase())) {
      return base.slice(0, -suffix.length)
    }
  }
  const ext = extname(base)
  return ext ? base.slice(0, -ext.length) : base
}

/* ─────────────────────────────────────────────────────────── the class ─── */

export interface CurveSource {
  id: string
  label: string
  file: string
}

export interface ImageStream {
  id: string
  label: string
  file: string
}

export class Manifest {
  constructor(
    public raw: Dict,
    public caseDir: string
  ) {}

  /**
   * Load `info.json` from a case directory.
   *
   * @throws ManifestError if the file is missing or cannot be decoded.
   */
  static async load(caseDir: string): Promise<Manifest> {
    const path = join(caseDir, MANIFEST_NAME)

    let text: string
    try {
      text = await fs.readFile(path, 'utf8')
    } catch {
      throw new ManifestError(`No ${MANIFEST_NAME} found in ${caseDir}`)
    }

    let raw: unknown
    try {
      raw = JSON.parse(text)
    } catch (error) {
      throw new ManifestError(`Could not read ${path}: ${String(error)}`)
    }

    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
      throw new ManifestError(`${path} must contain a JSON object`)
    }

    const dict = raw as Dict
    if (dict.manifest_version !== MANIFEST_VERSION) {
      throw new ManifestError(
        `${path} must declare "manifest_version": ${MANIFEST_VERSION}` +
          (dict.manifest_version === undefined ? ' (v1 manifests are no longer supported)' : '')
      )
    }
    return new Manifest(dict, caseDir)
  }

  /* ─────────────────────────────────────────────────── top-level blocks ─── */

  /** Human-readable dataset name; defaults to the case directory name. */
  get name(): string {
    return this.raw.name || basename(normalize(this.caseDir))
  }

  get table(): Dict {
    return this.raw.table ?? {}
  }

  get cloud(): Dict | null {
    return this.raw.cloud ?? null
  }

  get curve(): Dict | null {
    return this.raw.curve ?? null
  }

  get image(): Dict | null {
    return this.raw.image ?? null
  }

  get reference(): Dict | null {
    return this.raw.reference ?? null
  }

  /** Column the frames are keyed on. */
  get frameKey(): string {
    return this.table.slider || 'Frame'
  }

  /** The 3D view's axes as the manifest names them; null where it does not. */
  get axes3d(): { x: string | null; y: string | null; z: string | null } {
    const name = (value: unknown) =>
      typeof value === 'string' && value.trim() !== '' ? value : null
    return { x: name(this.table.x_3d), y: name(this.table.y_3d), z: name(this.table.z_3d) }
  }

  /** Column metadata driving the filter UI and hover text. */
  get keys(): Dict {
    return this.table.keys ?? {}
  }

  /* ───────────────────────────────────────────────────────────── stems ─── */

  get tableSuffix(): string {
    return this.table.suffix ?? DEFAULT_TABLE_SUFFIX
  }

  /**
   * Reduce a table filename to this dataset's log stem.
   *
   * A log in a subfolder keeps that folder as a `/`-separated prefix, which
   * locates its sidecars and keeps same-named logs in different folders apart.
   */
  stemOf(fileName: string): string {
    const stem = logStem(fileName, this.tableSuffix)
    const directory = dirname(fileName)
    if (!directory || directory === '.') {
      return stem
    }

    let rel: string
    try {
      rel = relative(this.caseDir, directory)
    } catch {
      return stem
    }
    if (rel === '' || rel === '.' || rel === '..' || rel.startsWith('..' + sep)) {
      return stem
    }
    return `${rel.split(sep).join('/')}/${stem}`
  }

  /** Split a stem into the folder holding its sidecars and its basename. */
  private stemLocation(stem: string): [string, string] {
    const slash = stem.lastIndexOf('/')
    const directory = slash === -1 ? '' : stem.slice(0, slash)
    const base = slash === -1 ? stem : stem.slice(slash + 1)
    return [join(this.caseDir, directory), base]
  }

  private sidecarPath(stem: string, suffix: string): string {
    return normalize(join(this.caseDir, `${stem}${suffix}`))
  }

  /**
   * The table a stem names.
   *
   * The same path `scanCase` listed the log from, derived rather than
   * remembered: a stem plus the manifest's table suffix is what a log is.
   */
  tablePath(stem: string): string | null {
    return stem ? this.sidecarPath(stem, this.tableSuffix) : null
  }

  /* ───────────────────────────────────────────────────────────── cloud ─── */

  get cloudSuffix(): string {
    return this.cloud?.suffix ?? DEFAULT_CLOUD_SUFFIX
  }

  cloudPath(stem: string): string | null {
    return this.cloud && stem ? this.sidecarPath(stem, this.cloudSuffix) : null
  }

  cloudDatasetPattern(): string {
    return this.cloud?.dataset_pattern ?? DEFAULT_CLOUD_PATTERN
  }

  cloudColumns(): Record<string, string | null> {
    return normalizeCloudColumns(this.cloud?.columns)
  }

  /** Fixed styling for the backdrop, merging manifest overrides over defaults. */
  cloudDisplay(): Dict {
    return { ...DEFAULT_CLOUD_DISPLAY, ...(this.cloud?.display ?? {}) }
  }

  /* ───────────────────────────────────────────────────────────── curve ─── */

  /**
   * Filename suffixes identifying a curve sidecar, in listing order.
   *
   * One generic suffix matches `<stem><suffix>` as the default source and
   * `<stem>.<id><suffix>` as a named one. A list names the sidecars outright,
   * which is worth the typing when the folder holds `.h5` files that are not
   * curves, or when the picker should list sensors in a particular order.
   */
  get curveSuffixes(): string[] {
    const declared = this.curve?.suffix ?? DEFAULT_CURVE_SUFFIX
    return typeof declared === 'string' ? [declared] : [...declared]
  }

  curveDatasetPattern(): string {
    return this.curve?.dataset_pattern ?? DEFAULT_CURVE_PATTERN
  }

  /**
   * Discover a log's curve sidecars on disk.
   *
   * Sources are found rather than declared, the same way image streams are.
   * The source id is whatever distinguishes the file: the text between stem
   * and suffix when the suffix is generic, and the suffix's own stem when it
   * names the file outright.
   *
   * @returns Sources in discovery order -- declared-suffix order first, then
   *     filename order within a suffix. A file matching more than one suffix
   *     is listed once, under the first that claimed it.
   */
  async curveSources(stem: string): Promise<CurveSource[]> {
    if (!this.curve || !stem) {
      return []
    }

    const [directory, base] = this.stemLocation(stem)
    let entries: string[]
    try {
      entries = (await fs.readdir(directory)).sort()
    } catch {
      return []
    }

    const suffixes = this.curveSuffixes
    const declared = new Set(suffixes.map((s) => s.toLowerCase()))

    // A suffix as generic as ".h5" would otherwise swallow the cloud sidecar,
    // which is a different kind of file entirely. A suffix the dataset
    // declared explicitly is never treated as someone else's.
    const reserved = [this.cloudSuffix, this.tableSuffix]
      .map((s) => s.toLowerCase())
      .filter((s) => !declared.has(s))

    const sources = new Map<string, CurveSource>()
    for (const suffix of suffixes) {
      const lowerSuffix = suffix.toLowerCase()
      for (const name of entries) {
        const lower = name.toLowerCase()
        if (!name.startsWith(base) || !lower.endsWith(lowerSuffix)) {
          continue
        }
        if (reserved.some((other) => lower.endsWith(other))) {
          continue
        }

        const middle = name.slice(base.length, name.length - suffix.length)
        let sourceId: string
        if (middle === '') {
          // The suffix names the file on its own, so it is what tells this
          // source apart from its siblings.
          sourceId = suffixSourceId(suffix)
        } else if (middle.startsWith('.')) {
          sourceId = middle.slice(1)
        } else {
          // Belongs to a different log whose stem merely shares a prefix.
          continue
        }

        if (!sources.has(sourceId)) {
          sources.set(sourceId, {
            id: sourceId,
            label: titleCase(sourceId),
            file: join(directory, name)
          })
        }
      }
    }
    return [...sources.values()]
  }

  async curvePath(stem: string, sourceId?: string): Promise<string | null> {
    const sources = await this.curveSources(stem)
    if (sources.length === 0) {
      return null
    }
    if (!sourceId) {
      return sources[0]!.file
    }
    return sources.find((source) => source.id === sourceId)?.file ?? null
  }

  async hasCurve(stem: string): Promise<boolean> {
    return (await this.curveSources(stem)).length > 0
  }

  /**
   * Normalized curve plot definitions.
   *
   * Curves are 1D and one file holds many, so what goes on which plot -- and
   * how each is drawn -- is declared rather than guessed. A trace's `name`
   * fills the `{name}` placeholder in the dataset pattern; an explicit
   * `dataset` overrides that entirely. `x` carries only a label, because every
   * series brings its own x column.
   */
  curvePlots(): Dict[] {
    const block = this.curve ?? {}
    const defaultPattern = block.dataset_pattern ?? DEFAULT_CURVE_PATTERN

    const plots: Dict[] = []
    const declared: unknown[] = block.plots ?? []

    declared.forEach((entry, index) => {
      if (!entry || typeof entry !== 'object' || Array.isArray(entry)) {
        return
      }
      const plot = entry as Dict
      const plotId = plot.id || `plot_${index}`
      const pattern = plot.dataset_pattern ?? defaultPattern

      const traces: Dict[] = []
      const rawTraces: unknown[] = plot.traces ?? []
      rawTraces.forEach((rawTrace, position) => {
        const trace: Dict =
          typeof rawTrace === 'string' ? { name: rawTrace } : ((rawTrace as Dict) ?? {})
        if (typeof trace !== 'object' || (!trace.name && !trace.dataset)) {
          return
        }
        const name = trace.name ?? ''
        traces.push({
          name,
          label: trace.label ?? name,
          dataset: trace.dataset || String(pattern).replace('{name}', name),
          color: trace.color ?? DEFAULT_TRACE_COLORS[position % DEFAULT_TRACE_COLORS.length],
          dash: trace.dash ?? 'solid',
          width: trace.width ?? 2,
          mode: trace.mode ?? 'lines',
          size: trace.size ?? 6,
          symbol: trace.symbol ?? 'circle'
        })
      })

      const xAxis: Dict = plot.x ?? {}
      plots.push({
        id: plotId,
        label: plot.label ?? plotId,
        x_label: xAxis.label ?? '',
        x_range: xAxis.range ?? null,
        y_label: plot.y_label ?? '',
        y_range: plot.y_range ?? null,
        log_y: Boolean(plot.log_y),
        traces
      })
    })

    return plots
  }

  curvePlot(plotId: string): Dict | null {
    return this.curvePlots().find((plot) => plot.id === plotId) ?? null
  }

  /* ───────────────────────────────────────────────────────── reference ─── */

  get referenceSuffix(): string {
    return this.reference?.suffix ?? DEFAULT_REFERENCE_SUFFIX
  }

  referencePath(stem: string): string | null {
    return stem ? this.sidecarPath(stem, this.referenceSuffix) : null
  }

  referenceColumns(): Record<string, string | null> {
    return normalizeReferenceColumns(this.reference?.columns)
  }

  referenceDisplay(): Dict {
    return normalizeReferenceDisplay(this.reference)
  }

  /**
   * Record the reference column mapping chosen in the view.
   *
   * Only the fields the block knows about; an unknown key would be written and
   * then silently ignored on the next read, which is worse than refusing it.
   */
  updateReferenceColumns(values: Dict): void {
    const block = (this.raw.reference ??= {})
    const columns = (block.columns ??= {})
    for (const [field, value] of Object.entries(values)) {
      if (field in DEFAULT_REFERENCE_COLUMNS) {
        columns[field] = value
      }
    }
  }

  /* ───────────────────────────────────────────────────────────── image ─── */

  get imageSuffixes(): string[] {
    const declared = this.image?.suffix
    if (!declared) {
      return [...DEFAULT_IMAGE_SUFFIXES]
    }
    return typeof declared === 'string' ? [declared] : [...declared]
  }

  /**
   * Discover a log's image streams on disk.
   *
   * `<stem>.mp4` is the default stream and `<stem>.<id>.mp4` adds a named one,
   * so a second camera is just another file in the folder. When one stream is
   * present in several containers the earliest declared suffix wins -- a log
   * shipped as both mp4 and avi serves the mp4 and skips the transcode.
   */
  async imageStreams(stem: string): Promise<ImageStream[]> {
    if (!this.image || !stem) {
      return []
    }

    const [directory, base] = this.stemLocation(stem)
    let entries: string[]
    try {
      entries = (await fs.readdir(directory)).sort()
    } catch {
      return []
    }

    const streams = new Map<string, ImageStream>()
    for (const suffix of this.imageSuffixes) {
      const lowerSuffix = suffix.toLowerCase()
      for (const name of entries) {
        if (!name.startsWith(base) || !name.toLowerCase().endsWith(lowerSuffix)) {
          continue
        }

        const middle = name.slice(base.length, name.length - suffix.length)
        let streamId: string
        let label: string
        if (middle === '') {
          streamId = 'image'
          label = 'Image'
        } else if (middle.startsWith('.')) {
          streamId = middle.slice(1)
          label = titleCase(streamId)
        } else {
          // Belongs to a different log whose stem merely shares a prefix.
          continue
        }

        if (!streams.has(streamId)) {
          streams.set(streamId, { id: streamId, label, file: join(directory, name) })
        }
      }
    }

    // Default stream first, then alphabetical.
    return [...streams.values()].sort((a, b) => {
      if ((a.id === 'image') !== (b.id === 'image')) {
        return a.id === 'image' ? -1 : 1
      }
      return a.id < b.id ? -1 : a.id > b.id ? 1 : 0
    })
  }

  async hasImage(stem: string): Promise<boolean> {
    return (await this.imageStreams(stem)).length > 0
  }

  /* ─────────────────────────────────────────────────────── persistence ─── */

  /** Update the axis/slider selections held in the manifest. */
  updateTableView(values: Dict): void {
    const table = (this.raw.table ??= {})
    for (const key of TABLE_VIEW_KEYS) {
      if (key in values) {
        table[key] = values[key]
      }
    }
  }

  /**
   * Write the manifest back to its case directory.
   *
   * The parsed object is written as-is rather than rebuilt, so unknown blocks,
   * key order and anything a later version adds all survive.
   *
   * @returns The path written.
   */
  async save(): Promise<string> {
    const path = join(this.caseDir, MANIFEST_NAME)

    // Four-space indent and a trailing newline, matching what the Python
    // wrote, so saving does not reflow a dataset. `\n` explicitly:
    // the view saves on every axis change, and letting the platform translate
    // would rewrite every line as a side effect of moving a picker.
    await fs.writeFile(path, JSON.stringify(this.raw, null, 4) + '\n', 'utf8')
    return path
  }
}

/**
 * Suffixes a case uses for sidecars that share the table's file extension.
 *
 * The file picker lists tables by extension, which was unambiguous while every
 * sidecar was an `.h5` or an `.mp4`. The reference pose is Parquet like the
 * table, so it has to be named out or it shows up in the picker as a log --
 * one with none of the columns the manifest describes.
 */
export async function tableSidecarSuffixes(caseDir: string): Promise<string[]> {
  const suffixes = [DEFAULT_REFERENCE_SUFFIX]
  try {
    const manifest = await Manifest.load(caseDir)
    suffixes.push(manifest.referenceSuffix)
  } catch {
    // No readable manifest: the picker must still not offer the defaults.
  }
  return [...new Set(suffixes.filter(Boolean).map((s) => s.toLowerCase()))].sort()
}

/** `sensor_1` -> `Sensor 1`, matching Python's `str.title()` on the same input. */
function titleCase(value: string): string {
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase())
}
