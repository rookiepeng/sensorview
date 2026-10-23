// Turning what is on screen into a file.
//
// Everything here is pure: it takes the table or a figure and returns the
// bytes. Where those bytes go is the save dialog's business, which lives in
// main -- so an exporter can be tested without a window and without writing
// anything to disk.
//
// The exports rebuild from the data rather than reading back what a library
// has on the page. The Dash exports learned that the hard way: they took
// `State("scatter3d", "figure")`, which worked only while Plotly was the thing
// drawing, and `tests/test_export_rebuild.py` exists to say so. The same rule
// holds here for a different reason -- the scene is three.js and has no
// figure to read back at all.

import { toCsv, csvNumber } from '@shared/csv'
import type { ColumnMeta, Table } from '@shared/table'

/**
 * The filtered table as CSV, every column, in table order.
 *
 * Column headers are the file's own names, not the manifest's descriptions: a
 * CSV is read by something else, and "East (m)" is a label for a person while
 * `X` is what the next tool will look for.
 *
 * @param table The open log.
 * @param rows The rows the filters kept.
 * @param keys Manifest metadata, read only for each column's decimals.
 */
export function tableCsv(
  table: Table,
  rows: Int32Array,
  keys: Record<string, ColumnMeta>
): string {
  const columns = [...table.columns.values()]
  const header = columns.map((column) => column.name)

  function* lines(): Generator<string[]> {
    for (let i = 0; i < rows.length; i++) {
      const row = rows[i]!
      yield columns.map((column) =>
        column.kind === 'number'
          ? csvNumber(column.values[row]!, keys[column.name]?.decimal)
          : (column.levels[column.codes[row]!] ?? '')
      )
    }
  }

  return toCsv(header, lines())
}

/**
 * A Plotly figure as a standalone HTML page.
 *
 * The library is inlined rather than linked, which is what "self-contained"
 * has to mean for a file that gets attached to an email and opened on a
 * machine with no network. It is ~4.7 MB, which is the same bargain
 * `write_html(include_plotlyjs=True)` struck in the Python.
 *
 * @param figure Data and layout, as a dock view built them.
 * @param title Page title, shown in the tab.
 * @param plotlyJs The library's source.
 */
export function standaloneHtml(
  figure: { data: unknown[]; layout: Record<string, unknown> },
  title: string,
  plotlyJs: string
): string {
  // Typed arrays do not survive JSON, so they are spread into plain ones on
  // the way out. Without this every trace ships as `{"0":1,"1":2,…}` and the
  // exported page draws nothing.
  const payload = JSON.stringify(
    { data: figure.data, layout: { ...figure.layout, autosize: true } },
    (_key, value) => (ArrayBuffer.isView(value) ? Array.from(value as never) : value)
  )

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)}</title>
<style>
  html, body { margin: 0; height: 100%; background: #0f1319; color: #e6e9ee;
    font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif; }
  #figure { width: 100%; height: 100%; }
</style>
<script>${plotlyJs}</script>
</head>
<body>
<div id="figure"></div>
<script>
  var figure = ${payload};
  Plotly.newPlot('figure', figure.data, figure.layout, { responsive: true });
</script>
</body>
</html>
`
}

/**
 * A still of the scene, wrapped in a page that says what it is.
 *
 * The 3D view is three.js, so there is no figure to hand Plotly and no
 * kaleido to render one. The canvas itself is the picture -- which is
 * strictly better than the Python's export, because it is what was on screen
 * rather than Plotly's drawing of the same data.
 */
export function snapshotHtml(dataUrl: string, title: string, caption: string): string {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)}</title>
<style>
  html, body { margin: 0; background: #0f1319; color: #e6e9ee;
    font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif; }
  figure { margin: 0; padding: 16px; }
  img { max-width: 100%; display: block; border-radius: 6px; }
  figcaption { margin-top: 10px; font-size: 0.85rem; color: #8a929e; }
</style>
</head>
<body>
<figure>
<img src="${dataUrl}" alt="${escapeHtml(title)}">
<figcaption>${escapeHtml(caption)}</figcaption>
</figure>
</body>
</html>
`
}

/** A timestamped name, as the Dash exports built theirs. */
export function exportName(stem: string | null, kind: string, extension: string): string {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  const stamp =
    `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}` +
    `_${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
  const base = stem ? `${stem}_` : ''
  return `${base}${stamp}_${kind}.${extension}`
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}
