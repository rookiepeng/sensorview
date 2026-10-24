// Reading the table.
//
// Parquet is the only accepted table format, and polars is the same engine the
// Python used -- `nodejs-polars` is napi bindings over the same Rust crate, so
// projection and predicate pushdown behave the way `radar_store.py` relied on
// rather than the way a reimplementation would.
//
// Everything here runs in the data utility process. `nodejs-polars` is a native
// addon, which is why: a `dlopen` on the process that owns the window would
// stall it, and a fault in it would take the window with it.

import pl from 'nodejs-polars'

/** A column, as the renderer wants it. */
export interface Column {
  name: string
  kind: 'number' | 'string'
  /** Numeric values, NaN where null or non-finite. */
  values?: Float64Array
  /** Level codes into `levels`, -1 where null. */
  codes?: Int32Array
  levels?: string[]
}

export interface TableData {
  rows: number
  columns: Column[]
}

/**
 * Frame ids present in a file, sorted ascending.
 *
 * Projection-only, so this reads one column rather than the file. It is what
 * builds the frame list and the per-frame log ownership, and on a multi-GB
 * table the difference between this and a full read is the difference between
 * opening a case in a second and in a minute.
 */
export function frameIds(path: string, frameKey: string): number[] {
  const df = pl
    .scanParquet(path)
    .select(pl.col(frameKey))
    .unique()
    .collectSync()

  const ids = Array.from(df.getColumn(frameKey).toArray() as ArrayLike<number>)
  return ids.filter((v) => Number.isFinite(v)).sort((a, b) => a - b)
}

/**
 * Scan one or more Parquet files as a single frame.
 *
 * Combined logs need not carry the same columns -- a case can hold a radar
 * log and a lidar one -- so a differing schema falls back to a diagonal
 * concat, which keeps the union and null-fills the rest. Tried in that order
 * because the fast path is the common one and the fallback reads every
 * file's schema to work out the union.
 */
function scanAll(paths: string[]): pl.LazyDataFrame {
  if (paths.length === 1) {
    return pl.scanParquet(paths[0]!)
  }
  try {
    return pl.scanParquet(paths as never)
  } catch {
    return pl.concat(
      paths.map((one) => pl.scanParquet(one)),
      { how: 'diagonal' }
    )
  }
}

/**
 * Collapse a length-one List or Array column to its scalar.
 *
 * Exporters routinely write `["sensor_1"]` where they meant `"sensor_1"`, and
 * a list column breaks `unique()` and every filter downstream. The Python
 * carried the same fix-up for the same reason; a file like that is common
 * enough that refusing it would just mean refusing real datasets.
 */
function scalarize(df: pl.DataFrame): pl.DataFrame {
  const listy = df.columns.filter((name) => {
    const dtype = String(df.getColumn(name).dtype)
    return dtype.includes('List') || dtype.includes('FixedSizeList')
  })
  if (listy.length === 0) {
    return df
  }
  return df.withColumns(...listy.map((name) => pl.col(name).lst.first().alias(name)))
}

/**
 * Read a table into columnar arrays.
 *
 * Numeric columns become Float64Array with NaN for null and for the infinities
 * -- the filters compare with `>=`/`<=`, which an infinity passes and a NaN
 * does not, and "no value" should not pass a range filter. Categoricals become
 * level codes plus a dictionary, which is what makes an `isin` filter a
 * integer comparison instead of a string one.
 *
 * Several paths are concatenated, which is what combining logs means -- the
 * rows of each one after another, with a frame id the only thing left tying a
 * row back to the log it came from.
 *
 * @param path File to read, or files to combine.
 * @param columns Columns to read, or all of them.
 */
export function readTable(path: string | string[], columns?: string[]): TableData {
  let scan = scanAll(Array.isArray(path) ? path : [path])
  if (columns?.length) {
    scan = scan.select(...columns.map((name) => pl.col(name)))
  }
  const df = scalarize(scan.collectSync())

  const out: Column[] = df.columns.map((name) => {
    const series = df.getColumn(name)
    const dtype = String(series.dtype)
    const raw = series.toArray() as unknown[]

    if (dtype.includes('Utf8') || dtype.includes('String') || dtype.includes('Categorical')) {
      const levels: string[] = []
      const index = new Map<string, number>()
      const codes = new Int32Array(raw.length)
      for (let i = 0; i < raw.length; i++) {
        const value = raw[i]
        if (value === null || value === undefined) {
          codes[i] = -1
          continue
        }
        const text = String(value)
        let code = index.get(text)
        if (code === undefined) {
          code = levels.length
          levels.push(text)
          index.set(text, code)
        }
        codes[i] = code
      }
      return { name, kind: 'string', codes, levels }
    }

    const values = new Float64Array(raw.length)
    for (let i = 0; i < raw.length; i++) {
      const value = raw[i]
      const n = value === null || value === undefined ? NaN : Number(value)
      values[i] = Number.isFinite(n) ? n : NaN
    }
    return { name, kind: 'number', values }
  })

  return { rows: df.height, columns: out }
}

/**
 * Columns as a Parquet file, for the export menu.
 *
 * The renderer holds the filtered rows, so it sends them here rather than
 * this re-reading the source: a combined log has no one file to re-read, and
 * the filters and hidden points live only in the renderer. NaN goes back to
 * null and level codes back to text, undoing what `readTable` did, so the
 * file reads like the one it came from rather than like the app's memory.
 *
 * Numbers are written as Float64, which is what the app holds. An integer
 * column in the source comes back as a float of the same value.
 */
export function tableParquet(columns: Column[]): Uint8Array {
  const series = columns.map((column) => {
    if (column.kind === 'string') {
      const levels = column.levels ?? []
      const codes = column.codes ?? new Int32Array(0)
      const text = Array.from(codes, (code) => (code >= 0 ? (levels[code] ?? null) : null))
      return pl.Series(column.name, text, pl.Utf8)
    }
    return pl.Series(column.name, column.values ?? new Float64Array(0), pl.Float64)
  })
  const numeric = columns.filter((column) => column.kind === 'number').map((c) => c.name)
  let df = pl.DataFrame(series)
  if (numeric.length > 0) {
    df = df.withColumns(...numeric.map((name) => pl.col(name).fillNan(null).alias(name)))
  }
  return new Uint8Array(df.writeParquet())
}
