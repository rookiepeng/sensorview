// The analysis dock: two slots, each showing one of the analysis views.
//
// Two rather than a grid of six, carried over from the Dash dock: the views
// are for comparing, and two side by side at a readable size beats six at a
// size where none of them can be read.
//
// It sits at the foot of the centre column rather than across the whole
// window. Full width it was taking a third of the rail's and the inspector's
// height and spending it on two 780x280 letterboxes; in the centre the panes
// are about 450 wide, which is the shape a chart wants.
//
// Every view draws the **whole filtered table**, not the frame on the slider.
// A histogram of one frame's five hundred detections says nothing. That makes
// the dock the one place where the filters are the whole input, which is why
// the rows are gathered here and handed down rather than each view filtering
// for itself.

import { useEffect, useMemo, useState } from 'react'

import { filterAll, frameRows, type Table } from '@shared/table'

import { maskedRows } from '../figures/common'
import { buildView, VIEW_LABELS, type ViewId, type ViewOptions } from '../figures/views'
import { CollapseButton, Picker, Switch } from './Controls'
import { Splitter } from './Splitter'
import { BOUNDS, useLayout } from '../layout'
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
  /**
   * Whether a scatter draws this frame or every frame.
   *
   * Only the scatters had this in the Dash app, and it defaulted to the
   * current frame. The other four views have no such switch and always drew
   * the whole filtered table, which is what a distribution is of.
   */
  scope: 'current' | 'all'
  /**
   * Fixed axis limits, as typed.
   *
   * Kept as strings so a half-typed "-" or an empty box is a state rather
   * than a NaN. An end left empty means autorange for that axis, which is
   * what the pane does by default.
   */
  limits: { xMin: string; xMax: string; yMin: string; yMax: string }
}

const EMPTY: SlotState = {
  view: null,
  x: '',
  y: '',
  colour: 'None',
  dimensions: [],
  logScale: false,
  histnorm: 'probability',
  scope: 'current',
  limits: { xMin: '', xMax: '', yMin: '', yMax: '' }
}

