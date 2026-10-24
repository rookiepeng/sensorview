// The top bar's export menu: the table, and the 3D view.
//
// The table goes out as CSV or Parquet, for the frame on the slider or for
// every frame; the 3D view as a PNG of this frame or a video of all of them.
// The 2D figures are exported from where they are drawn -- the dock and the
// curves card each have their own button (`FigureExport.tsx`).
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

import { useRef, useState } from 'react'
import { DropdownMenu } from 'radix-ui'

import { filterAll, frameRows } from '@shared/table'

import { maskedRows } from '../figures/common'
import { recordScene, toBase64 } from '../export/animation'
import { exportName, tableColumns, tableCsv } from '../export/exporters'
import { getScene } from '../sceneHandle'
import { useStore } from '../store'
import { useExport } from '../useExport'
import { Icon } from './Icon'

export function ExportMenu() {
  const table = useStore((s) => s.table)
  const filters = useStore((s) => s.filters)
  const keys = useStore((s) => s.keys)
  const stem = useStore((s) => s.stem)
  const frame = useStore((s) => s.frame)
  const frameCount = useStore((s) => s.frameCount)
  const setFrame = useStore((s) => s.setFrame)

  const [open, setOpen] = useState(false)
  const { busy, setBusy, note, save, run } = useExport()
  const cancelled = useRef(false)

  if (!table) {
    return null
  }

  // The menu has closed itself by the time a job runs, returning focus to
  // the trigger -- which is also the cancel button for the job about to
  // start, so the keyboard lands where it is needed.

  /**
   * The filtered rows, either every frame's or just the frame on the slider.
   *
   * Both, because the Dash app had both: a whole log is what you hand to
   * another tool, and one frame is what you paste into a bug report.
   */
  const scopedRows = (scope: 'all' | 'current') => {
    const rows = maskedRows(filterAll(table!, filters))
    if (scope === 'all') {
      return rows
    }
    const wanted = new Set(frameRows(table!, frame))
    return rows.filter((row) => wanted.has(row))
  }
  const scopeName = (scope: 'all' | 'current') => (scope === 'all' ? 'table' : `frame${frame}`)

  const exportCsv = (scope: 'all' | 'current') =>
    run(scope === 'all' ? 'CSV' : 'CSV (frame)', async () => {
      await save(
        exportName(stem, scopeName(scope), 'csv'),
        tableCsv(table!, scopedRows(scope), keys),
        'utf8',
        [{ name: 'CSV', extensions: ['csv'] }]
      )
    })

  // Written by the data process, which has polars; the renderer has no
  // Parquet writer and the bundle should not grow one for this.
  const exportParquet = (scope: 'all' | 'current') =>
    run(scope === 'all' ? 'Parquet' : 'Parquet (frame)', async () => {
      const result = await window.sensorview.data('tableParquet', {
        columns: tableColumns(table!, scopedRows(scope))
      })
      if (!result.ok || !result.data) {
        throw new Error(result.error ?? 'could not write the Parquet file')
      }
      await save(
        exportName(stem, scopeName(scope), 'parquet'),
        await toBase64(new Blob([result.data as BlobPart])),
        'base64',
        [{ name: 'Parquet', extensions: ['parquet'] }]
      )
    })

  const exportPng = () =>
    run('PNG', async () => {
      const dataUrl = getScene()?.snapshot()
      if (!dataUrl) {
        throw new Error('the 3D view is not drawing')
      }
      await save(
        exportName(stem, 'scene', 'png'),
        dataUrl.slice(dataUrl.indexOf(',') + 1),
        'base64',
        [{ name: 'PNG image', extensions: ['png'] }]
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

  // The trigger is two controls in one: it opens the menu when idle and stops
  // the running job otherwise. Radix owns the open half, so the busy half has
  // to stop the event reaching it -- `onPointerDown` rather than `onClick`,
  // because that is where `DropdownMenu.Trigger` opens.
  const stopIfBusy = (event: React.PointerEvent | React.KeyboardEvent) => {
    if (busy) {
      event.preventDefault()
      cancelled.current = true
    }
  }

  return (
    <DropdownMenu.Root open={open} onOpenChange={setOpen} modal={false}>
      <div className="sv-export">
        <DropdownMenu.Trigger asChild>
          <button
            type="button"
            className="sv-icon-btn"
            onPointerDown={stopIfBusy}
            title={busy ? `${busy} — click to stop` : 'Export'}
            // The same button is "open the menu" when idle and "stop" while a
            // job runs. The name has to say which, or a job is cancelled by a
            // button that still announces itself as Export.
            aria-label={busy ? `Stop the ${busy} export` : 'Export'}
          >
            <Icon name={busy ? 'stop' : 'export'} />
          </button>
        </DropdownMenu.Trigger>

        {busy && <span className="sv-export-note">{busy}…</span>}
        {!busy && note && (
          <span className="sv-export-note" role="status">
            {note}
          </span>
        )}

        {/* Portalled, so the glass top bar is not its containing block and
            Radix can keep it inside the window. `smoke.ts` finds it by
            `data-sv-menu`. */}
        <DropdownMenu.Portal>
        <DropdownMenu.Content
          className="sv-menu"
          data-sv-menu="export"
          side="bottom"
          align="end"
          sideOffset={5}
          collisionPadding={8}
        >
          <DropdownMenu.Label className="sv-menu-heading">Table</DropdownMenu.Label>
          <Item
            label="This frame as CSV"
            hint="the filtered rows on screen"
            onSelect={() => exportCsv('current')}
          />
          <Item
            label="All frames as CSV"
            hint="every filtered row"
            onSelect={() => exportCsv('all')}
          />
          <Item
            label="This frame as Parquet"
            hint="the filtered rows on screen"
            onSelect={() => exportParquet('current')}
          />
          <Item
            label="All frames as Parquet"
            hint="every filtered row"
            onSelect={() => exportParquet('all')}
          />
          <DropdownMenu.Separator className="sv-menu-sep" />
          <DropdownMenu.Label className="sv-menu-heading">3D view</DropdownMenu.Label>
          <Item label="3D view as PNG" hint="this frame" onSelect={exportPng} />
          <Item label="Animation" hint="every frame, as video" onSelect={exportAnimation} />
        </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </div>
    </DropdownMenu.Root>
  )
}

function Item({
  label,
  hint,
  onSelect
}: {
  label: string
  hint: string
  onSelect: () => void
}) {
  return (
    // `asChild` so the button and its two spans stay exactly as they were:
    // `smoke.ts` reads `.sv-menu-item`, `.sv-menu-label` and `.sv-menu-marks`
    // and counts on the shape.
    <DropdownMenu.Item asChild onSelect={onSelect}>
      <button type="button" className="sv-menu-item">
        <span className="sv-menu-label">{label}</span>
        <span className="sv-menu-marks">{hint}</span>
      </button>
    </DropdownMenu.Item>
  )
}
