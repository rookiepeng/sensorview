// The loaded table, and the filter every view runs over it.
//
// Columnar, with one typed array per column: numeric columns as Float64Array,
// categorical ones as Int32Array level codes plus their dictionary. That shape
// is what makes a category filter an integer comparison rather than a string
// one, and what lets the whole filter be a single pass over contiguous memory.
//
// It lives in the renderer. Under Dash this was a pandas DataFrame on the
// server, re-filtered per callback, with per-frame slices cached to disk and a
// background worker pre-computing every frame -- an apparatus that existed
// because each filter change crossed a network boundary. The real table is
// 19,756 rows and 702 KB; filtering it is sub-millisecond, so none of that
// apparatus has a reason to exist and none of it is ported.

export interface NumericColumn {
  name: string
  kind: 'number'
  /** NaN for null, and for values that were infinite. */
  values: Float64Array
}

export interface CategoricalColumn {
  name: string
  kind: 'string'
  /** Index into `levels`; -1 for null. */
  codes: Int32Array
  levels: string[]
}

export type Column = NumericColumn | CategoricalColumn

/** Which rows a point is allowed to be in, as the visibility picker sets it. */
export type Visibility = 'visible' | 'hidden'

export interface Table {
  rows: number
  columns: Map<string, Column>

  /** Column the frames are keyed on. */
  frameKey: string
  /** Frame ids, ascending. A slider position indexes this. */
  frameIds: Float64Array
  /**
   * CSR-style frame index: the rows of frame `i` are
   * `rowOrder[frameStart[i] .. frameStart[i + 1]]`.
   *
   * Built once at load. A frame's rows are then a contiguous slice rather than
   * a scan, which is what makes scrubbing cost nothing -- the Python paid for
   * this with a per-frame disk cache.
   */
  frameStart: Int32Array
  rowOrder: Int32Array

  /**
   * Per-row visibility, as click-to-hide leaves it.
   *
   * A parallel array rather than a column, because it is the only per-row
   * state the user edits and it must not be confused with the data.
   */
  visible: Uint8Array
}

export interface NumericFilter {
  column: string
  min: number
  max: number
}

export interface CategoryFilter {
  column: string
  /** Allowed level names. Empty means nothing passes. */
  allowed: string[]
}

export interface FilterState {
  numeric: NumericFilter[]
  categorical: CategoryFilter[]
  /**
   * Visibility states to show.
   *
   * Exactly one state filters; none passes nothing; **two or more is a no-op**,
   * which is how "show hidden points as well" is expressed. That last case
   * reads like an oversight and is not -- it is how the Python behaved and how
   * the picker is meant to work.
   */
  visible?: Visibility[]
}

/**
 * Build the frame index.
 *
 * @param frameValues The frame column's values, one per row.
 * @returns Ascending frame ids and the CSR arrays addressing their rows.
 */
export function buildFrameIndex(frameValues: Float64Array): {
  frameIds: Float64Array
  frameStart: Int32Array
  rowOrder: Int32Array
} {
  const counts = new Map<number, number>()
  for (let row = 0; row < frameValues.length; row++) {
    const id = frameValues[row]!
    if (!Number.isFinite(id)) {
      // A row with no frame belongs to no slider position. Dropping it here
      // keeps every later stage from having to ask.
      continue
    }
    counts.set(id, (counts.get(id) ?? 0) + 1)
  }

  const frameIds = Float64Array.from([...counts.keys()].sort((a, b) => a - b))
  const frameStart = new Int32Array(frameIds.length + 1)
  const position = new Map<number, number>()

  let running = 0
  for (let i = 0; i < frameIds.length; i++) {
    const id = frameIds[i]!
    frameStart[i] = running
    position.set(id, running)
    running += counts.get(id)!
  }
  frameStart[frameIds.length] = running

  const rowOrder = new Int32Array(running)
  for (let row = 0; row < frameValues.length; row++) {
    const id = frameValues[row]!
    if (!Number.isFinite(id)) {
      continue
    }
    const at = position.get(id)!
    rowOrder[at] = row
    position.set(id, at + 1)
  }

  return { frameIds, frameStart, rowOrder }
}

/**
 * Assemble a table from columns read by the data layer.
 *
 * @throws Error if the frame column is missing or not numeric -- every slider
 *     position is an index into its values, so there is nothing to show
 *     without it.
 */
export function buildTable(
  rows: number,
  columns: Column[],
  frameKey: string
): Table {
  const byName = new Map(columns.map((column) => [column.name, column]))
  const frameColumn = byName.get(frameKey)

  if (!frameColumn || frameColumn.kind !== 'number') {
    throw new Error(
      `Frame column ${JSON.stringify(frameKey)} is missing or not numeric ` +
        `(columns: ${[...byName.keys()].join(', ')})`
    )
  }

  const { frameIds, frameStart, rowOrder } = buildFrameIndex(frameColumn.values)
  return {
    rows,
    columns: byName,
    frameKey,
    frameIds,
    frameStart,
    rowOrder,
    visible: new Uint8Array(rows) // 0 = visible
  }
}

