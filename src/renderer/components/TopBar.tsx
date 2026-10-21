// The top bar: who we are, what is open, and the theme.
//
// The breadcrumb is the case picker, as it was in the Dash top bar -- the path
// is the only thing worth showing there, so clicking it is the obvious way to
// change it rather than hiding that behind a separate button.

import { useEffect, useState } from 'react'

import { buildTable, type Column } from '@shared/table'
import { buildFrameOwners } from '@shared/logs'
import type { CaseSummary, LogSummary } from '@shared/types'

import { ExportMenu } from './ExportMenu'
import { IconButton } from './Controls'
import { useMenu } from '../useMenu'
import { useStore } from '../store'

export function TopBar() {
  const dir = useStore((s) => s.dir)
  const stem = useStore((s) => s.stem)
  const stems = useStore((s) => s.stems)
  const openLog = useStore((s) => s.openLog)
  const summary = useStore((s) => s.summary)
  const setSummary = useStore((s) => s.setSummary)
  const [theme, setTheme] = useState('dark')
  const [error, setError] = useState<string | null>(null)
  const picker = useMenu()

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
    await openLogs(scan.data, [first])
  }

  /**
   * Read one or more logs of an already-scanned case.
   *
   * Takes the summary rather than reading it from the store, because the one
   * caller that has just scanned a case would otherwise race its own write.
   *
   * Combining concatenates the rows, so a frame id becomes the only thing
   * tying a slider position back to the log whose sidecars hold its cloud,
   * pose, curves and video. The owner map is read by projection before the
   * tables are: one column per file rather than the files themselves.
   *
   * @param scan The case.
   * @param chosen The logs to open, primary first.
   */
  async function openLogs(scan: CaseSummary, chosen: LogSummary[]) {
    setError(null)
    if (chosen.length === 0) {
      return
    }
    const primary = chosen[0]!
    const stems = chosen.map((log) => log.stem)

    const read = await window.sensorview.data('readTable', {
      path: chosen.map((log) => log.file)
    })
    if (!read.ok || !read.data) {
      setError(read.error ?? 'could not read the table')
      return
    }

    // Only worth asking when there is more than one log: with one, every
    // frame belongs to it, which is what `buildFrameOwners` assumes for a
    // null map anyway.
    let owners: Record<string, string[]> | null = null
    if (chosen.length > 1) {
      const result = await window.sensorview.data('logFrameOwners', {
        dir: scan.dir,
        stems
      })
      if (result.ok && result.data) {
        owners = result.data
      }
    }

    try {
      const table = buildTable(read.data.rows, read.data.columns as Column[], scan.frameKey)
      const { ownerSets } = buildFrameOwners(table.frameIds, owners, primary.stem)
      openLog({
        dir: scan.dir,
        stem: primary.stem,
        stems,
        ownerSets,
        table,
        keys: scan.keys,
        axes: pickAxes(table, scan.frameKey),
        // Case-wide styling, but only when some open log has a cloud beside
        // it -- otherwise the rail offers a switch for a file that is not
        // there.
        cloudDisplay: chosen.some((log) => log.hasCloud) ? scan.cloud : null
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
  const logs = summary?.logs ?? []

  return (
    <header className="sv-topbar">
      <div className="sv-brand">
        <span className="sv-brand-name">SensorView</span>
      </div>

      {/* Two targets, not one: the case name reopens the dialog and the stem
          picks among the logs already found. They read as one breadcrumb
          because they are one path. */}
      <div className="sv-breadcrumb" ref={picker.containerRef}>
        <button type="button" className="sv-crumb-btn" onClick={choose} title={dir ?? undefined}>
          <span className="sv-crumb">{name ?? 'No case'}</span>
        </button>
        <span className="sv-crumb-sep">/</span>
        <button
          type="button"
          className="sv-crumb-btn"
          disabled={logs.length === 0}
          {...picker.triggerProps}
          onClick={() => (logs.length > 1 ? picker.toggle() : choose())}
          title={logs.length > 1 ? `${logs.length} logs in this case` : undefined}
        >
          <span className={`sv-crumb sv-crumb-file${stem ? '' : ' sv-crumb-empty'}`}>
            {stem ?? 'open a case …'}
          </span>
          {/* Combined logs are named by a count rather than a list: the
              breadcrumb is a path, and three stems in it stop reading as
              one. */}
          {stems.length > 1 && (
            <span
              className="sv-crumb-more"
              title={`${stems.length - 1} more log${stems.length === 2 ? '' : 's'} combined`}
            >
              +{stems.length - 1}
            </span>
          )}
          {logs.length > 1 && (
            <i className="bi bi-chevron-down sv-crumb-caret" aria-hidden="true" />
          )}
        </button>

        {picker.open && summary && (
          <div className="sv-menu" role="menu" ref={picker.menuRef}>
            {logs.map((log) => {
              const at = stems.indexOf(log.stem)
              const open = at !== -1
              return (
                <div
                  key={log.stem}
                  role="none"
                  className={`sv-menu-item sv-menu-combine${open ? ' sv-menu-item-on' : ''}`}
                >
                  {/* Two targets per row. The checkbox combines a log with
                      what is already open; the label opens it alone and
                      makes it primary. One control could not say both, and
                      combining is the thing that needs explaining -- so the
                      common choice stays a plain click on the name. */}
                  <input
                    type="checkbox"
                    role="menuitemcheckbox"
                    checked={open}
                    aria-label={`Combine ${log.stem}`}
                    title={open ? 'Remove from the combination' : 'Combine with the open logs'}
                    onChange={() => {
                      const next = open
                        ? stems.filter((name) => name !== log.stem)
                        : [...stems, log.stem]
                      // Removing the last one would leave nothing loaded,
                      // which is not a state the rest of the app has.
                      if (next.length === 0) {
                        return
                      }
                      picker.close()
                      void openLogs(
                        summary,
                        next
                          .map((name) => logs.find((entry) => entry.stem === name))
                          .filter((entry): entry is LogSummary => Boolean(entry))
                      )
                    }}
                  />
                  <button
                    type="button"
                    role="menuitemradio"
                    aria-checked={log.stem === stem}
                    className="sv-menu-open"
                    onClick={() => {
                      picker.close()
                      if (stems.length !== 1 || log.stem !== stem) {
                        void openLogs(summary, [log])
                      }
                    }}
                  >
                    <span className="sv-menu-label">{log.stem}</span>
                  </button>
                  {/* Which log leads. Everything with room for one answer --
                      the cloud, the pose, an export -- reads the primary. */}
                  {at === 0 && stems.length > 1 && (
                    <span className="sv-menu-primary" title="Primary log">
                      <span aria-hidden="true">1st</span>
                      <span className="sv-sr-only">Primary log</span>
                    </span>
                  )}
                  {/* What this log has beside its table, so the choice is
                      made on what is in it rather than on the name alone. */}
                  <span className="sv-menu-marks">
                    {log.hasCloud && <Mark icon="cloud" name="point cloud" />}
                    {log.hasImage && <Mark icon="camera-video" name="camera" />}
                    {log.hasCurve && <Mark icon="graph-up" name="curves" />}
                    {log.hasReference && <Mark icon="car-front" name="reference pose" />}
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {error && (
        <span className="sv-topbar-error" role="alert" title={error}>
          <i className="bi bi-exclamation-triangle-fill" aria-hidden="true" />
          {error}
        </span>
      )}

      <div className="sv-topbar-spacer" />

      <div className="sv-topbar-actions">
        <ExportMenu />
        <IconButton
          icon={theme === 'dark' ? 'moon-fill' : 'sun-fill'}
          title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
          onClick={flipTheme}
        />
      </div>
    </header>
  )
}

/** One capability marker: a glyph for the eye, a word for everything else. */
function Mark({ icon, name }: { icon: string; name: string }) {
  return (
    <i className={`bi bi-${icon}`} role="img" aria-label={name} title={name} />
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
