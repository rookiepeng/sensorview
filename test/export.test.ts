// What the exports write.
//
// The quoting rules and the typed-array problem are the whole content: both
// produce a file that opens and looks plausible when they are wrong, which is
// the worst failure an export can have.

import pl from 'nodejs-polars'
import { describe, expect, it } from 'vitest'

import { tableParquet } from '../src/data/parquet'

import { csvField, csvNumber, toCsv } from '../src/shared/csv'
import { buildTable, type Column } from '../src/shared/table'
import {
  exportName,
  onPaper,
  standaloneHtml,
  tableColumns,
  tableCsv
} from '../src/renderer/export/exporters'

describe('csvField', () => {
  it.each([
    ['plain', 'plain'],
    ['has,comma', '"has,comma"'],
    ['has"quote', '"has""quote"'],
    ['has\nnewline', '"has\nnewline"'],
    ['has\rreturn', '"has\rreturn"'],
    // Unquoted, some readers strip it, and a column padded for alignment
    // comes back shorter than it went in.
    [' padded ', '" padded "'],
    ['', '']
  ])('%j -> %j', (input, expected) => {
    expect(csvField(input)).toBe(expected)
  })
})

describe('csvNumber', () => {
  it('writes a non-finite value as an empty cell', () => {
    // `NaN` and `Infinity` read back as text and turn the whole column into
    // strings, which is worse than a gap.
    expect(csvNumber(NaN)).toBe('')
    expect(csvNumber(Infinity)).toBe('')
    expect(csvNumber(-Infinity)).toBe('')
  })

  it('honours the manifest’s decimals', () => {
    expect(csvNumber(1.23456, 2)).toBe('1.23')
    expect(csvNumber(1.23456)).toBe('1.23456')
  })
})

describe('toCsv', () => {
  it('uses CRLF and ends with one', () => {
    // RFC 4180, and what Excel wants; the trailing newline keeps an append
    // from joining two rows.
    expect(toCsv(['a', 'b'], [['1', '2']])).toBe('a,b\r\n1,2\r\n')
  })
})

describe('tableCsv', () => {
  const table = buildTable(
    3,
    [
      { name: 'Frame', kind: 'number', values: Float64Array.from([0, 0, 1]) },
      { name: 'X', kind: 'number', values: Float64Array.from([1.23456, NaN, 3]) },
      {
        name: 'Sensor',
        kind: 'string',
        codes: Int32Array.from([0, 1, -1]),
        levels: ['front', 'rear, left']
      }
    ] as Column[],
    'Frame'
  )

  it('writes the file’s own column names, not the manifest’s labels', () => {
    // A CSV is read by something else, and "East (m)" is a label for a
    // person while `X` is what the next tool looks for.
    const csv = tableCsv(table, Int32Array.from([0]), {
      X: { description: 'East', unit: 'm' }
    })
    expect(csv.split('\r\n')[0]).toBe('Frame,X,Sensor')
  })

  it('writes only the rows it was given', () => {
    const csv = tableCsv(table, Int32Array.from([2]), {})
    expect(csv.trimEnd().split('\r\n')).toHaveLength(2)
  })

  it('rounds to the manifest’s decimals and quotes a level with a comma', () => {
    const csv = tableCsv(table, Int32Array.from([0, 1]), { X: { decimal: 2 } })
    const lines = csv.trimEnd().split('\r\n')
    expect(lines[1]).toBe('0,1.23,front')
    // NaN as a gap, and the level quoted because it carries a comma.
    expect(lines[2]).toBe('0,,"rear, left"')
  })

  it('leaves a null level as an empty cell', () => {
    const csv = tableCsv(table, Int32Array.from([2]), {})
    expect(csv.trimEnd().split('\r\n')[1]).toBe('1,3,')
  })
})

describe('tableColumns and tableParquet', () => {
  const table = buildTable(
    3,
    [
      { name: 'Frame', kind: 'number', values: Float64Array.from([0, 0, 1]) },
      { name: 'X', kind: 'number', values: Float64Array.from([1.5, NaN, 3]) },
      {
        name: 'Sensor',
        kind: 'string',
        codes: Int32Array.from([0, 1, -1]),
        levels: ['front', 'rear']
      }
    ] as Column[],
    'Frame'
  )

  it('keeps only the rows asked for, in table column order', () => {
    const columns = tableColumns(table, Int32Array.from([2, 0]))
    expect(columns.map((c) => c.name)).toEqual(['Frame', 'X', 'Sensor'])
    expect(Array.from(columns[1]!.values!)).toEqual([3, 1.5])
    expect(Array.from(columns[2]!.codes!)).toEqual([-1, 0])
  })

  it('writes a file that reads back with nulls where the gaps were', () => {
    // NaN and code -1 are how the app holds a missing value; written as
    // they are, a reader sees NaN and a level called "undefined".
    const bytes = tableParquet(tableColumns(table, Int32Array.from([0, 1, 2])))
    const back = pl.readParquet(Buffer.from(bytes))
    expect(back.columns).toEqual(['Frame', 'X', 'Sensor'])
    expect(back.getColumn('X').toArray()).toEqual([1.5, null, 3])
    expect(back.getColumn('Sensor').toArray()).toEqual(['front', 'rear', null])
  })
})

describe('onPaper', () => {
  it('puts the figure on white, whatever was behind it on screen', () => {
    const layout = onPaper({ paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)' })
    expect(layout.paper_bgcolor).toBe('#ffffff')
    expect(layout.plot_bgcolor).toBe('#ffffff')
    expect(layout.title).toBeUndefined()
  })

  it('makes room above the plot for a title', () => {
    const layout = onPaper({ margin: { l: 1, t: 22 } }, 'SNR')
    expect((layout.title as { text: string }).text).toBe('SNR')
    expect(layout.margin).toEqual({ l: 1, t: 48 })
  })
})

describe('standaloneHtml', () => {
  const figure = {
    data: [{ type: 'scatter', x: Float64Array.from([1, 2]), y: Float64Array.from([3, 4]) }],
    layout: { title: 'x' }
  }

  it('spreads typed arrays into real ones', () => {
    // JSON turns a Float64Array into {"0":1,"1":2}, and the exported page
    // then draws nothing at all.
    const html = standaloneHtml(figure, 'Title', '/* plotly */')
    expect(html).toContain('[1,2]')
    expect(html).not.toContain('"0":1')
  })

  it('inlines the library rather than linking it', () => {
    const html = standaloneHtml(figure, 'Title', 'PLOTLY_SOURCE_HERE')
    expect(html).toContain('PLOTLY_SOURCE_HERE')
    expect(html).not.toContain('<script src=')
  })

  it('is a light page', () => {
    expect(standaloneHtml(figure, 'Title', '')).toContain('background: #ffffff')
  })

  it('escapes the title', () => {
    const html = standaloneHtml(figure, '<script>x</script>', '')
    expect(html).not.toContain('<script>x</script>')
    expect(html).toContain('&lt;script&gt;')
  })
})

describe('exportName', () => {
  it('carries the log, a timestamp and the kind', () => {
    expect(exportName('scene_0061', 'table', 'csv')).toMatch(
      /^scene_0061_\d{8}_\d{6}_table\.csv$/
    )
  })

  it('still names a file with no log open', () => {
    expect(exportName(null, 'scene', 'png')).toMatch(/^\d{8}_\d{6}_scene\.png$/)
  })
})
