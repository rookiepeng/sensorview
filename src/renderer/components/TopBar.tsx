// The top bar: who we are, what is open, and the theme.
//
// The breadcrumb is the case picker, as it was in the Dash top bar -- the path
// is the only thing worth showing there, so clicking it is the obvious way to
// change it rather than hiding that behind a separate button.


import { useEffect, useRef, useState } from 'react'
import { DropdownMenu } from 'radix-ui'

import { buildTable, type Column } from '@shared/table'
import { pickAxes } from '@shared/axes'
import { buildFrameOwners } from '@shared/logs'
import type { CaseSummary, LogSummary } from '@shared/types'

import { ColumnConfig } from './ColumnConfig'
import { ExportMenu } from './ExportMenu'
import { IconButton } from './Controls'
import { Welcome } from './Welcome'
import { useStore } from '../store'
import logo from '../assets/logo.svg'

export function TopBar() {
  const dir = useStore((s) => s.dir)
  const stem = useStore((s) => s.stem)
  const stems = useStore((s) => s.stems)
  const pendingFrameKey = useStore((s) => s.pendingFrameKey)
  const clearFrameKey = useStore((s) => s.clearFrameKey)
  const openLog = useStore((s) => s.openLog)
  const summary = useStore((s) => s.summary)
  const setSummary = useStore((s) => s.setSummary)
  const frameCount = useStore((s) => s.frameCount)
  const [theme, setTheme] = useState('dark')
  const [error, setError] = useState<string | null>(null)
  // Cases to offer on an empty window, and the one being read, which is what
  // the plate says while a case is on its way.
  const [recent, setRecent] = useState<string[]>([])
  const [opening, setOpening] = useState<string | null>(null)
  // Opening a case is up to three IPC round trips and a whole-table build,
  // with nothing on screen saying so: the breadcrumb kept the old case's
  // name and stayed clickable, so a second click reopened the dialog
  // mid-load.
  const [busy, setBusy] = useState(false)
  // And two overlapping reads raced to call `openLog`, last to finish
  // winning regardless of which was asked for last.
  const load_id = useRef(0)
  const [picking, setPicking] = useState(false)

  useEffect(() => {
    void window.sensorview.settings.get().then((stored) => {
      if (stored.ok && stored.data) {
        setTheme(stored.data.theme)
        document.documentElement.setAttribute('data-bs-theme', stored.data.theme)
      }
    })
  }, [])

  // The case the app comes up on: one named at startup, or the last one
  // opened. Main decides which and authorises it; this only loads what it is
  // given. Runs once.
  useEffect(() => {
    void window.sensorview.initialCase().then(async (initial) => {
      if (initial.ok && initial.data) {
        void load(initial.data)
      }
      // After, not before: resolving the initial case is also what drops
      // directories that have been moved or deleted, and offering one of
      // those on the plate would be offering a case that cannot open.
      const stored = await window.sensorview.settings.get()
      if (stored.ok && stored.data) {
        setRecent(stored.data.recent.slice(0, MAX_OFFERED))
      }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function choose() {
    setError(null)
    const chosen = await window.sensorview.openCase()
    if (!chosen.ok || !chosen.data) {
      return
    }
    // Opening is what moves a case to the front of the list main keeps, so
    // the plate behind this reads it back rather than guessing at the order.
    void window.sensorview.settings
      .get()
      .then((stored) => stored.ok && setRecent(stored.data!.recent.slice(0, MAX_OFFERED)))
    await load(chosen.data)
  }

  /** True while this call is still the newest one. */
  function claim(): () => boolean {
    const mine = ++load_id.current
    setBusy(true)
    return () => mine === load_id.current
  }

  /** Scan a case and open the first of its logs. */
  async function load(caseDir: string) {
    setError(null)
    setOpening(caseDir)
    const mine = claim()
    const scan = await window.sensorview.data('scanCase', { dir: caseDir })
    if (!mine()) {
      return
    }
    if (!scan.ok || !scan.data) {
      setBusy(false)
      setOpening(null)
      setError(scan.error ?? 'could not read the case')
      return
    }

    const first = scan.data.logs[0]
    if (!first) {
      setBusy(false)
      setOpening(null)
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
  async function openLogs(scan: CaseSummary, chosen: LogSummary[], frameKey?: string) {
    setError(null)
    if (chosen.length === 0) {
      return
    }
    const mine = claim()
    const primary = chosen[0]!
    const stems = chosen.map((log) => log.stem)

    const read = await window.sensorview.data('readTable', {
      path: chosen.map((log) => log.file)
    })
    if (!mine()) {
      return
    }
    if (!read.ok || !read.data) {
      setBusy(false)
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
      if (!mine()) {
        return
      }
      if (result.ok && result.data) {
        owners = result.data
      }
    }

    setBusy(false)
    try {
      // A frame key the user chose in the column config overrides the
      // manifest's, since the manifest has just been told about it too.
      const key = frameKey ?? scan.frameKey
      const table = buildTable(read.data.rows, read.data.columns as Column[], key)
      const { ownerSets } = buildFrameOwners(table.frameIds, owners, primary.stem)
      openLog({
        dir: scan.dir,
        stem: primary.stem,
        stems,
        ownerSets,
        table,
        keys: scan.keys,
        axes: pickAxes(table, key, scan.axes),
        // Case-wide styling, but only when some open log has a cloud beside
        // it -- otherwise the rail offers a switch for a file that is not
        // there.
        cloudDisplay: chosen.some((log) => log.hasCloud) ? scan.cloud : null
      })
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : String(problem))
    }
  }

  // The column config can change which column indexes the frames, which means
  // rebuilding the table -- and only this component knows how to load one.
  useEffect(() => {
    if (!pendingFrameKey || !summary) {
      return
    }
    const chosen = stems
      .map((name) => summary.logs.find((log) => log.stem === name))
      .filter((log): log is LogSummary => Boolean(log))
    clearFrameKey()
    if (chosen.length > 0) {
      void openLogs(summary, chosen, pendingFrameKey)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingFrameKey])

  function flipTheme() {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    document.documentElement.setAttribute('data-bs-theme', next)
    void window.sensorview.settings.set({ theme: next })
  }

  const name = dir ? dir.split(/[\\/]/).filter(Boolean).pop() : null
  const logs = summary?.logs ?? []

  return (
    <>
      {/* The window with nothing in it, which is a first run or a case that
          has been moved. Rendered from here because opening one is this
          component's job, not because it belongs in the bar. */}
      {frameCount === 0 && (
        <Welcome
          recent={recent}
          busy={busy}
          opening={opening}
          onOpen={() => void choose()}
          onPick={(dir) => void load(dir)}
        />
      )}
      <header className="sv-topbar">
        <div className="sv-brand">
          {/* Decorative: the name beside it already says what it is. */}
          <img className="sv-brand-logo" src={logo} alt="" draggable={false} />
          <span className="sv-brand-name">SensorView</span>
        </div>

        {/* Two targets, not one: the case name reopens the dialog and the stem
            picks among the logs already found. They read as one breadcrumb
            because they are one path. */}
        <DropdownMenu.Root open={picking} onOpenChange={setPicking} modal={false}>
        <div className="sv-breadcrumb">
          <button
            type="button"
            className="sv-crumb-btn"
            onClick={choose}
            disabled={busy}
            title={dir ?? undefined}
          >
            <span className="sv-crumb">{name ?? 'No case'}</span>
          </button>
          <span className="sv-crumb-sep">/</span>
          <DropdownMenu.Trigger asChild>
          <button
            type="button"
            className="sv-crumb-btn"
            disabled={busy || logs.length === 0}
            // One log is not a menu: there is no chevron and this reopens the
            // dialog instead. Radix opens on pointer-down, so that is where
            // the open has to be stopped.
            onPointerDown={(event) => {
              if (logs.length <= 1) {
                event.preventDefault()
              }
            }}
            onClick={() => {
              if (logs.length <= 1) {
                choose()
              }
            }}
            title={logs.length > 1 ? `${logs.length} logs in this case` : undefined}
          >
            {/* The spinner replaces the caret rather than sitting beside it:
                there is nothing to drop down while a case is being read. */}
            {busy && <i className="bi bi-arrow-repeat sv-spin" aria-hidden="true" />}
            <span className={`sv-crumb sv-crumb-file${stem ? '' : ' sv-crumb-empty'}`}>
              {busy ? 'reading …' : (stem ?? 'Open a case …')}
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
            {!busy && logs.length > 1 && (
              <i className="bi bi-chevron-down sv-crumb-caret" aria-hidden="true" />
            )}
          </button>
          </DropdownMenu.Trigger>

          {/* Portalled, so the glass top bar is not its containing block and
              Radix can keep it inside the window. `smoke.ts` finds it by
              `data-sv-menu`. */}
          {summary && (
            <DropdownMenu.Portal>
            <DropdownMenu.Content
              className="sv-menu"
              data-sv-menu="logs"
              side="bottom"
              align="start"
              sideOffset={5}
              collisionPadding={8}
            >
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
                    {/* A `CheckboxItem`, not a bare input. Radix walks its
                        own items with the arrow keys and knows nothing about
                        anything else inside the menu, so an input left to
                        itself here is reachable by mouse only -- which the
                        hand-rolled menu this replaced did not do, and which
                        the menu check in `smoke.ts` now catches.
                        `asChild` keeps the native box, so it still looks like
                        a checkbox and `smoke.ts` still finds it by `input`;
                        `readOnly` because Radix owns the state and React
                        otherwise warns about a checked box with no handler. */}
                    <DropdownMenu.CheckboxItem
                      asChild
                      checked={open}
                      onCheckedChange={() => {
                        const next = open
                          ? stems.filter((name) => name !== log.stem)
                          : [...stems, log.stem]
                        // Removing the last one would leave nothing loaded,
                        // which is not a state the rest of the app has.
                        if (next.length === 0) {
                          return
                        }
                        void openLogs(
                          summary,
                          next
                            .map((name) => logs.find((entry) => entry.stem === name))
                            .filter((entry): entry is LogSummary => Boolean(entry))
                        )
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={open}
                        readOnly
                        aria-label={`Combine ${log.stem}`}
                        title={open ? 'Remove from the combination' : 'Combine with the open logs'}
                      />
                    </DropdownMenu.CheckboxItem>
                    {/* `asChild`, so the markup `smoke.ts` reads is
                        untouched. The role stays `menuitemradio` rather than
                        taking Radix's `menuitem`: what it says is which log
                        leads, and that is still true. */}
                    <DropdownMenu.Item
                      asChild
                      onSelect={() => {
                        if (stems.length !== 1 || log.stem !== stem) {
                          void openLogs(summary, [log])
                        }
                      }}
                    >
                      <button
                        type="button"
                        role="menuitemradio"
                        aria-checked={log.stem === stem}
                        className="sv-menu-open"
                      >
                        <span className="sv-menu-label">{log.stem}</span>
                      </button>
                    </DropdownMenu.Item>
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
            </DropdownMenu.Content>
            </DropdownMenu.Portal>
          )}
        </div>
        </DropdownMenu.Root>

        {error && (
          <span className="sv-topbar-error" role="alert" title={error}>
            <i className="bi bi-exclamation-triangle-fill" aria-hidden="true" />
            {error}
          </span>
        )}

        <div className="sv-topbar-spacer" />

        <div className="sv-topbar-actions">
          <ColumnConfig />
          <ExportMenu />
          <IconButton
            icon={theme === 'dark' ? 'moon-fill' : 'sun-fill'}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
            onClick={flipTheme}
          />
        </div>
      </header>
    </>
  )
}

/** How many recent cases the empty window offers. A list, not a history. */
const MAX_OFFERED = 5

/** One capability marker: a glyph for the eye, a word for everything else. */
function Mark({ icon, name }: { icon: string; name: string }) {
  return (
    <i className={`bi bi-${icon}`} role="img" aria-label={name} title={name} />
  )
}
