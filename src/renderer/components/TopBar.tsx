// The top bar: who we are, what is open, and the theme.
//
// The breadcrumb is the case picker, as it was in the Dash top bar -- the path
// is the only thing worth showing there, so clicking it is the obvious way to
// change it rather than hiding that behind a separate button.

import { useEffect, useRef, useState } from 'react'

import { buildTable, type Column } from '@shared/table'
import type { CaseSummary, LogSummary } from '@shared/types'

import { useStore } from '../store'

export function TopBar() {
  const dir = useStore((s) => s.dir)
  const stem = useStore((s) => s.stem)
  const openLog = useStore((s) => s.openLog)
  const summary = useStore((s) => s.summary)
  const setSummary = useStore((s) => s.setSummary)
  const [theme, setTheme] = useState('dark')
  const [error, setError] = useState<string | null>(null)
  const [picking, setPicking] = useState(false)
  const menu = useRef<HTMLDivElement>(null)

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

  /** Scan a case and open the first of its logs. */
  async function load(caseDir: string) {
    setError(null)
    const scan = await window.sensorview.data('scanCase', { dir: caseDir })
    if (!scan.ok || !scan.data) {
      setError(scan.error ?? 'could not read the case')
      return
    }

    const first = scan.data.logs[0]
    if (!first) {
      setError('no logs in that folder')
      return
    }

    setSummary(scan.data)
    await openOne(scan.data, first)
  }

  /**
   * Read one log of an already-scanned case.
   *
   * Takes the summary rather than reading it from the store, because the one
   * caller that has just scanned a case would otherwise race its own write.
   */
  async function openOne(scan: CaseSummary, log: LogSummary) {
    setError(null)
    const read = await window.sensorview.data('readTable', { path: log.file })
    if (!read.ok || !read.data) {
      setError(read.error ?? 'could not read the table')
      return
    }

    try {
      const table = buildTable(read.data.rows, read.data.columns as Column[], scan.frameKey)
      openLog({
        dir: scan.dir,
        stem: log.stem,
        table,
        keys: scan.keys,
        axes: pickAxes(table, scan.frameKey),
        // Case-wide styling, but only for a log that has a cloud beside it --
        // otherwise the rail offers a switch for a file that is not there.
        cloudDisplay: log.hasCloud ? scan.cloud : null
      })
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : String(problem))
    }
  }

  useEffect(() => {
    if (!picking) {
      return
    }
    const close = (event: MouseEvent) => {
      if (!menu.current?.contains(event.target as Node)) {
        setPicking(false)
      }
    }
    // Captured, so a click on something that stops propagation still closes
    // the menu rather than leaving it open over the thing just clicked.
    document.addEventListener('mousedown', close, true)
    return () => document.removeEventListener('mousedown', close, true)
  }, [picking])

  function flipTheme() {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    document.documentElement.setAttribute('data-bs-theme', next)
    void window.sensorview.settings.set({ theme: next })
  }

  const name = dir ? dir.split(/[\\/]/).filter(Boolean).pop() : null
  const logs = summary?.logs ?? []

  return (
    <header className="sv-topbar">
      <div className="sv-brand">
        <span className="sv-brand-name">SensorView</span>
      </div>

      {/* Two targets, not one: the case name reopens the dialog and the stem
          picks among the logs already found. They read as one breadcrumb
          because they are one path. */}
      <div className="sv-breadcrumb" ref={menu}>
        <button type="button" className="sv-crumb-btn" onClick={choose} title={dir ?? undefined}>
          <span className="sv-crumb">{name ?? 'No case'}</span>
        </button>
        <span className="sv-crumb-sep">/</span>
        <button
          type="button"
          className="sv-crumb-btn"
          disabled={logs.length === 0}
          aria-haspopup="menu"
          aria-expanded={picking}
          onClick={() => (logs.length > 1 ? setPicking((open) => !open) : choose())}
          title={logs.length > 1 ? `${logs.length} logs in this case` : undefined}
        >
          <span className={`sv-crumb sv-crumb-file${stem ? '' : ' sv-crumb-empty'}`}>
            {stem ?? 'open a case …'}
          </span>
          {logs.length > 1 && <i className="bi bi-chevron-down sv-crumb-caret" />}
        </button>

        {picking && summary && (
          <div className="sv-menu" role="menu">
            {logs.map((log) => (
              <button
                type="button"
                role="menuitemradio"
                aria-checked={log.stem === stem}
                key={log.stem}
                className={`sv-menu-item${log.stem === stem ? ' sv-menu-item-on' : ''}`}
                onClick={() => {
                  setPicking(false)
                  if (log.stem !== stem) {
                    void openOne(summary, log)
                  }
                }}
              >
                <span className="sv-menu-label">{log.stem}</span>
                {/* What this log has beside its table, so the choice is made
                    on what is in it rather than on the name alone. */}
                <span className="sv-menu-marks">
                  {log.hasCloud && <i className="bi bi-cloud" title="point cloud" />}
                  {log.hasImage && <i className="bi bi-camera-video" title="camera" />}
                  {log.hasCurve && <i className="bi bi-graph-up" title="curves" />}
                  {log.hasReference && <i className="bi bi-car-front" title="reference pose" />}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

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
