// The bottom dock: two slots, each showing one of the analysis views.
//
// Two rather than a grid of six, carried over from the Dash dock: the views
// are for comparing, and two side by side at a readable size beats six at a
// size where none of them can be read.
//
// Every view draws the **whole filtered table**, not the frame on the slider.
// A histogram of one frame's five hundred detections says nothing. That makes
// the dock the one place where the filters are the whole input, which is why
// the rows are gathered here and handed down rather than each view filtering
// for itself.

import { useEffect, useMemo, useState } from 'react'

import { filterAll, type Table } from '@shared/table'

import { maskedRows } from '../figures/common'
import { buildView, VIEW_LABELS, type ViewId, type ViewOptions } from '../figures/views'
import { PlotlyFigure } from './PlotlyFigure'
import { useStore } from '../store'

interface SlotState {
  view: ViewId | null
  x: string
  y: string
  colour: string
  dimensions: string[]
  logScale: boolean
  histnorm: 'probability' | 'density'
}

const EMPTY: SlotState = {
  view: null,
  x: '',
  y: '',
  colour: 'None',
  dimensions: [],
  logScale: false,
  histnorm: 'probability'
}

export function AnalysisDock({ theme }: { theme: 'dark' | 'light' }) {
  const table = useStore((s) => s.table)
  const filters = useStore((s) => s.filters)
  const keys = useStore((s) => s.keys)
  const colormap = useStore((s) => s.colormap)
  const stems = useStore((s) => s.stems)

  const [collapsed, setCollapsed] = useState(false)
  const [slots, setSlots] = useState<[SlotState, SlotState]>([
    { ...EMPTY, view: 'histogram' },
    { ...EMPTY }
  ])

  // One pass over the table per filter change, shared by both slots.
  const rows = useMemo(
    () => (table ? maskedRows(filterAll(table, filters)) : new Int32Array(0)),
    [table, filters]
  )

  const numeric = useMemo(
    () =>
      table
        ? [...table.columns.values()].filter((c) => c.kind === 'number').map((c) => c.name)
        : [],
    [table]
  )
  // The frame column is selectable but never chosen for you: a scatter of
  // frame against time is a straight line, which is a dull thing to greet
  // someone with when the position columns are right there.
  const preferred = useMemo(
    () => numeric.filter((name) => name !== table?.frameKey),
    [numeric, table]
  )
  const categorical = useMemo(
    () =>
      table
        ? [...table.columns.values()].filter((c) => c.kind === 'string').map((c) => c.name)
        : [],
    [table]
  )

  // A slot's columns cannot be chosen until a table says which exist, and
  // they have to be re-chosen when the log changes: a column name that is not
  // in the new table reads back as zeros from every row, which draws a
  // plausible-looking chart of nothing. That was this component's first bug.
  useEffect(() => {
    if (numeric.length === 0 && categorical.length === 0) {
      return
    }
    setSlots((current) => [
      defaults(current[0], numeric, categorical, preferred),
      defaults(current[1], numeric, categorical, preferred)
    ])
  }, [numeric, categorical, preferred])

  if (!table) {
    return null
  }

  const set = (index: 0 | 1, patch: Partial<SlotState>) =>
    setSlots((current) => {
      const next: [SlotState, SlotState] = [current[0], current[1]]
      next[index] = defaults({ ...next[index], ...patch }, numeric, categorical, preferred)
      return next
    })

  const shown = slots.filter((slot) => slot.view !== null).length

  return (
    <div className="sv-dock-wrap">
      <div className={`sv-dock${collapsed ? ' sv-collapsed' : ''}`}>
        <div className="sv-dock-head">
          {([0, 1] as const).map((index) => (
            <div className="sv-slot-picker" key={index}>
              <select
                value={slots[index].view ?? ''}
                aria-label={`Slot ${index + 1} view`}
                onChange={(event) =>
                  set(index, { view: (event.target.value || null) as ViewId | null })
                }
              >
                <option value="">Empty</option>
                {(Object.keys(VIEW_LABELS) as ViewId[]).map((id) => (
                  <option key={id} value={id}>
                    {VIEW_LABELS[id]}
                  </option>
                ))}
              </select>
            </div>
          ))}

          <div className="sv-dock-actions">
            <button
              type="button"
              className="sv-icon-btn"
              onClick={() => setCollapsed((on) => !on)}
              aria-label={collapsed ? 'Expand the dock' : 'Collapse the dock'}
              title={collapsed ? 'Expand' : 'Collapse'}
            >
              <i className={`bi bi-chevron-${collapsed ? 'up' : 'down'}`} />
            </button>
          </div>
        </div>

        <div className="sv-dock-grid">
          {([0, 1] as const).map((index) => {
            const slot = slots[index]
            if (!slot.view || !slot.x) {
              return null
            }
            return (
              <div
                key={index}
                className={`sv-dock-pane sv-slot-${index === 0 ? 'a' : 'b'}${
                  shown === 2 && index === 1 ? ' sv-slot-paired' : ''
                }`}
              >
                <Pane
                  slot={slot}
                  table={table}
                  rows={rows}
                  keys={keys}
                  colormap={colormap}
                  theme={theme}
                  numeric={numeric}
                  categorical={categorical}
                  stems={stems}
                  onChange={(patch) => set(index, patch)}
                />
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

/**
 * Fill in the columns a view needs but has not been given one for.
 *
 * Run on every change rather than only on the first, because switching view
 * changes which fields are read: a histogram needs only x, and switching it to
 * a scatter with no y would draw nothing and look broken.
 */
function defaults(
  slot: SlotState,
  numeric: string[],
  categorical: string[],
  preferred: string[]
): SlotState {
  const next = { ...slot }
  if (!numeric.includes(next.x)) {
    next.x = preferred[0] ?? numeric[0] ?? ''
  }
  if (!numeric.includes(next.y)) {
    next.y = preferred[1] ?? preferred[0] ?? numeric[0] ?? ''
  }
  if (next.colour !== 'None' && ![...numeric, ...categorical].includes(next.colour)) {
    next.colour = categorical[0] ?? 'None'
  }
  if (next.view === 'violin' && !categorical.includes(next.x)) {
    // A violin's x is what it groups by, so it is a category, not a number.
    next.x = categorical[0] ?? ''
  }
  if (next.view === 'parcats' && next.dimensions.length === 0) {
    next.dimensions = categorical.slice(0, 2)
  }
  return next
}

function Pane({
  slot,
  table,
  rows,
  keys,
  colormap,
  theme,
  numeric,
  categorical,
  stems,
  onChange
}: {
  slot: SlotState
  table: Table
  rows: Int32Array
  keys: ViewOptions['keys']
  colormap: string
  theme: 'dark' | 'light'
  numeric: string[]
  categorical: string[]
  stems: string[]
  onChange: (patch: Partial<SlotState>) => void
}) {
  const figure = useMemo(
    () =>
      buildView(slot.view!, table, rows, {
        x: slot.x,
        y: slot.y,
        colour: slot.colour,
        dimensions: slot.dimensions,
        colormap,
        keys,
        theme,
        histnorm: slot.histnorm,
        logScale: slot.logScale
      }),
    [slot, table, rows, colormap, keys, theme]
  )

  const view = slot.view!
  const revision = [stems.join('+'), view, slot.x, slot.y, slot.colour].join('|')
  const wantsY = view === 'scatter' || view === 'heatmap' || view === 'violin'
  const xChoices = view === 'violin' ? categorical : numeric

  return (
    <div className="sv-pane">
      <div className="sv-pane-controls">
        {view !== 'parcats' && (
          <Picker
            label="X"
            value={slot.x}
            choices={xChoices}
            onChange={(x) => onChange({ x })}
          />
        )}
        {wantsY && (
          <Picker label="Y" value={slot.y} choices={numeric} onChange={(y) => onChange({ y })} />
        )}
        {view !== 'heatmap' && (
          <Picker
            label="Colour"
            value={slot.colour}
            choices={['None', ...categorical, ...numeric]}
            onChange={(colour) => onChange({ colour })}
          />
        )}
        {view === 'histogram' && (
          <Picker
            label="Norm"
            value={slot.histnorm}
            choices={['probability', 'density']}
            onChange={(histnorm) =>
              onChange({ histnorm: histnorm as SlotState['histnorm'] })
            }
          />
        )}
        {view === 'heatmap' && (
          <label className="sv-switch-row">
            <input
              type="checkbox"
              checked={slot.logScale}
              onChange={(event) => onChange({ logScale: event.target.checked })}
            />
            <span>log counts</span>
          </label>
        )}
        {view === 'parcats' &&
          [0, 1, 2].map((at) => (
            <Picker
              key={at}
              label={`Dim ${at + 1}`}
              value={slot.dimensions[at] ?? 'None'}
              choices={['None', ...categorical]}
              onChange={(name) => {
                const dimensions = [...slot.dimensions]
                if (name === 'None') {
                  dimensions.splice(at, 1)
                } else {
                  dimensions[at] = name
                }
                onChange({ dimensions: dimensions.filter(Boolean) })
              }}
            />
          ))}
      </div>

      <PlotlyFigure
        data={figure.data}
        layout={figure.layout}
        className="sv-pane-graph"
        // The axes follow what the figure is of. A zoom has to survive a
        // slider tick -- that is the whole reason uirevision exists -- and
        // must not survive a change of view, of column, or of which logs are
        // loaded, each of which is a different extent entirely.
        revision={revision}
      />
    </div>
  )
}

function Picker({
  label,
  value,
  choices,
  onChange
}: {
  label: string
  value: string
  choices: string[]
  onChange: (value: string) => void
}) {
  return (
    <label className="sv-pane-field">
      <span className="sv-section-label">{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {choices.map((choice) => (
          <option key={choice} value={choice}>
            {choice}
          </option>
        ))}
      </select>
    </label>
  )
}
