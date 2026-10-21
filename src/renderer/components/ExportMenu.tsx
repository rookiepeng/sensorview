// The export menu.
//
// Every entry rebuilds from the data rather than reading back what a library
// has on the page. That rule is inherited: the Dash exports took the live
// Plotly figure out of the browser, which worked only while Plotly was the
// thing drawing, and `tests/test_export_rebuild.py` was written when a second
// renderer made it wrong. Here there is no figure to read back at all.
//
// A download in the Dash app depended on an ALLOW_DOWNLOADS flag that, when
// missing, broke every export button silently. There is no flag now: main
// opens a save dialog, and a dismissed dialog is a null rather than an error.

import { useEffect, useRef, useState } from 'react'

import { filterAll } from '@shared/table'

import { maskedRows } from '../figures/common'
import { recordScene, toBase64 } from '../export/animation'
import { exportName, snapshotHtml, standaloneHtml, tableCsv } from '../export/exporters'
import { getScene } from '../sceneHandle'
import { useMenu } from '../useMenu'
import { useStore } from '../store'

/** Long enough to read a filename, short enough not to outlive its moment. */
const NOTE_MS = 6000

export function ExportMenu() {
  const table = useStore((s) => s.table)
  const filters = useStore((s) => s.filters)
  const keys = useStore((s) => s.keys)
  const stem = useStore((s) => s.stem)
  const frame = useStore((s) => s.frame)
  const frameCount = useStore((s) => s.frameCount)
  const setFrame = useStore((s) => s.setFrame)

  const menu = useMenu()
  const [busy, setBusy] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const cancelled = useRef(false)

  // "Saved foo.csv" used to sit in the top bar until the next export, which
  // made a stale success look like a live one.
  useEffect(() => {
    if (!note) {
      return
    }
    const timer = setTimeout(() => setNote(null), NOTE_MS)
    return () => clearTimeout(timer)
  }, [note])

  if (!table) {
    return null
  }

  async function save(
    name: string,
    data: string,
    encoding: 'utf8' | 'base64',
    filters?: Array<{ name: string; extensions: string[] }>
  ) {
    const result = await window.sensorview.saveFile({
      suggestedName: name,
      data,
      encoding,
      filters
    })
    if (!result.ok) {
      setNote(result.error ?? 'could not write the file')
      return
    }
    // A dismissed dialog is not a failure, and saying "cancelled" where the
    // user cancelled is noise.
    setNote(result.data ? `Saved ${name}` : null)
  }

  async function run(label: string, job: () => Promise<void>) {
    // Closing returns focus to the trigger, which is also the cancel button
    // for the job about to start -- so the keyboard lands where it is needed.
    menu.close()
    setBusy(label)
    setNote(null)
    try {
      await job()
    } catch (problem) {
      setNote(problem instanceof Error ? problem.message : String(problem))
    } finally {
      setBusy(null)
    }
  }

  const exportCsv = () =>
    run('CSV', async () => {
      const rows = maskedRows(filterAll(table!, filters))
      await save(exportName(stem, 'table', 'csv'), tableCsv(table!, rows, keys), 'utf8', [
        { name: 'CSV', extensions: ['csv'] }
      ])
    })

  const exportPng = () =>
    run('PNG', async () => {
      const dataUrl = getScene()?.snapshot()
      if (!dataUrl) {
        throw new Error('the scene is not drawing')
      }
      await save(
        exportName(stem, 'scene', 'png'),
        dataUrl.slice(dataUrl.indexOf(',') + 1),
        'base64',
        [{ name: 'PNG image', extensions: ['png'] }]
      )
    })

  const exportHtml = () =>
    run('HTML', async () => {
      const dataUrl = getScene()?.snapshot()
      if (!dataUrl) {
        throw new Error('the scene is not drawing')
      }
      await save(
        exportName(stem, 'scene', 'html'),
        snapshotHtml(
          dataUrl,
          `${stem ?? 'SensorView'} — frame ${frame}`,
          // Said rather than left for someone to notice: the axis labels are
          // CSS2D elements over the canvas, so they are not in the capture.
          `${stem ?? 'Log'}, frame ${frame + 1} of ${frameCount}. ` +
            'Captured from the 3D view; axis labels are drawn over the canvas and are not included.'
        ),
        'utf8',
        [{ name: 'HTML page', extensions: ['html'] }]
      )
    })

  const exportFigureHtml = () =>
    run('Figure', async () => {
      const pane = document.querySelector('.sv-pane-graph.js-plotly-plot') as
        | (HTMLElement & { data?: unknown[]; layout?: Record<string, unknown> })
        | null
      if (!pane?.data?.length) {
        throw new Error('no dock view to export')
      }
      // The library is fetched rather than imported: it is 4.7 MB, and
      // bundling it into the app to serve an export taken once a session
      // would put it in memory for every session that never exports.
      const { default: url } = await import('plotly.js/dist/plotly.min.js?url')
      const source = await (await fetch(url)).text()
      await save(
        exportName(stem, 'figure', 'html'),
        standaloneHtml(
          { data: pane.data, layout: pane.layout ?? {} },
          `${stem ?? 'SensorView'} — figure`,
          source
        ),
        'utf8',
        [{ name: 'HTML page', extensions: ['html'] }]
      )
    })

  const exportAnimation = () =>
    run('Animation', async () => {
      const canvas = getScene()?.canvas()
      if (!canvas) {
        throw new Error('the scene is not drawing')
      }
      cancelled.current = false
      const was = frame

      const recording = await recordScene({
        canvas,
        frameCount,
        fps: 10,
        cancelled: () => cancelled.current,
        onProgress: (done, total) => setBusy(`Animation ${done}/${total}`),
        show: async (at) => {
          setFrame(at)

          // The cloud is a read per frame through the data process, and it
          // does not land within a repaint. Waiting only for the paint
          // recorded each frame with the previous frame's cloud under it --
          // which looks like a lag of one frame and is a different picture
          // from the one on screen.
          const state = useStore.getState()
          if (state.cloudOn && state.cloudDisplay) {
            const wanted = state.table?.frameIds[at]
            const until = Date.now() + 5000
            while (Date.now() < until) {
              const now = useStore.getState().cloud
              if (now && now.frameId === wanted) {
                break
              }
              await new Promise((resolve) => setTimeout(resolve, 20))
            }
          }

          // Two frames: one for React to push the payload into the scene, one
          // for the scene's own on-demand loop to draw it. Recording after a
          // single frame captures the previous frame's pixels.
          await new Promise((resolve) => requestAnimationFrame(() => resolve(null)))
          await new Promise((resolve) => requestAnimationFrame(() => resolve(null)))
        }
      })

      setFrame(was)
      if (!recording) {
        throw new Error('nothing was recorded')
      }
      await save(
        exportName(stem, 'animation', recording.extension),
        await toBase64(recording.blob),
        'base64',
        [{ name: 'Video', extensions: [recording.extension] }]
      )
    })

  return (
    <div className="sv-export" ref={menu.containerRef}>
      <button
        type="button"
        className="sv-icon-btn"
        onClick={() => (busy ? (cancelled.current = true) : menu.toggle())}
        {...menu.triggerProps}
        title={busy ? `${busy} — click to stop` : 'Export'}
        // The same button is "open the menu" when idle and "stop" while a job
        // runs. The name has to say which, or a job is cancelled by a button
        // that still announces itself as Export.
        aria-label={busy ? `Stop the ${busy} export` : 'Export'}
      >
        <i className={`bi bi-${busy ? 'stop-circle' : 'download'}`} aria-hidden="true" />
      </button>

      {busy && <span className="sv-export-note">{busy}…</span>}
      {!busy && note && (
        <span className="sv-export-note" role="status">
          {note}
        </span>
      )}

      {menu.open && (
        <div className="sv-menu sv-menu-right" role="menu" ref={menu.menuRef}>
          <Item label="Table as CSV" hint="the filtered rows" onClick={exportCsv} />
          <Item label="Scene as PNG" hint="this frame" onClick={exportPng} />
          <Item label="Scene as HTML" hint="this frame, with a caption" onClick={exportHtml} />
          <Item
            label="Figure as HTML"
            hint="the dock view, self-contained"
            onClick={exportFigureHtml}
          />
          <Item label="Animation" hint="every frame, as video" onClick={exportAnimation} />
        </div>
      )}
    </div>
  )
}

function Item({
  label,
  hint,
  onClick
}: {
  label: string
  hint: string
  onClick: () => void
}) {
  return (
    <button type="button" role="menuitem" className="sv-menu-item" onClick={onClick}>
      <span className="sv-menu-label">{label}</span>
      <span className="sv-menu-marks">{hint}</span>
    </button>
  )
}
