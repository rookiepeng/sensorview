// The top bar: who we are, what is open, and the theme.
//
// The breadcrumb is the case picker, as it was in the Dash top bar -- the path
// is the only thing worth showing there, so clicking it is the obvious way to
// change it rather than hiding that behind a separate button.

import { useEffect, useState } from 'react'

import { buildTable, type Column } from '@shared/table'

import { useStore } from '../store'

export function TopBar() {
  const dir = useStore((s) => s.dir)
  const stem = useStore((s) => s.stem)
  const openLog = useStore((s) => s.openLog)
  const [theme, setTheme] = useState('dark')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void window.sensorview.settings.get().then((stored) => {
      if (stored.ok && stored.data) {
        setTheme(stored.data.theme)
        document.documentElement.setAttribute('data-bs-theme', stored.data.theme)
      }
    })
  }, [])

  // Opening a case named at startup, so the app can come up on one without a
  // dialog. Runs once.
  useEffect(() => {
    const initial = window.sensorview.initialCase
    if (initial) {
      void load(initial)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function choose() {
    setError(null)
    const chosen = await window.sensorview.openCase()
    if (!chosen.ok || !chosen.data) {
      return
    }
    await load(chosen.data)
  }

  /**
   * Open a case and read its first log.
   *
   * One log at a time for now; the picker that chooses between them is the
   * next thing, and nothing about this changes when it arrives.
   */
  async function load(caseDir: string) {
    const summary = await window.sensorview.data('scanCase', { dir: caseDir })
    if (!summary.ok || !summary.data) {
      setError(summary.error ?? 'could not read the case')
      return
    }

    const first = summary.data.logs[0]
    if (!first) {
      setError('no logs in that folder')
      return
    }

    const read = await window.sensorview.data('readTable', { path: first.file })
    if (!read.ok || !read.data) {
      setError(read.error ?? 'could not read the table')
      return
    }

    try {
      const table = buildTable(
        read.data.rows,
        read.data.columns as Column[],
        summary.data.frameKey
      )
      openLog({
        dir: caseDir,
        stem: first.stem,
        table,
        keys: summary.data.keys,
        axes: pickAxes(table, summary.data.frameKey),
        cloudDisplay: first.hasCloud ? summary.data.cloud : null
      })
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : String(problem))
    }
  }

  function flipTheme() {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    document.documentElement.setAttribute('data-bs-theme', next)
    void window.sensorview.settings.set({ theme: next })
  }

  const name = dir ? dir.split(/[\\/]/).filter(Boolean).pop() : null

  return (
    <header className="sv-topbar">
      <div className="sv-brand">
        <span className="sv-brand-name">SensorView</span>
      </div>

      <button type="button" className="sv-breadcrumb" onClick={choose} title={dir ?? undefined}>
        <span className="sv-crumb">{name ?? 'No case'}</span>
        <span className="sv-crumb-sep">/</span>
        <span className={`sv-crumb sv-crumb-file${stem ? '' : ' sv-crumb-empty'}`}>
          {stem ?? 'open a case …'}
        </span>
      </button>

      {error && (
        <span className="sv-topbar-error" role="status">
          {error}
        </span>
      )}

      <div className="sv-topbar-spacer" />

      <div className="sv-topbar-actions">
        <button
          type="button"
          className="sv-icon-btn"
          onClick={flipTheme}
          title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
          aria-label="Toggle theme"
        >
          <i className={theme === 'dark' ? 'bi bi-moon-fill' : 'bi bi-sun-fill'} />
        </button>
      </div>
    </header>
  )
}

/**
 * Choose sensible starting axes.
 *
 * The manifest does name them, in `table.x_3d` and friends, but a log whose
 * manifest says nothing should still open -- so this falls back to the first
 * numeric columns that are not the frame key, which for a radar table is
 * almost always the position.
 */
function pickAxes(
  table: ReturnType<typeof buildTable>,
  frameKey: string
): { x: string; y: string; z: string; colour: string } {
  const numeric = [...table.columns.values()]
    .filter((column) => column.kind === 'number' && column.name !== frameKey)
    .map((column) => column.name)
  const categorical = [...table.columns.values()]
    .filter((column) => column.kind === 'string')
    .map((column) => column.name)

  const pick = (want: string, fallback: string | undefined) =>
    numeric.includes(want) ? want : (fallback ?? numeric[0] ?? frameKey)

  return {
    x: pick('X', numeric[0]),
    y: pick('Y', numeric[1]),
    z: pick('Z', numeric[2]),
    // Colour by a category when there is one: it is more legible than a
    // gradient on first open, and it shows the legend doing something.
    colour: categorical[0] ?? numeric[0] ?? frameKey
  }
}
