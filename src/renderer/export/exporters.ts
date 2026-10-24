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
import type { DataParams } from '@shared/types'

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
 * The rows being exported, column by column, for the Parquet writer.
 *
 * The same shapes `readTable` hands over, narrowed to `rows`: the data
 * process turns NaN back into null and codes back into text, so all this
 * does is copy. A categorical keeps its full dictionary rather than being
 * re-coded, because the codes are dropped on the other side anyway.
 */
export function tableColumns(table: Table, rows: Int32Array): ExportColumn[] {
  return [...table.columns.values()].map((column) => {
    if (column.kind === 'number') {
      const values = new Float64Array(rows.length)
      for (let i = 0; i < rows.length; i++) {
        values[i] = column.values[rows[i]!]!
      }
      return { name: column.name, kind: 'number', values }
    }
    const codes = new Int32Array(rows.length)
    for (let i = 0; i < rows.length; i++) {
      codes[i] = column.codes[rows[i]!]!
    }
    return { name: column.name, kind: 'string', codes, levels: column.levels }
  })
}

/** One column as `tableColumns` hands it to the data process. */
export type ExportColumn = DataParams<'tableParquet'>['columns'][number]

/**
 * A figure's layout, put on paper.
 *
 * On screen the figures are transparent over the app's glass, with ink and
 * grid picked for the theme. A file has no glass behind it, so an exported
 * figure is always the light theme on white -- the same picture whether it
 * was taken in the dark theme or not, and one that prints. The caller
 * builds the figure with the light theme; this fills in what is behind it.
 *
 * @param layout The light-theme layout, as the view or curve built it.
 * @param title Drawn at the top of the figure when given, with room made
 *     for it.
 */
export function onPaper(
  layout: Record<string, unknown>,
  title?: string
): Record<string, unknown> {
  const paper: Record<string, unknown> = {
    ...layout,
    paper_bgcolor: '#ffffff',
    plot_bgcolor: '#ffffff'
  }
  if (title) {
    const margin = (layout.margin as Record<string, number> | undefined) ?? {}
    paper.title = {
      text: title,
      x: 0,
      xref: 'paper',
      xanchor: 'left',
      y: 1,
      yref: 'container',
      yanchor: 'top',
      pad: { t: 8 },
      font: { size: 13, color: '#12161c' }
    }
    // Room above whatever the layout already keeps there -- the curves'
    // legend row, a thinned scatter's note -- so the title sits over them.
    paper.margin = { ...margin, t: (margin.t ?? 10) + 26 }
  }
  return paper
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
  html, body { margin: 0; height: 100%; background: #ffffff; color: #12161c;
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