/** The rows of one frame, by slider position. */
export function frameRows(table: Table, position: number): Int32Array {
  if (position < 0 || position >= table.frameIds.length) {
    return new Int32Array(0)
  }
  return table.rowOrder.subarray(table.frameStart[position]!, table.frameStart[position + 1]!)
}

/**
 * Bring a slider position inside the current frame list.
 *
 * Kept from the Python, where loading a dataset replaced the frame list and
 * reset the slider in two separate callbacks -- so for one round the old
 * position was read against the new list. React makes that race impossible,
 * but a stale position can still arrive from restored state, and clamping is
 * cheaper than auditing every path that could produce one.
 *
 * @returns A valid index, or null when there are no frames to point at.
 */
export function clampFrameIndex(frameCount: number, position: number | null): number | null {
  if (frameCount <= 0) {
    return null
  }
  if (position === null || !Number.isFinite(position)) {
    return 0
  }
  return Math.min(Math.max(Math.trunc(position), 0), frameCount - 1)
}

/**
 * Which rows pass the filters.
 *
 * One boolean pass over contiguous arrays rather than a chain of slices, which
 * is what the numpy version was doing and for the same reason: this runs on
 * every filter change.
 *
 * Three behaviours carried over deliberately, because each reads like a bug
 * and is not:
 *
 *   - A filter naming a column the table does not have is skipped, not an
 *     error. Filters are generated from the manifest and the table is the
 *     data; a manifest describing a column a particular log lacks should not
 *     stop that log opening.
 *   - An empty allowed-list on a categorical filter means nothing passes, and
 *     short-circuits the rest.
 *   - NaN fails both range comparisons, so a row with no value in a filtered
 *     column drops out. "No value" should not pass a range.
 *
 * @returns A mask, one byte per row.
 */
export function filterAll(table: Table, filters: FilterState): Uint8Array {
  const mask = new Uint8Array(table.rows).fill(1)

  for (const filter of filters.numeric) {
    const column = table.columns.get(filter.column)
    if (!column || column.kind !== 'number') {
      continue
    }
    const { values } = column
    const { min, max } = filter
    for (let row = 0; row < table.rows; row++) {
      if (mask[row] === 0) {
        continue
      }
      const value = values[row]!
      // NaN fails both, which is the intent.
      if (!(value >= min && value <= max)) {
        mask[row] = 0
      }
    }
  }

  for (const filter of filters.categorical) {
    const column = table.columns.get(filter.column)
    if (!column || column.kind !== 'string') {
      continue
    }
    if (filter.allowed.length === 0) {
      mask.fill(0)
      return mask
    }

    // Allowed levels resolved to codes once, so the inner loop is an integer
    // membership test rather than a string compare per row.
    const allowed = new Uint8Array(column.levels.length)
    for (const name of filter.allowed) {
      const code = column.levels.indexOf(name)
      if (code >= 0) {
        allowed[code] = 1
      }
    }

    const { codes } = column
    for (let row = 0; row < table.rows; row++) {
      if (mask[row] === 0) {
        continue
      }
      const code = codes[row]!
      if (code < 0 || allowed[code] !== 1) {
        mask[row] = 0
      }
    }
  }

  const wanted = filters.visible
  if (wanted) {
    if (wanted.length === 0) {
      mask.fill(0)
      return mask
    }
    // Two or more states selected is deliberately a no-op: that is how the
    // picker says "show hidden points as well".
    if (wanted.length === 1) {
      const hidden = wanted[0] === 'hidden' ? 1 : 0
      for (let row = 0; row < table.rows; row++) {
        if (mask[row] === 1 && table.visible[row] !== hidden) {
          mask[row] = 0
        }
      }
    }
  }

  return mask
}

/** Row indices of one frame that pass a mask, in frame order. */
export function visibleRows(table: Table, position: number, mask: Uint8Array): Int32Array {
  const rows = frameRows(table, position)
  let kept = 0
  for (let i = 0; i < rows.length; i++) {
    if (mask[rows[i]!] === 1) {
      kept++
    }
  }

  const out = new Int32Array(kept)
  let at = 0
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i]!
    if (mask[row] === 1) {
      out[at++] = row
    }
  }
  return out
}

/** Distinct level names of a categorical column, in the order they appear. */
export function levelsOf(table: Table, name: string): string[] {
  const column = table.columns.get(name)
  return column && column.kind === 'string' ? column.levels : []
}

/**
 * Finite range of a numeric column.
 *
 * @returns `[min, max]`, or `[0, 0]` when the column has no finite value --
 *     numpy's `nanmin` raises on an all-NaN column and the Python guarded
 *     against it, so a column of nothing gets a degenerate range rather than
 *     taking the load down.
 */
export function rangeOf(table: Table, name: string): [number, number] {
  const column = table.columns.get(name)
  if (!column || column.kind !== 'number') {
    return [0, 0]
  }

  let min = Infinity
  let max = -Infinity
  for (let row = 0; row < column.values.length; row++) {
    const value = column.values[row]!
    if (Number.isFinite(value)) {
      if (value < min) {
        min = value
      }
      if (value > max) {
        max = value
      }
    }
  }
  return Number.isFinite(min) ? [min, max] : [0, 0]
}