export function AnalysisDock({ theme }: { theme: 'dark' | 'light' }) {
  const table = useStore((s) => s.table)
  const filters = useStore((s) => s.filters)
  const keys = useStore((s) => s.keys)
  const colormap = useStore((s) => s.colormap)
  const stems = useStore((s) => s.stems)
  // Visibility lives in a typed array on the table, which a memo cannot see
  // change; this is what tells it to re-filter.
  const visibleRev = useStore((s) => s.visibleRev)
  const frame = useStore((s) => s.frame)
  const hideRows = useStore((s) => s.hideRows)
  const showRows = useStore((s) => s.showRows)

  const collapsed = useLayout((s) => s.dockCollapsed)
  const toggleCollapsed = useLayout((s) => s.toggle)
  const dockH = useLayout((s) => s.dockH)
  const setSize = useLayout((s) => s.setSize)
  const [selection, setSelection] = useState<number[]>([])
  const [slots, setSlots] = useState<[SlotState, SlotState]>([
    { ...EMPTY, view: 'histogram' },
    { ...EMPTY }
  ])

  // One pass over the table per filter change, shared by both slots.
  const rows = useMemo(
    () => {
    // `visibleRev` is a real dependency: the visibility it stands for lives
    // in a typed array that is mutated in place, which a memo cannot see.
    // Referenced rather than only listed, so the rule agrees.
    void visibleRev
      return table ? maskedRows(filterAll(table, filters)) : new Int32Array(0)
    },
    [table, filters, visibleRev]
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

  // A selection is remembered rather than acted on: hiding on the lasso
  // itself would make an accidental drag destructive, and there is no undo
  // for something that leaves no trace of what it removed.
  const selectRows = (rows: number[]) => setSelection(rows)

  const set = (index: 0 | 1, patch: Partial<SlotState>) =>
    setSlots((current) => {
      const next: [SlotState, SlotState] = [current[0], current[1]]
      next[index] = defaults({ ...next[index], ...patch }, numeric, categorical, preferred)
      return next
    })

  const shown = slots.filter((slot) => slot.view !== null).length

  return (
    <div className="sv-dock-wrap">
      {/* `.sv-dock-wrap:has(.sv-dock.sv-collapsed) .sv-splitter` has been in
          app.css since the port, waiting for a handle to hide. */}
      {!collapsed && (
        <Splitter
          id="dock-splitter"
          axis="row"
          label="Analysis dock height"
          measure={() => document.querySelector('.sv-dock')?.getBoundingClientRect().height ?? 0}
          onResize={(px) => setSize('dockH', px)}
          onReset={() => setSize('dockH', null)}
          value={dockH}
          invert
          {...BOUNDS.dock}
        />
      )}
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

          {/* What to do with a selection, beside the dock's own controls.
              Present only while something is selected -- two buttons that do
              nothing are worse than none. */}
          {selection.length > 0 && (
            <div className="sv-dock-selection">
              <span className="sv-export-note">{selection.length} selected</span>
              <button
                type="button"
                className="sv-text-btn"
                onClick={() => {
                  hideRows(selection)
                  setSelection([])
                }}
              >
                Hide
              </button>
              <button
                type="button"
                className="sv-text-btn"
                onClick={() => {
                  showRows(selection)
                  setSelection([])
                }}
              >
                Show
              </button>
            </div>
          )}

          <div className="sv-dock-actions">
            {/* Swapping beats re-picking both slots when the comparison is
                the right way round but on the wrong sides. */}
            <button
              type="button"
              className="sv-icon-btn"
              onClick={() => setSlots((current) => [current[1], current[0]])}
              aria-label="Swap the two slots"
              title="Swap the two slots"
            >
              <i className="bi bi-arrow-left-right" />
            </button>
            <CollapseButton
              collapsed={collapsed}
              onToggle={() => toggleCollapsed('dockCollapsed')}
              subject="dock"
              edge="bottom"
            />
          </div>
        </div>

        <div className="sv-dock-grid">
          {([0, 1] as const).map((index) => {
            const slot = slots[index]
            if (!slot.view) {
              return null
            }
            // A view is chosen but the table has no column of the kind it
            // needs -- a violin with nothing categorical, a histogram with
            // nothing numeric. This used to draw a blank pane under a
            // picker that said "Histogram", which reads as a broken figure.
            if (!slot.x) {
              return (
                <div key={index} className={`sv-dock-pane sv-slot-${index === 0 ? 'a' : 'b'}`}>
                  <p className="sv-rail-note">
                    {slot.view === 'violin'
                      ? 'This table has no categorical column for a violin plot.'
                      : 'This table has no numeric column for this view.'}
                  </p>
                </div>
              )
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
                  frame={frame}
                  onSelectRows={selectRows}
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
  frame,
  onSelectRows,
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
  frame: number
  onSelectRows: (rows: number[]) => void
  onChange: (patch: Partial<SlotState>) => void
}) {
  // The scatter's scope narrows the shared rows to the frame on the slider.
  // `frameRows` is what `buildFrame` uses, so a current-frame scatter and the
  // scene resolve a slider position identically.
  const scoped = useMemo(() => {
    if (slot.view !== 'scatter' || slot.scope === 'all') {
      return rows
    }
    const wanted = new Set(frameRows(table, frame))
    return rows.filter((row) => wanted.has(row))
  }, [slot.view, slot.scope, rows, table, frame])

  const [showLimits, setShowLimits] = useState(false)

  const figure = useMemo(
    () =>
      buildView(slot.view!, table, scoped, {
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
    [slot, table, scoped, colormap, keys, theme]
  )

  // Applied over the built figure rather than inside the builders: a limit is
  // a view setting, not a property of the data, and the builders stay pure
  // functions of the table.
  const limited = useMemo(() => {
    const span = (low: string, high: string) => {
      const a = Number.parseFloat(low)
      const b = Number.parseFloat(high)
      return Number.isFinite(a) && Number.isFinite(b) ? ([a, b] as [number, number]) : null
    }
    const x = span(slot.limits.xMin, slot.limits.xMax)
    const y = span(slot.limits.yMin, slot.limits.yMax)
    if (!x && !y) {
      return figure
    }
    return {
      data: figure.data,
      layout: {
        ...figure.layout,
        xaxis: { ...figure.layout.xaxis, ...(x ? { range: x, autorange: false } : {}) },
        yaxis: { ...figure.layout.yaxis, ...(y ? { range: y, autorange: false } : {}) }
      }
    }
  }, [figure, slot.limits])

  const view = slot.view!
  const revision = [stems.join('+'), view, slot.x, slot.y, slot.colour].join('|')
  const wantsY = view === 'scatter' || view === 'heatmap' || view === 'violin'
  const xChoices = view === 'violin' ? categorical : numeric

  return (
    <div className="sv-pane">
      <div className="sv-pane-controls">
        {/* Only the scatter: the other four draw a distribution, which one
            frame's few hundred points does not describe. */}
        {view === 'scatter' && (
          <Picker
            label="Frames"
            value={slot.scope}
            choices={['current', 'all']}
            onChange={(scope) => onChange({ scope: scope as SlotState['scope'] })}
          />
        )}
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
          <Switch checked={slot.logScale} onChange={(logScale) => onChange({ logScale })}>
            Log counts
          </Switch>
        )}
        {/* Limits last in the strip, since they are set once and then left
            alone -- unlike the pickers beside them. */}
        {view !== 'parcats' && (
          <button
            type="button"
            className={`sv-icon-btn sv-limits-btn${showLimits ? ' sv-limits-on' : ''}`}
            onClick={() => setShowLimits((on) => !on)}
            aria-expanded={showLimits}
            aria-label="Set fixed axis limits"
            title="Set fixed axis limits"
          >
            <i className="bi bi-arrows-angle-expand" />
          </button>
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

      {showLimits && view !== 'parcats' && (
        <div className="sv-pane-controls sv-pane-limits">
          {(
            [
              ['xMin', 'x min'],
              ['xMax', 'x max'],
              ['yMin', 'y min'],
              ['yMax', 'y max']
            ] as const
          ).map(([field, label]) => (
            <label className="sv-pane-field" key={field}>
              <span className="sv-section-label">{label}</span>
              <input
                type="number"
                value={slot.limits[field]}
                placeholder="auto"
                onChange={(event) =>
                  onChange({ limits: { ...slot.limits, [field]: event.target.value } })
                }
              />
            </label>
          ))}
          <button
            type="button"
            className="sv-text-btn"
            onClick={() => onChange({ limits: { xMin: '', xMax: '', yMin: '', yMax: '' } })}
          >
            Auto
          </button>
        </div>
      )}

      <PlotlyFigure
        data={limited.data}
        layout={limited.layout}
        className="sv-pane-graph"
        // The axes follow what the figure is of. A zoom has to survive a
        // slider tick -- that is the whole reason uirevision exists -- and
        // must not survive a change of view, of column, or of which logs are
        // loaded, each of which is a different extent entirely.
        revision={revision}
        // Only the scatter carries row ids, so only it can turn a selection
        // into a visibility change. A lasso on a histogram encloses bars,
        // not rows.
        onSelected={view === 'scatter' ? onSelectRows : undefined}
        // The toolbar is how box and lasso select are reached. Without it
        // the selection path exists and nothing can start one.
        tools
        
      />
    </div>
  )
}
