// The export button on the analysis dock and on the curves card.
//
// One menu per place a figure is, rather than one entry in the top bar that
// had to guess which dock pane was meant -- it took the first one in the
// page, whichever side that was. Here each figure is named in the menu, so
// with two panes up the left and the right are separate choices.
//
// Every figure is rebuilt in the light theme before it is written: a file is
// read on white paper, whatever the app happened to be showing.

import { DropdownMenu } from 'radix-ui'
import { Fragment } from 'react'

import { exportName } from '../export/exporters'
import { FORMATS, figureFile, type ExportFigure, type FigureFormat } from '../export/figure'
import { useStore } from '../store'
import { useExport } from '../useExport'
import { Icon } from './Icon'

export interface FigureTarget {
  /** Goes into the filename, so a short slug: `left`, `curve-snr`. */
  id: string
  /** Heads the figure's entries in the menu. */
  label: string
  /** The figure in the light theme, or null when there is nothing drawn. */
  build: () => ExportFigure | null
}

export function FigureExportMenu({
  targets,
  subject
}: {
  targets: FigureTarget[]
  /** What the figures are, for the button's name: "dock", "curve". */
  subject: string
}) {
  const stem = useStore((s) => s.stem)
  const { busy, note, save, run } = useExport()

  if (targets.length === 0) {
    return null
  }

  const exportOne = (target: FigureTarget, format: FigureFormat) =>
    run(`${FORMATS[format].label}`, async () => {
      const figure = target.build()
      if (!figure) {
        throw new Error('nothing drawn to export')
      }
      const file = await figureFile(figure, format)
      await save(exportName(stem, target.id, format), file.data, file.encoding, [
        FORMATS[format].filter
      ])
    })

  return (
    <DropdownMenu.Root modal={false}>
      <span className="sv-figure-export">
        {busy && <span className="sv-figure-note">{busy}…</span>}
        {!busy && note && (
          <span className="sv-figure-note" role="status">
            {note}
          </span>
        )}
        <DropdownMenu.Trigger asChild>
          <button
            type="button"
            className="sv-icon-btn"
            disabled={busy !== null}
            title={`Export the ${subject} figure`}
            aria-label={`Export the ${subject} figure`}
          >
            <Icon name="export" />
          </button>
        </DropdownMenu.Trigger>
      </span>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          className="sv-menu"
          data-sv-menu={`export-${subject}`}
          side="bottom"
          align="end"
          sideOffset={5}
          collisionPadding={8}
        >
          {targets.map((target, at) => (
            <Fragment key={target.id}>
              {at > 0 && <DropdownMenu.Separator className="sv-menu-sep" />}
              <DropdownMenu.Label className="sv-menu-heading">{target.label}</DropdownMenu.Label>
              {(Object.keys(FORMATS) as FigureFormat[]).map((format) => (
                <DropdownMenu.Item
                  key={format}
                  asChild
                  onSelect={() => void exportOne(target, format)}
                >
                  <button type="button" className="sv-menu-item">
                    <span className="sv-menu-label">{FORMATS[format].label}</span>
                    <span className="sv-menu-marks">{FORMATS[format].hint}</span>
                  </button>
                </DropdownMenu.Item>
              ))}
            </Fragment>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}
