// numpy's histogram machinery, as much of it as the views use.
//
// This is the only real numeric port in the view layer, and the one that is
// easiest to get subtly wrong: a bin width that is a few percent off still
// draws a plausible histogram, just not the same one. So it follows numpy's
// own source step for step, and the tests assert against values captured from
// numpy rather than against anything derived here.
//
// The `auto` estimator is numpy's current one -- Freedman-Diaconis, floored at
// half the square-root estimate to stop it producing thousands of bins, then
// capped by Sturges. An older numpy picked between FD and Sturges with no
// sqrt term; this matches the version the Dash app actually runs, because the
// point is for the two to draw the same picture.

/** Peak-to-peak: numpy's `_ptp`. */
function ptp(sorted: Float64Array): number {
  return sorted.length === 0 ? 0 : sorted[sorted.length - 1]! - sorted[0]!
}

/**
 * numpy's `percentile` with its default linear interpolation.
 *
 * @param sorted Ascending finite values.
 * @param q Percentile in [0, 100].
 */
export function percentile(sorted: Float64Array, q: number): number {
  const n = sorted.length
  if (n === 0) {
    return NaN
  }
  if (n === 1) {
    return sorted[0]!
  }
  const virtual = ((n - 1) * q) / 100
  const low = Math.floor(virtual)
  const high = Math.ceil(virtual)
  const fraction = virtual - low
  return sorted[low]! + fraction * (sorted[high]! - sorted[low]!)
}

/** Freedman-Diaconis bin width: `2 * IQR * n ** (-1/3)`. */
function fdWidth(sorted: Float64Array): number {
  const iqr = percentile(sorted, 75) - percentile(sorted, 25)
  return 2 * iqr * Math.pow(sorted.length, -1 / 3)
}

/** Sturges bin width: `ptp / (log2(n) + 1)`. */
function sturgesWidth(sorted: Float64Array): number {
  return ptp(sorted) / (Math.log2(sorted.length) + 1)
}

/** Square-root bin width: `ptp / sqrt(n)`. */
function sqrtWidth(sorted: Float64Array): number {
  return ptp(sorted) / Math.sqrt(sorted.length)
}

/** numpy's `auto`: FD, floored at half the sqrt estimate, capped by Sturges. */
function autoWidth(sorted: Float64Array): number {
  const corrected = Math.max(fdWidth(sorted), sqrtWidth(sorted) / 2)
  return Math.min(corrected, sturgesWidth(sorted))
}

/**
 * numpy's `_get_outer_edges`.
 *
 * @returns `[first, last]`. An empty input is `[0, 1]`, and a constant one is
 *     widened by half either way -- otherwise the bin width divides by zero.
 */
export function outerEdges(sorted: Float64Array): [number, number] {
  if (sorted.length === 0) {
    return [0, 1]
  }
  let first = sorted[0]!
  let last = sorted[sorted.length - 1]!
  if (first === last) {
    first -= 0.5
    last += 0.5
  }
  return [first, last]
}

/**
 * numpy's `linspace` with `endpoint=True`.
 *
 * Written out rather than accumulated, and with the last value assigned
 * exactly: `start + i * step` drifts, and a bin edge that misses the data's
 * maximum by an ulp drops the largest sample out of the histogram.
 */
export function linspace(start: number, stop: number, num: number): Float64Array {
  const out = new Float64Array(num)
  if (num === 0) {
    return out
  }
  if (num === 1) {
    out[0] = start
    return out
  }
  const step = (stop - start) / (num - 1)
  for (let i = 0; i < num; i++) {
    out[i] = start + i * step
  }
  out[num - 1] = stop
  return out
}

/**
 * `np.histogram_bin_edges(values, bins='auto')`.
 *
 * @param values Finite values; callers drop NaN first, as numpy's callers do.
 * @returns Ascending edges, one more than the bin count.
 */
export function histogramBinEdges(values: Float64Array): Float64Array {
  const sorted = Float64Array.from(values).sort()
  const [first, last] = outerEdges(sorted)

  const width = sorted.length === 0 ? 0 : autoWidth(sorted)
  // numpy tests the width for truthiness, so a zero width -- every value the
  // same, or an IQR and a range of nothing -- is one bin rather than an
  // infinite count.
  const bins = width ? Math.ceil((last - first) / width) : 1

  return linspace(first, last, bins + 1)
}

/**
 * `np.histogram2d(x, y, bins=[xEdges, yEdges])`.
 *
 * @returns Counts indexed `[xBin * yBins + yBin]`, as numpy's `(nx, ny)`.
 */
export function histogram2d(
  x: Float64Array,
  y: Float64Array,
  xEdges: Float64Array,
  yEdges: Float64Array
): Float64Array {
  const nx = xEdges.length - 1
  const ny = yEdges.length - 1
  const counts = new Float64Array(Math.max(0, nx * ny))
  if (nx <= 0 || ny <= 0) {
    return counts
  }

  for (let i = 0; i < x.length; i++) {
    const bx = binOf(x[i]!, xEdges, nx)
    if (bx < 0) {
      continue
    }
    const by = binOf(y[i]!, yEdges, ny)
    if (by < 0) {
      continue
    }
    counts[bx * ny + by]! += 1
  }
  return counts
}

/**
 * Which bin a value falls in, numpy's way.
 *
 * Bins are half-open except the last, which includes its right edge -- so the
 * maximum sample lands in the top bin rather than outside every one of them.
 */
function binOf(value: number, edges: Float64Array, bins: number): number {
  if (!Number.isFinite(value) || value < edges[0]! || value > edges[bins]!) {
    return -1
  }
  if (value === edges[bins]) {
    return bins - 1
  }

  // Binary search: the edges are ascending and a frame can carry tens of
  // thousands of samples.
  let low = 0
  let high = bins
  while (low < high) {
    const mid = (low + high) >> 1
    if (value < edges[mid]!) {
      high = mid
    } else {
      low = mid + 1
    }
  }
  return low - 1
}
