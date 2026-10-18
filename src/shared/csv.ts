// CSV, written the way a spreadsheet will read it back.
//
// Pure, and in `shared` rather than beside the exporter, because the quoting
// rules are the whole content of this file and they are worth a test that does
// not need a window.

/** Characters that force a field to be quoted. */
const NEEDS_QUOTES = /[",\r\n]/

/**
 * Quote one field if it needs it.
 *
 * A field containing a quote has its quotes doubled, which is RFC 4180 and
 * also what every spreadsheet actually implements. A leading or trailing
 * space is quoted too: unquoted, some readers strip it, and a column of
 * identifiers padded for alignment comes back shorter than it went in.
 */
export function csvField(value: string): string {
  if (value === '') {
    return ''
  }
  if (NEEDS_QUOTES.test(value) || value !== value.trim()) {
    return `"${value.replace(/"/g, '""')}"`
  }
  return value
}

/**
 * Format one number for a CSV cell.
 *
 * A non-finite value is written as nothing rather than as `NaN` or `Infinity`:
 * those read back as text and turn the whole column into strings, which is a
 * worse answer than an empty cell.
 */
export function csvNumber(value: number, decimals?: number): string {
  if (!Number.isFinite(value)) {
    return ''
  }
  return decimals === undefined ? String(value) : value.toFixed(decimals)
}

/**
 * Join rows into a CSV document.
 *
 * CRLF line endings, which is what RFC 4180 says and what Excel wants; a
 * trailing newline, so appending to the file does not join two rows.
 */
export function toCsv(header: string[], rows: Iterable<string[]>): string {
  const lines: string[] = [header.map(csvField).join(',')]
  for (const row of rows) {
    lines.push(row.map(csvField).join(','))
  }
  return lines.join('\r\n') + '\r\n'
}
